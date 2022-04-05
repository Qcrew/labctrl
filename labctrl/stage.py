"""
This module contains methods and classes for 
    1. Locating resource classes in specified resources folder
    2. Loading / Dumping resource instances from / to yaml config files
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
from pathlib import Path
import pkgutil
import time

import Pyro5.api as pyro
import Pyro5.errors

from labctrl.logger import logger
from labctrl.resource import Resource, Instrument
from labctrl.settings import Settings
import labctrl.yamlizer as yml

_PORT = 9090  # port to bind a remote stage on (used to initialize Pyro Daemon)
_SERVERNAME = "STAGE"
# remote stage unique resource identifier (URI)
_STAGE_URI = f"PYRO:{_SERVERNAME}@localhost:{_PORT}"


class StagingError(Exception):
    """ """


@pyro.expose
class Stage:
    """ """

    def __init__(self, *configpaths: Path, daemon: pyro.Daemon | None = None) -> None:
        """configpaths: path to YAML file containing Resource classes to be instantiated
        daemon: if not None, this stage will be a remote stage that serves the Resources in the configpath remotely with Pyro. you can send in multiple configpaths, the resources will be bundled up on the same stage."""

        logger.debug("Initializing a stage...")

        # self._config and self._services will be updated by _setup()
        self._config = {}  # dict with key: configpath, value: list of Resources

        # if local, services is a dict with key: resource name, value: Resource object
        # if remote, it is a dict with key: resource name, value: remote resource URI
        self._services = {}

        self._daemon = daemon

        if configpaths:
            self._register()  # locate and register resource classes with yaml and pyro
            self._load(*configpaths)
            if self._daemon is not None:
                self._serve()

    def _register(self) -> None:
        """ """
        # ensure that the resourcepath is available
        resourcepath = Settings().resourcepath
        logger.debug(f"Found labctrl setting {resourcepath = }.")
        if resourcepath is None:
            message = (
                f"Unable to register resources as no resource path is specified. "
                f"Please set a resource path through the Settings context manager."
            )
            raise StagingError(message)

        try:
            resource_classes = locate(Path(resourcepath))
        except TypeError:
            message = (
                f"Unable to cast {resourcepath = } to a 'Path' object. "
                f"Please set 'resourcepath' with a string that is a valid path."
            )
            raise StagingError(message) from None
        else:
            if not resource_classes:
                message = "Unable to setup stage as no resource classes were found."
                raise StagingError(message)

            for resource_class in resource_classes:
                yml.register(resource_class)
                if self._daemon is not None:
                    pyro.expose(resource_class)
                    logger.debug(f"Exposed '{resource_class}' with pyro.")

    def _load(self, *configpaths: Path) -> None:
        """ """
        num_resources = 0
        for configpath in configpaths:
            resources = yml.load(configpath)
            self._config[configpath] = resources
            num_resources += len(resources)
            logger.info(f"Found {len(resources)} resource(s) in '{configpath.name}'.")

            for resource in resources:
                try:
                    resource_name = resource.name
                except (TypeError, AttributeError):
                    message = (
                        f"A {resource = } in {configpath = } does not have a 'name'. "
                        f"All resources must have a '.name' attribute to be staged."
                    )
                    raise StagingError(message) from None
                else:
                    self._services[resource.name] = resource
                    setattr(self, resource_name, resource)
                    logger.info(f"Set stage attribute '{resource_name}'")

        if num_resources != len(self._services):
            message = (
                f"Two or more resources in {configpaths = } share a name. "
                f"All resources must have unique names to be staged."
            )
            raise StagingError(message)

    def _serve(self) -> None:
        """ """
        for name, resource in self._services.items():
            try:
                uri = self._daemon.register(resource, objectId=name)
            except (TypeError, AttributeError):
                message = (
                    f"Daemon must be of type '{pyro.Daemon}', not {type(self._daemon)}."
                )
                raise StagingError(message) from None
            else:
                self._services[name] = uri
                logger.info(f"Served '{resource}' remotely at '{uri}'.")

    def __enter__(self) -> Stage:
        """ """
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        self.teardown()

    def save(self) -> None:
        """save current state state to respective yaml configs"""
        logger.debug(f"Saving the current state of staged resources to configs...")
        for configpath, resources in self._config.items():
            yml.dump(configpath, *resources)

    @property
    def services(self) -> dict[str, str]:
        """if remote stage, return dict with key = resource name and value = uri
        if local stage, return dict with key = resource name and value - resource object
        """
        return self._services.copy()

    def teardown(self) -> None:
        """disconnect instruments (if any) and shutdown daemon request loop if remote"""
        self.save()

        for resource in self._services.values():
            if isinstance(resource, Instrument):
                try:
                    resource.disconnect()
                except ConnectionError:
                    logger.warning(
                        f"Can't disconnect '{resource}' due to a connection error. "
                        f"Please check the physical connection and re-setup the stage."
                    )

        if self._daemon is not None:
            self._daemon.shutdown()

        logger.debug("Tore down the stage gracefully!")


class Stagehand:
    """client context manager"""

    def __init__(self, *configpaths: Path) -> None:
        """ """
        logger.debug("Initializing a stagehand...")

        self._stage = Stage(*configpaths)

        # attributes '_remote_stage' and '_proxies' are updated if remote stage exists
        self._proxies: list[pyro.Proxy] = []
        self._remote_stage: pyro.Proxy = pyro.Proxy(_STAGE_URI)

        try:
            for name, uri in self._remote_stage.services.items():
                proxy = pyro.Proxy(uri)
                self._proxies.append(proxy)
                setattr(self._stage, name, proxy)  # replace resource with proxy
                logger.info(
                    f"Set stage attribute '{name}' after finding a remote resource "
                    f"served at {uri}."
                )
        except Pyro5.errors.CommunicationError:
            message = (
                f"Did not find a remote stage at {_STAGE_URI}. "
                f"Please setup a remote stage if you want to use remote resources. "
                f"Use a Stage context manager if you want to only use local resources."
            )
            raise StagingError(message) from None

    @property
    def stage(self) -> Stage:
        """ """
        return self._stage

    def __enter__(self) -> Stage:
        """ """
        return self._stage

    def __exit__(self, exc_type, exc_value, exc_traceback) -> None:
        """ """
        self._stage.teardown()

        if self._remote_stage is not None:
            self._remote_stage.save()
            self._remote_stage._pyroRelease()

        for proxy in self._proxies:  # release proxies, if any
            proxy._pyroRelease()


def locate(source: Path) -> set[Resource]:
    """ "source" is a folder containing modules that contain all instantiable user-defined Resource subclasses. We find all resource classes defined in all modules in all subfolders of the source folder THAT ARE DESIGNATED PYTHON PACKAGES i.e. the folder has an __init__.py file. We return a set of resource classes.

    source must be Path object, strings will throw a TypeError
    """
    resources = set()
    for modfinder, modname, is_pkg in pkgutil.iter_modules([source]):
        if not is_pkg:  # we have found a module, let's find Resources defined in it
            modspec = modfinder.find_spec(modname)
            module = importlib.util.module_from_spec(modspec)
            modspec.loader.exec_module(module)  # for module namespace to be populated
            classes = inspect.getmembers(module, inspect.isclass)
            resources |= {cls for _, cls in classes if issubclass(cls, Resource)}
        else:  # we have found a subpackage, let's send it recursively to locate()
            resources |= locate(source / modname)
    return resources

def main() -> None:
    """ """
    # command line argument definition
    parser = argparse.ArgumentParser(description="Setup or Teardown a remote Stage")
    parser.add_argument(
        "--run",
        help="--run to setup & --no-run to teardown a remote stage",
        action=argparse.BooleanOptionalAction,
        required=True,
    )
    parser.add_argument(
        "configpaths",
        help="path(s) to yml config files to serve Resources from",
        nargs="*",
    )
    args = parser.parse_args()

    # command line argument handling
    if args.run:  # setup remote stage with resources from user supplied configpath(s)
        logger.info("Setting up a remote stage...")

        # extract configpaths from args
        configpaths = [Path(configpath) for configpath in args.configpaths]

    	# validate configpaths
        if not configpaths:
            raise StagingError(
                f"Failed to setup stage as no configpaths were provided. "
                f"Please provide at least one path to a yml config file and try again."
            )
        for path in configpaths:
            if path.suffix.lower() not in (".yml", ".yaml"):
                raise StagingError(
                    f"Unrecognized configpath '{path.name}'. "
                    f"Valid configs are YAML files with a '.yml' or '.yaml' extension."
                )
        logger.debug(f"Validated all {configpaths = }")

        # create pyro Daemon and register a remote stage
        daemon = pyro.Daemon(port=_PORT)
        stage = Stage(*configpaths, daemon=daemon)
        stage_uri = daemon.register(stage, objectId=_SERVERNAME)
        logger.info(f"Served a remote stage at '{stage_uri}'.")

        # start listening for requests
        with daemon:
            logger.info("Remote stage daemon is now listening for requests...")
            daemon.requestLoop()
            logger.info("Exited remote stage daemon request loop.")

    else:  # teardown remote stage
        logger.info("Tearing down remote stage at '{_STAGE_URI}', please wait ~2s...")
        try:
            with pyro.Proxy(_STAGE_URI) as remote_stage:
                remote_stage.teardown()
        except Pyro5.errors.CommunicationError:
            message = (f"No remote stage to teardown at {_STAGE_URI}. ")
            raise StagingError(message) from None
        else:
            time.sleep(2)

if __name__ == "__main__":
    main()

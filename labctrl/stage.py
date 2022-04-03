"""
This module contains methods and classes for 
    1. Locating resource classes in specified resources folder
    2. Loading / Dumping resource instances from / to yaml config files
"""

import argparse
import importlib.util
import inspect
from pathlib import Path
import pkgutil
import time

import Pyro5.api as pyro
import Pyro5.errors

from labctrl.parameter import Parameter
from labctrl.resource import Resource, Instrument
import labctrl.yamlizer as yml

_PORT = 9090  # port to bind a remote stage on (used to initialize Pyro Daemon)
_SERVERNAME = "STAGE"
# remote stage unique resource identifier (URI)
_STAGE_URI = f"PYRO:{_SERVERNAME}@localhost:{_PORT}"


class StagingError(Exception):
    """ """


@pyro.expose
class Stage:
    """server"""

    def __init__(self, *configpaths: Path, daemon: pyro.Daemon | None = None) -> None:
        """configpaths: path to YAML file containing Resource classes to be instantiated
        daemon: if not None, this stage will be a remote stage that serves the Resources in the configpath remotely with Pyro. you can send in multiple configpaths, the resources will be bundled up on the same stage."""

        # self._config and self._services will be updated by _setup()
        self._config = {}  # dict with key: configpath, value: list of Resources

        # if local, services is a dict with key: resource name, value: Resource object
        # if remote, it is a dict with key: resource name, value: remote resource URI
        self._services = {}

        self._setup(*configpaths)

        self._daemon = daemon
        if self._daemon is not None:
            self._serve()

    def _setup(self, *configpaths: Path) -> None:
        """ """
        num_resources = 0
        for configpath in configpaths:
            resources = yml.load(configpath)
            self._config[configpath] = resources
            num_resources += len(resources)

            for resource in resources:
                try:
                    self._services[resource.name] = resource
                except (TypeError, AttributeError):
                    message = (
                        f"A {resource = } in {configpath = } does not have a 'name'\n"
                        f"All resources must have a '.name' attribute to be staged"
                    )
                    raise StagingError(message) from None

        if num_resources != len(self._services):
            message = (
                f"Two or more resources in {configpaths = } share a name\n"
                f"All resources must have unique names to be staged"
            )
            raise StagingError(message)

    def _serve(self) -> None:
        """ """
        for name, resource in self._services.items():
            try:
                uri = self._daemon.register(resource, objectId=name)
            except (TypeError, AttributeError):
                message = (
                    f"Expect {daemon = } of type '{pyro.Daemon}', not {type(daemon)}"
                )
                raise StagingError(message) from None

            self._services[name] = uri
            print(f"served {resource = } at {uri}")

    def save(self) -> None:
        """save current state state to respective yaml configs"""
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
                    # TODO upgrade to logger warning
                    print(f"WARNING - can't disconnect {resource = }, connection error")

        if self._daemon is not None:
            self._daemon.shutdown()


class Stagehand:
    """client context manager"""

    def __init__(self, *configpaths: Path) -> None:
        """ """
        self._stage = Stage(*configpaths)
        # set resource names as stage attributes for easy access
        for name, resource in self._stage.services.items():
            setattr(self._stage, name, resource)

        # connect to remote stage, if available
        self._proxies: list[pyro.Proxy] = []
        try:
            with pyro.Proxy(_STAGE_URI) as remote_stage:
                for name, uri in remote_stage.services.items():
                    print(f"found remote resource with {name = } at {uri}")
                    proxy = pyro.Proxy(uri)
                    self._proxies.append(proxy)
                    setattr(self._stage, name, proxy)
                    print(f"set stage attribute '{name}'")
        except Pyro5.errors.CommunicationError:
            # TODO warn user that no remote stageg could be found
            print("No remote stage found!")

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

        # release proxies, if any
        for proxy in self._proxies:
            proxy._pyroRelease()


def locate(source: Path) -> set[Resource]:
    """ "source" is a folder containing modules that contain all instantiable user-defined Resource subclasses. We find all resource classes defined in all modules in all subfolders of the source folder THAT ARE DESIGNATED PYTHON PACKAGES i.e. the folder has an __init__.py file. We return a set of resource classes.

    source must be Path object, strings will throw a TypeError

    TODO - error handling
    message = (f"Can't load resource package folder '{source.stem}' at {source}. "
                   f"Did you forget to place an empty __init__.py file in that folder?")
    raise StagingError(message)

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


def validate(configpaths: list[Path]) -> None:
    """ """
    if not configpaths:
        raise StagingError(
            f"Failed to setup stage as no configpaths were provided. "
            f"Please provide at least one path to a yml config file and try again."
        )
    for path in configpaths:
        if path.suffix not in (".yml", ".yaml"):
            raise StagingError(
                f"Unrecognized configpath '{path.name}'. "
                f"Valid configs are YAML files with a '.yml' or '.yaml' extension."
            )
    print("configpath(s) have been validated")


if __name__ == "__main__":

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

    if args.run:  # setup remote stage with resources from the user supplied configpaths
        print("setting up remote stage...")

        # extract configpaths from args
        configpaths = [Path(configpath) for configpath in args.configpaths]
        validate(configpaths)

        settings = yml.load(Path.cwd().parent / "settings.yml")
        resourcepath = Path(settings["resourcepath"])

        # expose resource classes with Pyro
        pyro.expose(Parameter)
        resource_classes = locate(resourcepath)
        for resource_class in resource_classes:
            pyro.expose(resource_class)
            yml.register(resource_class)
        print(f"sucessfully registered {resource_classes = }")

        # create pyro Daemon and register a remote stage
        daemon = pyro.Daemon(port=_PORT)
        stage = Stage(*configpaths, daemon=daemon)
        stage_uri = daemon.register(stage, objectId=_SERVERNAME)
        print(f"served remote stage at {stage_uri}")

        # start listening for requests
        with daemon:
            print("remote stage setup complete! now listening for requests...")
            daemon.requestLoop()
            print("exited remote stage daemon request loop")

    else:  # teardown remote stage
        print("tearing down remote stage, no action needed, just wait ~3 seconds...")
        with pyro.Proxy(_STAGE_URI) as remote_stage:
            remote_stage.teardown()
        time.sleep(3)

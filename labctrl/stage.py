"""
This module contains methods and classes for 
    1. Locating resource classes in specified resources folder
    2. Loading / Dumping resource instances from / to yaml config files
"""

import importlib.util
import inspect
from pathlib import Path
import pkgutil

import yaml

from labctrl.resource import Resource, Instrument


class StagingError(Exception):
    """ """


def _is_resource(cls) -> bool:
    """new resource is found when a class subclasses Resource but is not Resource or Instrument. to be extended to include Experiment classes..."""
    return issubclass(cls, Resource) and cls not in (Resource, Instrument)


def locate(source: Path) -> set[Resource]:
    """ "source" is a folder containing modules that contain all instantiable user-defined Resource subclasses. We find all resource classes defined in all modules in all subfolders of the source folder THAT ARE DESIGNATED PYTHON PACKAGES i.e. the folder has an __init__.py file. We return a set of resource classes.

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
            resources |= {cls for _, cls in classes if _is_resource(cls)}
        else:  # we have found a subpackage, let's send it recursively to locate() 
            resources |= locate(source / modname)
    return resources


def load(configpath: Path) -> list:
    """returns a list of resource objects by reading a YAML file e.g. Instruments"""
    try:
        with open(configpath, mode="r") as config:
            return yaml.safe_load(config)
    except AttributeError:
        message = (
            f"Failed to load a labctrl resource from {configpath}\n"
            f"An entry in {configpath.name} may have an invalid attribute (key)"
        )
    except yaml.YAMLError:
        message = (
            f"Failed to identify and load labctrl resources from {configpath}\n"
            f"{configpath.name} may have an invalid or unrecognized yaml tag"
        )
        raise StagingError(message) from None


if __name__ == "__main__":
    resource_path = Path.cwd() / "resources"
    resource_classes = locate(resource_path)
    print(f"Found {len(resource_classes)} {resource_classes = }")

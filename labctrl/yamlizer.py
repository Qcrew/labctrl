# -*- coding: utf-8 -*-
"""This module contains utilities that perform resource class registration, dumping and
loading.

Resource classes can be registered with yamlizer to allow their instances to be
loaded from (dumped to) yaml files without changing the class inheritance structure."""

from pathlib import Path
from typing import Any, Type

import numpy as np
import yaml

from labctrl.resource import Resource


class YamlRegistrationError(Exception):
    """Raised if the user tries to register a non-class object with yamlizer."""


class YamlizationError(Exception):
    """Raised if a resource object cannot be dumped to or loaded from a given path to a yaml config file"""


class _YamlRegistrar:
    """Internal class to keep track of classes registered with yamlizer in a single
    Python process."""

    def __init__(self) -> None:
        """ """
        self._register: dict[str, Type[Any]] = {}


_REGISTRAR = _YamlRegistrar()


def _sci_notation_representer(dumper, value) -> yaml.ScalarNode:
    """custom representer for converting floating point types to scientific notation if their absolute value is greater than an arbitrarily set threshold of 1e3"""
    threshold = 1e3  # based on the feeling that values > 1e3 are better read in sci not
    yaml_float_tag = "tag:yaml.org,2002:float"
    value_in_sci_not = f"{value:E}" if abs(value) >= threshold else str(value)
    return dumper.represent_scalar(yaml_float_tag, value_in_sci_not)


def register(cls: Type[Resource]) -> None:
    """Registers a Resource class with yamlizer for safe loading (dumping).

    Args:
        cls (Type[Any]): Custom Python class to be registered with yamlizer.

    Raises:
        YamlRegistrationError: If `cls` is not a Python class."""

    if not issubclass(cls, Resource):
        raise YamlRegistrationError(f"Only Resource(s) can be registered, not {cls}")

    yamltag = cls.__name__

    yaml.SafeLoader.add_constructor(yamltag, _construct)
    yaml.SafeDumper.add_representer(cls, _represent)

    # customise dumper to represent float values in scientific notation
    yaml.SafeDumper.add_representer(float, _sci_notation_representer)
    yaml.SafeDumper.add_multi_representer(np.floating, _sci_notation_representer)

    _REGISTRAR._register[yamltag] = cls


def _construct(loader: yaml.SafeLoader, node: yaml.MappingNode) -> Resource:
    """Constructor for classes registered with yamlizer.

    Args:
        loader (yaml.SafeLoader): PyYAML's `SafeLoader`.
        node (yaml.MappingNode): Yaml map for initializing an instance of a registered
        custom class.

    Raises:
        YamlizationError: If an object cannot be instantiated with the loaded yaml map.

    Returns:
        Any: Initialized instance of the custom class."""

    yamlmap = loader.construct_mapping(node, deep=True)
    cls = _REGISTRAR._register[node.tag]
    return cls(**yamlmap)


def _represent(dumper: yaml.SafeDumper, resource: Resource) -> yaml.MappingNode:
    """Representer for classes registered with yamlizer.

    Args:
        dumper (yaml.SafeDumper): PyYAML's `SafeDumper`.
        yamlizable (Any): Instance of a registered custom class to be dumped to yaml.

    Returns:
        yaml.MappingNode: Yaml map representation of the given custom instance."""
    yamltag = resource.__class__.__name__
    yamlmap = resource.snapshot()
    return dumper.represent_mapping(yamltag, yamlmap)


def load(configpath: Path) -> list[Resource]:
    """returns a list of resource objects by reading a YAML file e.g. Instruments"""
    try:
        with open(configpath, mode="r") as config:
            return yaml.safe_load(config)
    except IOError:
        message = (
            f"Unable to find and load from a file at {configpath = }\n"
            f"You may have specified an invalid path"
        )
        raise YamlizationError(message) from None
    except AttributeError:
        message = (
            f"Failed to load a labctrl resource from {configpath}\n"
            f"An entry in {configpath.name} may have an invalid attribute (key)"
        )
        raise YamlizationError(message) from None
    except yaml.YAMLError:
        message = (
            f"Failed to identify and load labctrl resources from {configpath}\n"
            f"{configpath.name} may have an invalid or unrecognized yaml tag"
        )
        raise YamlizationError(message) from None


def dump(configpath: Path, *resources: Resource) -> None:
    """ """
    try:
        with open(configpath, mode="w+") as config:
            yaml.safe_dump(resources, config)
    except IOError:
        message = (
            f"Unable to find and save to a file at {configpath = }\n"
            f"You may have specified an invalid path"
        )
        raise YamlizationError(message) from None
    except yaml.YAMLError:
        message = (
            f"Failed to save labctrl resources to {configpath}\n"
            f"You may have supplied an invalid or unrecognized Resource class"
        )
        raise YamlizationError(message) from None

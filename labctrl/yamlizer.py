# -*- coding: utf-8 -*-
"""This module contains utilities that perform custom object registration, dumping and
loading.

Custom object classes can be registered with yamlizer to allow their instances to be
loaded from (dumped to) yaml files without having the class inherit `Yamlizable`."""

import inspect
from pathlib import Path
from typing import Any, Type

import yaml

from . import yamlmapper


class YamlRegistrationError(Exception):
    """Raised if the user tries to register a non-class object with yamlizer."""


class YamlizationError(Exception):
    """Raised if a custom object cannot be instantiated with the yaml map loaded from a
    yaml file due to an incompatibility between the keys in the yaml map and the names
    of the keyword arguments in the object's __init__()."""


class _YamlRegistrar:
    """Internal class to keep track of classes registered with yamlizer in a single
    Python process."""

    def __init__(self) -> None:
        self.register: dict[str, Type[Any]] = {}


_REGISTRAR = _YamlRegistrar()


def register(cls: Type[Any]) -> None:
    """Registers a custom Python class with yamlizer for safe loading (dumping).

    Args:
        cls (Type[Any]): Custom Python class to be registered with yamlizer.

    Raises:
        YamlRegistrationError: If `cls` is not a Python class."""
    if not inspect.isclass(cls):
        raise YamlRegistrationError("Only Python class(es) can be registered")
    yaml_tag = cls.__name__
    yaml.SafeDumper.add_representer(cls, _represent)
    yaml.SafeLoader.add_constructor(yaml_tag, _construct)
    _REGISTRAR.register[yaml_tag] = cls


def _represent(dumper: yaml.SafeDumper, yamlizable: Any) -> yaml.MappingNode:
    """Representer for classes registered with yamlizer.

    Args:
        dumper (yaml.SafeDumper): PyYAML's `SafeDumper`.
        yamlizable (Any): Instance of a registered custom class to be dumped to yaml.

    Returns:
        yaml.MappingNode: Yaml map representation of the given custom instance."""
    yaml_tag = yamlizable.__class__.__name__
    yaml_map = yamlmapper.yaml_map(yamlizable)
    return dumper.represent_mapping(yaml_tag, yaml_map)


def _construct(loader: yaml.SafeLoader, node: yaml.MappingNode) -> Any:
    """Constructor for classes registered with yamlizer.

    Args:
        loader (yaml.SafeLoader): PyYAML's `SafeLoader`.
        node (yaml.MappingNode): Yaml map for initializing an instance of a registered
        custom class.

    Raises:
        YamlizationError: If an object cannot be instantiated with the loaded yaml map.

    Returns:
        Any: Initialized instance of the custom class."""
    kwargs = loader.construct_mapping(node, deep=True)
    cls = _REGISTRAR.register[node.tag]
    try:
        return cls(**kwargs)
    except TypeError:
        raise YamlizationError(f"Yaml map incompatible with {cls} init()") from None


def dump(config: Any, configpath: Path, mode: str = "w+") -> None:
    """Dumps a given configuration of yamlizable instances to the given configpath.

    The configuration may be a single yamlizable or a sequence (list) or mapping (dict)
    of objects that are either registered with yamlizer or natively recognized as safe
    by PyYAML.

    Args:
        config (Any): Yamlizable instances to be dumped to a yaml file.
        configpath (Path): Path to the yaml file to dump the config to.
        mode (str, optional): Yaml file access mode. Defaults to "w+".
    """
    with open(configpath, mode=mode) as configfile:
        yaml.safe_dump(config, configfile)


def load(configpath: Path) -> Any:
    """Loads a given configuration of yamlizable instances from the given configpath.

    The configuration may be a single yamlizable or a sequence (list) or mapping (dict)
    of objects that are either registered with yamlizer or natively recognized as safe
    by PyYAML.

    Args:
        configpath (Path): Path to the yaml file to load the yamlizable instances from.

    Returns:
        Any: Configuration of yamlizable instances.
    """
    with open(configpath, mode="r") as configfile:
        return yaml.safe_load(configfile)

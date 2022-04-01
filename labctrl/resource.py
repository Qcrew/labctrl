""" A resource is the encapsulation of objects used in measurements - an instrument, a sample """

from __future__ import annotations

from typing import Any

import yaml

from labctrl.parameter import Parameter, parametrize


class ResourceMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)

        cls._params = parametrize(cls)  # key: parameter name, value: Parameter object
        cls._defaults = {k: v.default for k, v in cls._params.items() if v.has_default}
        cls._gettables = {k for k, v in cls._params.items() if v.is_gettable}
        cls._settables = {k for k, v in cls._params.items() if v.is_settable}

        yaml.SafeDumper.add_representer(cls, cls.dump)
        yaml.SafeLoader.add_constructor(name, cls.load)

    def __repr__(cls) -> str:
        """ """
        return f"<class '{cls.__name__}'>"


class Resource(metaclass=ResourceMetaclass):
    """ """

    name = Parameter()

    def __init__(self, name: str, **parameters) -> None:
        """ """
        self._name = str(name)
        # set parameters with default values (if present) if not supplied by the user
        self.configure(**{**self.__class__._defaults, **parameters})

    def __repr__(self) -> str:
        """ """
        return f"{self.__class__.__name__} '{self._name}'"

    @name.getter
    def name(self) -> str:
        """ """
        return self._name

    def configure(self, **parameters) -> None:
        """ """
        for name, value in parameters.items():
            if name in self.__class__._settables:
                setattr(self, name, value)

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self.__class__._gettables}

    @classmethod
    def dump(cls, dumper: yaml.SafeDumper, resource: Resource) -> yaml.MappingNode:
        """ """
        yamltag = cls.__name__
        return dumper.represent_mapping(yamltag, resource.snapshot())

    @classmethod
    def load(cls, loader: yaml.SafeLoader, node: yaml.MappingNode):
        """ """
        yamlmap = loader.construct_mapping(node, deep=True)
        return cls(**yamlmap)


class ConnectionError(Exception):
    """ """


class Instrument(Resource):
    """ """

    id = Parameter()

    def __init__(self, id: Any, **parameters) -> None:
        """ """
        self._id = id
        self.connect()
        super().__init(**parameters)

    def __repr__(self) -> str:
        """ """
        return f"{self.__class__.__name__} #{self._id}"

    @id.getter
    def id(self) -> Any:
        """ """
        return self._id

    @property
    def status(self) -> bool:
        """ """
        raise NotImplementedError("Instrument subclasses must implement `status`")

    def connect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement `connect()`")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement `disconnect()`")

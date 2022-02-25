""" """

from __future__ import annotations

from typing import Any

import yaml

from labctrl.parameter import parametrize


class ConnectionError(Exception):
    """ """


class InstrumentMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)
        _paramdict = parametrize(cls)  # key: parameter name, value: Parameter object
        cls._parameters = sorted(_paramdict.keys())
        cls._gettables = {k for k, v in _paramdict.items() if v.is_gettable}
        cls._settables = {k for k, v in _paramdict.items() if v.is_settable}
        yaml.SafeDumper.add_representer(cls, cls.dump)
        yaml.SafeLoader.add_constructor(name, cls.load)

    def __repr__(cls) -> str:
        """ """
        return f"<class '{cls.__name__}>"


class Instrument(metaclass=InstrumentMetaclass):
    """ """

    def __init__(self, name: str, id: Any, **parameters) -> None:
        """ """
        self._name = str(name)
        self._id = id
        self.connect()
        self.configure(**parameters)

    def __repr__(self) -> str:
        """ """
        return f"{self._name}-{self._id}"

    @property
    def parameters(self) -> list[str]:
        """ """
        return self.__class__._parameters

    @property
    def name(self) -> str:
        """ """
        return self._name

    @property
    def id(self) -> Any:
        """ """
        return self._id

    @property
    def status(self) -> bool:
        """ """
        raise NotImplementedError("subclasses must implement `status`")

    def connect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement `connect()`")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement `disconnect()`")

    def configure(self, **parameters) -> None:
        """ """
        settables = self.__class__._settables
        for name, value in parameters.items():
            if name not in settables:
                raise AttributeError(f"Can't set '{name}' as {self} has {settables = }")
            setattr(self, name, value)

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self.__class__._gettables}

    @classmethod
    def dump(cls, dumper: yaml.SafeDumper, instrument: Instrument) -> yaml.MappingNode:
        """ """
        yamltag = cls.__name__
        yamlkeys = ["name", "id", *sorted(cls._gettables & cls._settables)]
        yamlmap = {key: getattr(instrument, key) for key in yamlkeys}
        print(yamlmap)
        return dumper.represent_mapping(yamltag, yamlmap)

    @classmethod
    def load(cls, loader: yaml.SafeLoader, node: yaml.MappingNode):
        """ """
        yamlmap = loader.construct_mapping(node, deep=True)
        return cls(**yamlmap)

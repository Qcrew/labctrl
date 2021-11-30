""" """

from __future__ import annotations

from typing import Any

import yaml

from labctrl.parameter import Parameter, parametrize, NotSettableError


class InstrumentMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)
        cls._parameters = parametrize(cls)
        cls._gettables = sorted(k for k, v in cls._parameters.items() if v.is_gettable)
        cls._settables = sorted(k for k, v in cls._parameters.items() if v.is_settable)
        yaml.SafeDumper.add_representer(cls, cls.dump)
        yaml.SafeLoader.add_constructor(name, cls.load)

    def __repr__(cls) -> str:
        """ """
        return f"<class '{cls.__name__}>"


class Instrument(metaclass=InstrumentMetaclass):
    """ """

    name = Parameter()
    id = Parameter()

    def __init__(self, name: str, id: Any, **parameters) -> None:
        """ """
        self._name = str(name)
        self._id = id
        self._handle = None  # to be updated by connect()
        self.connect()
        self.configure(**parameters)

    def __repr__(self) -> str:
        """ """
        return f"{self._name}-{self._id}"

    @property
    def parameters(self) -> list[str]:
        """ """
        return sorted(self.__class__._parameters.keys())

    @name.getter
    def name(self) -> str:
        """ """
        return self._name

    @id.getter
    def id(self) -> Any:
        """ """
        return self._id

    def connect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement connect()")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement disconnect()")

    def configure(self, **parameters) -> None:
        """ """
        settables = self.__class__._settables
        for name, value in parameters.items():
            if name not in settables:
                raise NotSettableError(f"Can't set '{name}'; {self} has {settables = }")
            setattr(self, name, value)

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self.__class__._gettables}

    @classmethod
    def dump(cls, dumper: yaml.SafeDumper, instrument: Instrument) -> yaml.MappingNode:
        """ """
        yamltag = instrument.__class__.__name__
        yamlmap = instrument.snapshot()
        return dumper.represent_mapping(yamltag, yamlmap)

    @classmethod
    def load(cls, loader: yaml.SafeLoader, node: yaml.MappingNode):
        """ """
        yamlmap = loader.construct_mapping(node, deep=True)
        return cls(**yamlmap)

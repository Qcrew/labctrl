""" """

import ctypes
import inspect
from pathlib import Path
from typing import Any

import pyvisa
import yaml

from labctrl.parametrizer import Param, parametrize


class InstrumentConnectionError(Exception):
    """ """


class InstrumentMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        super().__init__(name, bases, kwds)
        cls._params: list[str] = parametrize(cls)
        yaml.SafeDumper.add_representer(cls, cls.dump)
        yaml.SafeLoader.add_constructor(name, cls.load)

    def __repr__(cls) -> str:
        return f"<class '{cls.__name__}>"

    @property
    def params(cls) -> list[str]:
        """ """
        return cls._params


class Instrument(metaclass=InstrumentMetaclass):
    """ """

    name = Param(bounds=str, setter=False)
    id = Param(setter=False)

    def __init__(self, name: str, id: Any) -> None:
        """ """
        self.name = name
        self.id = id

    def __repr__(self) -> str:
        """ """
        return f"{self.name}-{self.id}"

    def connect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement connect()")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement disconnect()")

    def configure(self, **params) -> None:
        """ """
        for name, value in params.items():
            if name not in self.params:
                message = f"'{name}' is not a param of {self}: {self.params}"
                raise AttributeError(message)
            setattr(self, name, value)

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self.params}

    @classmethod
    def dump(cls, dumper: yaml.SafeDumper, instrument) -> yaml.MappingNode:
        """ """
        yamltag = instrument.__class__.__name__
        yamlmap = instrument.snapshot()
        return dumper.represent_mapping(yamltag, yamlmap)

    @classmethod
    def load(cls, loader: yaml.SafeLoader, node: yaml.MappingNode):
        """ """
        params = loader.construct_mapping(node, deep=True)
        return cls(**params)


class DLLInstrument(Instrument):
    """ """

    def __init__(self, name: str, id: Any, **params) -> None:
        """ """
        super().__init__(name, id)
        # TODO error handling, outsource to _locatedll() method
        modulepath = Path(inspect.getsourcefile(self.__class__))
        handlepath = modulepath.parent / f"{modulepath.stem}.dll"
        self._handle = ctypes.CDLL(str(handlepath))
        self._pointer = self.connect()
        self.configure(**params)

    @property
    def handle(self) -> tuple[Any]:
        """ """
        return self._handle, self._pointer


class VISAInstrument(Instrument):
    """ """

    id = Param(bounds=str, setter=False)

    def __init__(self, name: str, id: Any, **params) -> None:
        """ """
        super().__init__(name, id)
        self._handle = self.connect()
        self.configure(**params)

    @property
    def handle(self) -> tuple[Any]:
        """ """
        return self._handle

    def connect(self) -> None:
        """ """  # TODO error handling
        return pyvisa.ResourceManager().open_resource(self.id)

    def disconnect(self) -> None:
        """ """
        self._handle.close()

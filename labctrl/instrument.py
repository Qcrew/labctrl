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

    @property
    def handle(self) -> Any:
        """ """
        raise NotImplementedError("subclasses must assign handle")

    def connect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement connect()")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("subclasses must implement disconnect()")

    def communicate(self, command: str, value: Any) -> Any:
        """ """
        raise NotImplementedError("subclasses must implement communicate()")

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
        self._driver = self._locatedll()
        self._pointer = self.connect()
        self.configure(**params)

    def _locatedll(self) -> ctypes.CDLL:
        """ """
        modulepath = Path(inspect.getsourcefile(self.__class__))
        driverpath = (path := modulepath.parent) / (dllname := f"{modulepath.stem}.dll")
        if not driverpath.exists():
            message = f"driver named '{dllname}' does not exist in {path = }"
            raise InstrumentConnectionError(message)
        try:
            return ctypes.CDLL(str(driverpath))
        except OSError:
            message = f"some dependent dll(s) of '{dllname}' were not found"
            raise InstrumentConnectionError(message) from None

    @property
    def handle(self) -> tuple[Any]:
        """ """
        return self._driver, self._pointer

    def communicate(self, command: str, value: Any = None):
        """ """
        if value is None:  # command gets param value from the instrument
            return getattr(self._driver, command)(self._pointer)
        # command sets param value on the instrument
        return getattr(self._driver, command)(self._pointer, value)


class VISAInstrument(Instrument):
    """ """

    id = Param(bounds=str, setter=False)

    def __init__(self, name: str, id: Any, **params) -> None:
        """ """
        super().__init__(name, id)
        self._driver = self.connect()
        self.configure(**params)

    @property
    def handle(self) -> tuple[Any]:
        """ """
        return self._driver

    def connect(self) -> None:
        """ """  # TODO error handling
        return pyvisa.ResourceManager().open_resource(self.id)

    def disconnect(self) -> None:
        """ """
        self._driver.close()

    def communicate(self, command: str, value: Any = None):
        """ """
        if value is None:  # command gets param value from the instrument
            return self._driver.query(f"{command}?")
        # command sets param value on the instrument
        return self._driver.write(f"{command} {value}")

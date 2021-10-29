""" """

from typing import Any

import yaml

from parameter import Parameter, parametrize


class InstrumentMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        super().__init__(name, bases, kwds)
        yaml.SafeDumper.add_representer(cls, cls.dump)
        yaml.SafeLoader.add_constructor(name, cls.load)

    def __repr__(cls) -> str:
        return f"<class '{cls.__name__}>"


class Instrument(metaclass=InstrumentMetaclass):
    """ """

    name: str = Parameter(setter=False)
    id: Any = Parameter(setter=False)

    def __init__(self, name: str, id: Any, **parameters) -> None:
        """ """
        self._parameters: set[str] = parametrize(self.__class__)
        self.name = name
        self.id = id
        self._handle = self.connect()
        if parameters:
            self.configure(**parameters)

    def __repr__(self) -> str:
        """ """
        return f"{self.name}-{self.id}"

    @property
    def handle(self) -> Any:
        """ """
        return self._handle

    @property
    def parameters(self) -> set[str]:
        """ """
        return self._parameters

    def connect(self) -> Any:
        """ """
        raise NotImplementedError("Instrument subclasses must implement connect()")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement disconnect()")

    def configure(self, **parameters) -> None:
        """ """
        for name, value in parameters.items():
            if name not in self._parameters:
                message = f"'{name}' is not a parameter of {self}: {self._parameters}"
                raise AttributeError(message)
            setattr(self, name, value)

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self._parameters}

    @classmethod
    def dump(cls, dumper: yaml.SafeDumper, instrument) -> yaml.MappingNode:
        """ """
        yaml_tag = instrument.__class__.__name__
        yaml_map = instrument.snapshot()
        return dumper.represent_mapping(yaml_tag, yaml_map)

    @classmethod
    def load(cls, loader: yaml.SafeLoader, node: yaml.MappingNode):
        """ """
        parameters = loader.construct_mapping(node, deep=True)
        return cls(**parameters)

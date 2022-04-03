""" A resource is the encapsulation of objects used in measurements - an instrument, a sample """

from __future__ import annotations

from typing import Any

import numpy as np

from labctrl.parameter import Parameter, parametrize


class ConnectionError(Exception):
    """ """


class ResourceMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)

        cls._params = parametrize(cls)  # key: parameter name, value: Parameter object
        cls._defaults = {k: v.default for k, v in cls._params.items() if v.has_default}
        cls._gettables = {k for k, v in cls._params.items() if v.is_gettable}
        cls._settables = {k for k, v in cls._params.items() if v.is_settable}

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
            # TODO else raise warning logger

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in self.__class__._gettables}


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

    def configure(self, **parameters) -> None:
        """ """
        if not self.status:
            message = (
                f"{self} cannot be configured as it has disconnected\n"
                f"Please check the physical connection and try to reconnect"
            )
            raise ConnectionError(message)
        super().configure(**parameters)

    def snapshot(self) -> dict[str, Any]:
        """ """
        if not self.status:
            # TODO upgrade to logger warning
            print(f"WARNING: {self} has disconnected, returning minimal snapshot")
            return {"name": self.name, "id": self.id}
        super().snapshot()

    def connect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement `connect()`")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("Instrument subclasses must implement `disconnect()`")

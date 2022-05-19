""" A resource is the encapsulation of objects used in measurements - an instrument, a sample """

from __future__ import annotations

from typing import Any

from labctrl.logger import logger
from labctrl.parameter import Parameter, parametrize


class ConnectionError(Exception):
    """ """


class ResourceMetaclass(type):
    """ """

    def __init__(cls, name, bases, kwds) -> None:
        """ """
        super().__init__(name, bases, kwds)

        cls.paramspec: dict[str, Parameter] = parametrize(cls)
        cls.defaults = {k: v.default for k, v in cls.paramspec.items() if v.has_default}
        cls.gettables = {k for k, v in cls.paramspec.items() if v.is_gettable}
        cls.settables = {k for k, v in cls.paramspec.items() if v.is_settable}

    def __repr__(cls) -> str:
        """ """
        return f"<class '{cls.__name__}'>"


class Resource(metaclass=ResourceMetaclass):
    """ """

    name = Parameter()

    def __init__(self, name: str, **parameters) -> None:
        """ """
        self._name = str(name)
        logger.debug(f"Initialized {self}.")
        # set parameters with default values (if present) if not supplied by the user
        self.configure(**{**self.__class__.defaults, **parameters})

    def __repr__(self) -> str:
        """ """
        return f"{self.__class__.__name__} '{self._name}'"

    @name.getter
    def name(self) -> str:
        """ """
        return self._name

    @property
    def parameters(self) -> list[str]:
        """ """
        return [repr(parameter) for parameter in self.__class__.paramspec.values()]

    def configure(self, **parameters) -> None:
        """ """
        for name, value in parameters.items():
            if name in self.__class__.settables:
                setattr(self, name, value)
                logger.debug(f"Set {self} '{name}' = {value}.")

    def snapshot(self) -> dict[str, Any]:
        """ """
        return {name: getattr(self, name) for name in sorted(self.__class__.gettables)}


class Instrument(Resource):
    """ """

    id = Parameter()

    def __init__(self, id: Any, **parameters) -> None:
        """ """
        self._id = id
        self.connect()
        super().__init__(**parameters)

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
        raise NotImplementedError("Subclasses must implement 'status'.")

    def configure(self, **parameters) -> None:
        """ """
        if not self.status:
            message = (
                f"Unable to configure {self} as it has disconnected. "
                f"Please check the physical connection and try to reconnect."
            )
            logger.error(message)
            raise ConnectionError(message)

        super().configure(**parameters)

    def snapshot(self) -> dict[str, Any]:
        """ """
        if not self.status:
            message = (
                f"Returning a minimal snapshot as {self} has disconnected. "
                f"Please check the physical connection and try to reconnect."
                )
            logger.error(message)
            return {"id": self.id, "name": self.name}

        return super().snapshot()

    def connect(self) -> None:
        """ """
        raise NotImplementedError("Subclasses must implement 'connect()'.")

    def disconnect(self) -> None:
        """ """
        raise NotImplementedError("Subclasses must implement 'disconnect()'.")

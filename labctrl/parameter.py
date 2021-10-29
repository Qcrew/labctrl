""" """

import inspect
from typing import Any, Callable, Type, Union

import numpy as np


class ParameterGetterError(Exception):
    """ """


class ParameterSetterError(Exception):
    """ """


class ParameterConversionError(Exception):
    """ """


class BoundsParsingError(Exception):
    """ """


class ParameterOutOfBoundsError(Exception):
    """ """


class Parameter:
    """ """

    def __init__(
        self,
        bounds: Union[Callable[[Any], bool], tuple, set] = None,
        getter: Union[Callable[[Any], Any], bool, str] = True,
        setter: Union[Callable[[Any, Any], None], bool, str] = True,
        parser: Callable[[Any], Any] = None,
    ) -> None:
        """ """
        self._name = None  # updated by __set_name__()
        self._bounds = bounds
        self._bound = self._get_bound(bounds)
        self._getter = self._get_getter(getter)
        self._setter = self._get_setter(setter, getter)
        self._parser = parser

    def __repr__(self) -> str:
        name, bounds = self._name, self._bounds
        return f"{self.__class__.__name__}({name = }, {bounds = })"

    def __set_name__(self, cls: Type[Any], name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, cls: Type[Any] = None) -> object:
        if obj is None:
            return self

        if self._getter is None:  # parameter is not gettable
            raise ParameterGetterError(f"'{self._name}' is not gettable")

        try:
            value = self._getter(obj)
            parsed_value = self._parse(value)  # cast value if specified
            if not self._bound(parsed_value):  # check value bounds
                msg = f"Got bad {self._name} value = {parsed_value}"
                raise ParameterOutOfBoundsError(msg)
            return parsed_value
        except TypeError:
            raise ParameterGetterError(f"Invalid getter: {self._getter}") from None

    def __set__(self, obj: Any, value: Any) -> None:
        parsed_value = self._parse(value)  # cast value if specified

        if not self._bound(parsed_value):  # check value bounds
            msg = f"{self._name} out of bounds = {self._bounds}"
            raise ParameterOutOfBoundsError(msg)

        if self._setter is None:  # parameter is only settable once
            if f"_{self._name}" in obj.__dict__:
                raise ParameterSetterError(f"'{self._name}' is not settable")
            self._set(obj, parsed_value)
        else:
            try:
                self._setter(obj, parsed_value)
            except TypeError:
                raise ParameterSetterError(f"Invalid setter: {self._setter}") from None

    def _get_bound(self, bounds) -> Callable[[Any], bool]:
        """ """
        if callable(bounds):  # custom function to check parameter bounds
            return bounds
        elif bounds is None:  # unbounded parameter
            return lambda x: True
        elif isinstance(bounds, set):  # discrete parameter bounded by a set of values
            return lambda x: x in bounds
        elif isinstance(bounds, list):  # continuous parameter
            if len(bounds) == 2:  # bounded by [min, max]
                min, max = (*bounds,)
                return lambda x: min <= x <= max
            elif len(bounds) == 3:  # bounded by [start, stop] and incremented in steps
                start, stop, step = (*bounds,)
                interval = np.arange(start, stop + step / 2, step)
                return lambda x: x in interval
        elif isinstance(bounds, tuple):  # hybrid (both discrete & continuous) parameter
            predicates = (self._get_bounds(bound) for bound in bounds)
            return lambda x: all((predicate(x) for predicate in predicates))
        else:
            raise BoundsParsingError(f"Invalid specification of {bounds = }")

    def _get_getter(
        self, getter: Union[Callable[[Any], Any], bool, str]
    ) -> Callable[[Any], Any]:
        """ """
        if getter is False:
            return None
        elif getter is True:
            return self._default_getter
        elif isinstance(getter, str):
            return lambda obj: obj._handle.query(f"{getter}?")
        else:
            return lambda obj: getter(obj._handle)

    def _default_getter(self, obj: Any) -> Any:
        """ """
        try:
            return getattr(obj, f"_{self._name}")
        except AttributeError:
            raise ParameterGetterError(f"'{self._name}' is not set yet") from None

    def _get_setter(
        self,
        setter: Union[Callable[[Any, Any], None], bool, str],
        getter: Union[Callable[[Any, Any], None], bool, str],
    ) -> Callable[[Any, Any], None]:
        """ """
        if setter is False:
            return None
        elif setter is True:
            if isinstance(getter, str):
                return lambda obj, value: obj._handle.write(f"{getter} {value}")
            return self._default_setter
        else:
            return lambda obj, value: setter(obj._handle, value)

    def _default_setter(self, obj: Any, value: Any) -> None:
        """ """
        setattr(obj, f"_{self._name}", value)

    def _parse(self, value: Any) -> Any:
        """ """
        if self._parser is not None:
            try:
                return self._parser(value)
            except TypeError:
                msg = f"Invalid parser '{self._parser}' for {value = }"
                raise ParameterConversionError(msg)
            except ValueError:
                msg = f"Invalid {value = } for parser '{self._parser}'"
                raise ParameterConversionError(msg)
        return value


def parametrize(cls: Type[Any]) -> set[str]:
    """Finds the names of Parameters of a class hierachy"""
    if not inspect.isclass(cls):
        raise ValueError("Only python classes can be parametrized")
    mro = inspect.getmro(cls)
    return {k for c in mro for k, v in c.__dict__.items() if isinstance(v, Parameter)}

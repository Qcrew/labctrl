""" """

import inspect
from typing import Any, Callable, Type, Union

import numpy as np


class ParamGetterError(Exception):
    """ """


class ParamSetterError(Exception):
    """ """


class ParamConversionError(Exception):
    """ """


class BoundsParsingError(Exception):
    """ """


class ParamOutOfBoundsError(Exception):
    """ """


class Bounds:
    """ """

    def __init__(self, boundspec) -> None:
        """ """
        try:
            self._predicate, self._stringrep = self._parse(boundspec)
        except (TypeError, RecursionError) as e:
            message = f"{e} due to invalid bound specification {boundspec}"
            raise BoundsParsingError(message) from None

    def _parse(self, boundspec):
        """ """
        predicate, stringrep = None, str(boundspec)  # default case
        is_nested = lambda: any(isinstance(spec, list) for spec in boundspec)

        # unbounded Param
        if boundspec is None:
            predicate = lambda *_: True
        # Param with numeric values in an interval
        elif isinstance(boundspec, (list, tuple)) and not is_nested():
            # continuous value in closed interval [min, max]
            if len(boundspec) == 2:
                min, max = boundspec
                predicate = lambda value, _: min <= value <= max
            # linearly spaced values in closed interval [start, stop, step]
            elif len(boundspec) == 3:
                start, stop, step = boundspec
                interval = np.arange(start, stop + step / 2, step)
                predicate = lambda value, _: value in interval
        # Param with a discrete set of values
        elif isinstance(boundspec, set):
            predicate = lambda value, _: value in boundspec
        # Param with values of one specified type
        elif inspect.isclass(boundspec):
            predicate = lambda value, _: isinstance(value, boundspec)
        # Param with values truth-tested by a user-defined predicate function
        elif inspect.isfunction(boundspec):
            num_args = len(inspect.signature(boundspec).parameters)
            stringrep = f"tested by {boundspec.__qualname__}"
            # function needs a single argument which is the value to be tested
            if num_args == 1:
                predicate = lambda value, _: boundspec(value)
            # function also needs the state of the obj the Param is bound to
            elif num_args == 2:
                predicate = lambda value, obj: boundspec(value, obj)
        # Param with multiple bound specifications
        elif is_nested():
            predicates, stringreps = zip(*(self._parse(spec) for spec in boundspec))
            # value must pass all specifications
            if isinstance(boundspec, list):
                predicate = lambda value, obj: all((p(value, obj) for p in predicates))
                stringrep = f"all({', '.join(stringreps)})"
            # value must pass any specification
            elif isinstance(boundspec, tuple):
                predicate = lambda value, obj: any((p(value, obj) for p in predicates))
                stringrep = f"any({', '.join(stringreps)})"
        else:
            raise BoundsParsingError(f"invalid bound specification {boundspec}")

        return predicate, stringrep

    def __call__(self, value, obj):
        """ """
        return self._predicate(value, obj)

    def __repr__(self) -> str:
        """ """
        return self._stringrep


class Param:
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
        self._bound = Bounds(bounds)
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

        if self._getter is None:  # Param is not gettable
            raise ParamGetterError(f"'{self._name}' is not gettable")

        value = self._getter(obj)
        parsed_value = self._parse(value)  # cast value if specified
        if not self._bound(parsed_value):  # check value bounds
            msg = f"Got bad {self._name} value = {parsed_value}"
            raise ParamOutOfBoundsError(msg)
        return parsed_value

    def __set__(self, obj: Any, value: Any) -> None:
        parsed_value = self._parse(value)  # cast value if specified

        if not self._bound(parsed_value):  # check value bounds
            msg = f"{self._name} out of bounds given by '{self._bounds}'"
            raise ParamOutOfBoundsError(msg)

        if self._setter is None:  # Param is only settable once
            if f"_{self._name}" in obj.__dict__:
                raise ParamSetterError(f"'{self._name}' is not settable")
            self._default_setter(obj, parsed_value)
        else:
            self._setter(obj, parsed_value)

    def _get_getter(
        self, getter: Union[Callable[[Any], Any], bool, str]
    ) -> Callable[[Any], Any]:
        """ """
        if getter is False:
            return None
        elif getter is True:
            return self._default_getter
        elif isinstance(getter, str):

            def scpi_Param_getter(obj: Any) -> Any:
                try:
                    return obj.handle.query(f"{getter}?")
                except AttributeError:
                    msg = f"Failed to query '{self._name}' from the handle of '{obj}'"
                    raise ParamGetterError(msg) from None

            return scpi_Param_getter
        elif callable(getter):

            def dll_Param_getter(obj: Any) -> Any:
                try:
                    return getter(obj.handle)
                except AttributeError:
                    msg = f"Failed to access the handle of {obj} to get '{self._name}'"
                    raise ParamGetterError(msg) from None

            return dll_Param_getter
        else:
            raise ParamGetterError(f"Invalid {getter = }")

    def _default_getter(self, obj: Any) -> Any:
        """ """
        try:
            return getattr(obj, f"_{self._name}")
        except AttributeError:
            raise ParamGetterError(f"'{self._name}' is not set yet") from None

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

                def scpi_Param_setter(obj: Any, value: Any) -> None:
                    try:
                        obj.handle.write(f"{getter} {value}")
                    except AttributeError:
                        msg = f"Failed to write '{self._name}' to the handle of '{obj}'"
                        raise ParamSetterError(msg) from None

                return scpi_Param_setter
            return self._default_setter
        elif callable(setter):

            def dll_Param_setter(obj: Any, value: Any) -> None:
                try:
                    return setter(obj.handle, value)
                except AttributeError:
                    msg = f"Failed to access the handle of {obj} to set '{self._name}'"
                    raise ParamGetterError(msg) from None

            return dll_Param_setter
        else:
            raise ParamSetterError(f"Invalid {setter = }")

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
                raise ParamConversionError(msg)
            except ValueError:
                msg = f"Invalid {value = } for parser '{self._parser}'"
                raise ParamConversionError(msg)
        return value


def parametrize(cls: Type[Any]) -> set[str]:
    """Finds the names of Params of a class hierachy"""
    if not inspect.isclass(cls):
        raise ValueError("Only python classes can be parametrized")
    mro = inspect.getmro(cls)
    return {k for c in mro for k, v in c.__dict__.items() if isinstance(v, Param)}

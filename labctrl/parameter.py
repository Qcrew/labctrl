""" """

import inspect
from typing import Any, Type


class BoundsParsingError(Exception):
    """ """


class OutOfBoundsError(Exception):
    """ """


class BoundingError(Exception):
    """ """


class _MISSING:
    """Sentinel for missing parameter default value"""

    def __repr__(self):
        """ """
        return "<MISSING>"


class Parameter:
    """ """

    class Bounds:
        """ """

        def __init__(self, boundspec) -> None:
            """ """
            try:
                self._predicate, self._stringrep = self._parse(boundspec)
            except (TypeError, RecursionError, ValueError, UnboundLocalError):
                message = f"Invalid bound specification: {boundspec}"
                raise BoundsParsingError(message) from None

        def _parse(self, boundspec):
            """ """
            stringrep = str(boundspec)  # default case
            numeric = lambda: all(isinstance(spec, (int, float)) for spec in boundspec)

            # unbounded Parameter
            if boundspec is None:
                predicate = lambda *_: True
            # Parameter with numeric values inside a closed interval [min, max]
            elif isinstance(boundspec, list) and numeric() and len(boundspec) == 2:
                min, max = boundspec
                predicate = lambda val, _: min <= val <= max
            # Parameter with a discrete set of values
            elif isinstance(boundspec, set):
                predicate = lambda val, _: val in boundspec
            # Parameter with values of one specified type
            elif inspect.isclass(boundspec):
                predicate = lambda val, _: isinstance(val, boundspec)
            # Parameter with values truth-tested by a user-defined predicate function
            elif inspect.isfunction(boundspec):
                num_args = len(inspect.signature(boundspec).parameters)
                stringrep = f"tested by {boundspec.__qualname__}"
                # function needs a single argument which is the value to be tested
                if num_args == 1:
                    predicate = lambda val, _: boundspec(val)
                # function also needs the state of the object the Parameter is bound to
                elif num_args == 2:
                    predicate = lambda val, obj: boundspec(val, obj)
            # Parameter with multiple bound specifications
            else:
                predicates, stringreps = zip(*(self._parse(spec) for spec in boundspec))
                # value must pass all specifications
                if isinstance(boundspec, list):
                    predicate = lambda val, obj: all((p(val, obj) for p in predicates))
                    stringrep = f"all({', '.join(stringreps)})"
                # value must pass any specification
                elif isinstance(boundspec, tuple):
                    predicate = lambda val, obj: any((p(val, obj) for p in predicates))
                    stringrep = f"any({', '.join(stringreps)})"

            return predicate, stringrep

        def __call__(self, value, obj, param) -> None:
            """ """
            try:
                truth = self._predicate(value, obj)
            except (TypeError, ValueError) as error:
                message = f"Can't validate Parameter '{param}' bounds due to {error = }"
                raise BoundingError(message) from None
            else:
                if not truth:
                    message = f"Parameter '{param}' {value = } is out of bounds {self}"
                    raise OutOfBoundsError(message)

        def __repr__(self) -> str:
            """ """
            return self._stringrep

    def __init__(self, bounds=None, default=_MISSING):
        """ """
        self._name = None  # updated by __set_name__()
        self._bound = self.Bounds(bounds)
        self._default = default  # default value of the parameter
        self._get, self._set = None, None  # updated by getter() and setter()

    def __repr__(self) -> str:
        """ """
        return (
            f"{self.__class__.__name__}('{self._name}', bounds = {self._bound}, "
            f"default = {self._default})"
        )

    def __set_name__(self, cls: Type[Any], name: str) -> None:
        """ """
        self._name = name

    def __get__(self, obj: Any, cls: Type[Any] = None) -> Any:
        """ """
        if obj is None:  # user wants to inspect this Parameter's object representation
            return self

        if self._get is None:  # user has not specified a getter for this Parameter
            raise AttributeError(f"Parameter '{self._name}' is not gettable")

        value = self._get(obj)
        self._bound(value, obj, self._name)  # validate the value that was got
        return value

    def __set__(self, obj: Any, value: Any) -> Any:
        """ """
        if self._set is None:  # user has not specified a setter for this Parameter
            raise AttributeError(f"Parameter '{self._name}' is not settable")
        self._bound(value, obj, self)  # validate the value to be set
        self._set(obj, value)

    def getter(self, getter):
        """ """
        self._get = getter
        return self

    @property
    def is_gettable(self) -> bool:
        """ """
        return self._get is not None

    def setter(self, setter):
        """ """
        self._set = setter
        return self

    @property
    def is_settable(self) -> bool:
        """ """
        return self._set is not None

    @property
    def default(self) -> Any:
        """ """
        return self._default

    @property
    def has_default(self) -> bool:
        """ """
        return self._default is not _MISSING


def parametrize(cls: Type[Any]) -> dict[str, Parameter]:
    """ """
    if not inspect.isclass(cls):
        raise ValueError(f"Argument must be a Python class, not '{cls}' of {type(cls)}")
    f = inspect.getmro(cls)  # f is for family
    return {k: v for c in f for k, v in c.__dict__.items() if isinstance(v, Parameter)}

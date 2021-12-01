""" """

import functools
import inspect
from typing import Any, Type

import numpy as np


class BoundsParsingError(Exception):
    """ """


class ParserParsingError(Exception):
    """ """


class OutOfBoundsError(Exception):
    """ """


class BoundingError(Exception):
    """ """


class ParsingError(Exception):
    """ """


class NotGettableError(Exception):
    """ """


class NotSettableError(Exception):
    """ """


class Parameter:
    """ """

    class Bounds:
        """ """

        def __init__(self, boundspec) -> None:
            """ """
            try:
                self._predicate, self._stringrep = self._parse(boundspec)
            except (TypeError, RecursionError, ValueError, UnboundLocalError):
                message = f"invalid bound specification: {boundspec}"
                raise BoundsParsingError(message) from None

        def _parse(self, boundspec):
            """ """
            stringrep = str(boundspec)  # default case
            numeric = lambda: all(isinstance(spec, (int, float)) for spec in boundspec)

            # unbounded Parameter
            if boundspec is None:
                predicate = lambda *_: True
            # Parameter with numeric values in an interval
            elif isinstance(boundspec, (list, tuple)) and numeric():
                # continuous value in closed interval [min, max]
                if len(boundspec) == 2:
                    min, max = boundspec
                    predicate = lambda value, _: min <= value <= max
                # linearly spaced values in closed interval [start, stop, step]
                elif len(boundspec) == 3:
                    start, stop, step = boundspec
                    interval = np.arange(start, stop + step / 2, step)
                    predicate = lambda value, _: value in interval
            # Parameter with a discrete set of values
            elif isinstance(boundspec, set):
                predicate = lambda value, _: value in boundspec
            # Parameter with values of one specified type
            elif inspect.isclass(boundspec):
                predicate = lambda value, _: isinstance(value, boundspec)
            # Parameter with values truth-tested by a user-defined predicate function
            elif inspect.isfunction(boundspec):
                num_args = len(inspect.signature(boundspec).parameters)
                stringrep = f"tested by {boundspec.__qualname__}"
                # function needs a single argument which is the value to be tested
                if num_args == 1:
                    predicate = lambda value, _: boundspec(value)
                # function also needs the state of the object the Parameter is bound to
                elif num_args == 2:
                    predicate = lambda value, obj: boundspec(value, obj)
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
                raise BoundingError(f"can't test {param} due to {error = }") from None
            else:
                if not truth:
                    raise OutOfBoundsError(f"{value = } out of bounds for {param}")

        def __repr__(self) -> str:
            """ """
            return self._stringrep

    class Parser:
        """ """

        def __init__(self, parserspec):
            """ """
            try:
                self._function, self._stringrep = self._parse(parserspec)
            except UnboundLocalError:
                message = f"invalid parser specification: {parserspec}"
                raise ParserParsingError(message) from None

        def _parse(self, parserspec):
            """ """
            stringrep = str(parserspec)  # default case
            # do not parse Parameter
            if parserspec is None:
                function = lambda val, *_: val
            # parse Parameter by passing it to a user-specified type
            elif inspect.isclass(parserspec):
                function = lambda val, *_: parserspec(val)
            # parse Parameter by passing it to a user-specified function
            elif inspect.isfunction(parserspec):
                num_args = len(inspect.signature(parserspec).parameters)
                stringrep = f"{parserspec.__qualname__}"
                # function needs a single argument which is the value to be parsed
                if num_args == 1:
                    function = lambda val, *_: parserspec(val)
                # function also needs the state of the object the Parameter is bound to
                elif num_args == 2:
                    function = lambda val, obj: parserspec(val, obj)
            return function, stringrep

        def __call__(self, value, obj, paramname):
            """ """
            try:
                return self._function(value, obj)
            except (TypeError, ValueError) as error:
                message = f"can't parse {paramname} with {self} due to {error = }"
                raise ParsingError(message) from None

        def __repr__(self) -> str:
            """ """
            return self._stringrep

    def __init__(self, bounds=None):
        """ """
        self._name = None  # updated by __set_name__()
        self._bound = self.Bounds(bounds)
        self._get, self._parseget = None, None  # updated by getter()
        self._set, self._parseset = None, None  # updated by setter()

    def __repr__(self) -> str:
        """ """
        return f"{self.__class__.__name__}('{self._name}', bounds = {self._bound})"

    def __set_name__(self, cls: Type[Any], name: str) -> None:
        """ """
        self._name = name

    def __get__(self, obj: Any, cls: Type[Any] = None) -> Any:
        """ """
        if obj is None:
            return self
        if self._get is None:
            raise NotGettableError(f"'{self._name}'")
        rawvalue = self._get(obj)
        parsedvalue = self._parseget(rawvalue, obj, self)
        self._bound(parsedvalue, obj, self._name)
        return parsedvalue

    def __set__(self, obj: Any, value: Any) -> Any:
        """ """
        if self._set is None:
            raise NotSettableError(f"'{self._name}'")
        self._bound(value, obj, self)
        parsedvalue = self._parseset(value, obj, self)
        self._set(obj, parsedvalue)

    def getter(self, getter=None, *, parser=None):
        """ """
        if getter is None:
            return functools.partial(self.getter, parser=parser)
        self._parseget = self.Parser(parser)
        self._get = getter
        return self

    @property
    def is_gettable(self) -> bool:
        return self._get is not None

    def setter(self, setter=None, *, parser=None):
        """ """
        if setter is None:
            return functools.partial(self.setter, parser=parser)
        self._parseset = self.Parser(parser)
        self._set = setter
        return self

    @property
    def is_settable(self) -> bool:
        return self._set is not None


def parametrize(cls: Type[Any]) -> dict[str, Parameter]:
    """ """
    if not inspect.isclass(cls):
        raise ValueError(f"argument must be a class, not {cls} of {type(cls)}")
    f = inspect.getmro(cls)  # f is for family
    return {k: v for c in f for k, v in c.__dict__.items() if isinstance(v, Parameter)}

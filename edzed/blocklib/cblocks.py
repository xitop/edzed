"""
Combinational blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

from collections.abc import Callable
import inspect
from typing import Any

from .. import block

__all__ = ['And', 'Or', 'Not', 'FuncBlock', 'Compare', 'Override']


class Not(block.CBlock):
    """
    Boolean negation.
    """
    def calc_output(self) -> bool:
        return not self._in['_'][0]

    def start(self) -> None:
        super().start()
        self.check_signature({'_': 1})


class FuncBlock(block.CBlock):
    """
    Create a combinational circuit block from a regular function.
    """

    def __init__(self, *args, func: Callable, unpack: bool = True, **kwargs):
        self._func = func
        self._unpack = unpack
        super().__init__(*args, **kwargs)

    def calc_output(self) -> Any:
        kwargs = {name: self._in[name] for name in self.inputs}
        args = kwargs.pop('_', ())
        if self._unpack:
            return self._func(*args, **kwargs)
        return self._func(args, **kwargs)

    def start(self) -> None:
        try:
            func = self._func
            self._func = inspect.signature(func).bind
            self.calc_output()
        except TypeError as err:
            raise TypeError(
                f"function {func.__qualname__} does not match the connected inputs: {err}"
                ) from None
        finally:
            self._func = func
        super().start()


class And(FuncBlock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, func=all, unpack=False, **kwargs)


class Or(FuncBlock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, func=any, unpack=False, **kwargs)


class Compare(block.CBlock):
    """
    A comparator with hysteresis.
    """

    # low, high = type "Comparable"
    def __init__(self, *args, low, high, **kwargs):
        if high < low:
            raise ValueError("high threshold cannot be lower than low threshold")
        self._low = low
        self._high = high
        super().__init__(*args, **kwargs)

    def calc_output(self) -> bool:
        if self._output is block.UNDEF:
            thr = (self._low + self._high) / 2
        else:
            thr = self._low if self._output else self._high
        return self._in['_'][0] >= thr

    def start(self) -> None:
        super().start()
        self.check_signature({'_': 1})


class Override(block.CBlock):
    """
    Either pass input to output unchanged or override it with value.
    """
    def __init__(self, *args, null_value: Any = None, **kwargs):
        self._null = null_value
        super().__init__(*args, **kwargs)

    def calc_output(self) -> Any:
        override = self._in.override
        return self._in.input if override == self._null else override

    def start(self) -> None:
        super().start()
        self.check_signature({'input': None, 'override': None})

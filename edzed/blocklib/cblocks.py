"""
Combinational blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import inspect

from .. import block

__all__ = ['Invert', 'FuncBlock', 'Compare', 'Override']


class Invert(block.CBlock):
    """
    Boolean negation.
    """
    def _eval(self):
        return not self._in['_'][0]

    def start(self):
        super().start()
        self.check_signature({'_': 1})


class FuncBlock(block.CBlock):
    """
    Create a combinational circuit block from a regular function.
    """

    def __init__(self, *args, func, unpack: bool = True, **kwargs):
        self._func = func
        self._unpack = unpack
        super().__init__(*args, **kwargs)

    def _eval(self):
        kwargs = {name: self._in[name] for name in self.inputs}
        args = kwargs.pop('_', ())
        if self._unpack:
            return self._func(*args, **kwargs)
        return self._func(args, **kwargs)

    def start(self):
        try:
            func = self._func
            self._func = inspect.signature(func).bind
            self._eval()
        except TypeError as err:
            raise TypeError(
                f"function {func.__qualname__} does not match the connected inputs: {err}")
        finally:
            self._func = func
        super().start()


class Compare(block.CBlock):
    """
    A comparator with hysteresis.
    """

    def __init__(self, *args, low, high, **kwargs):
        if high < low:
            raise ValueError("high threshold cannot be lower than low threshold")
        self._low = low
        self._high = high
        super().__init__(*args, **kwargs)

    def _eval(self):
        if self._output is block.UNDEF:
            thr = (self._low + self._high) / 2
        else:
            thr = self._low if self._output else self._high
        return self._in['_'][0] >= thr

    def start(self):
        super().start()
        self.check_signature({'_': 1})


class Override(block.CBlock):
    """
    Either pass input to output unchanged or override it with value.
    """
    def __init__(self, *args, null_value=None, **kwargs):
        self._null = null_value
        super().__init__(*args, **kwargs)

    def _eval(self):
        override = self._in.override
        return self._in.input if override == self._null else override

    def start(self):
        super().start()
        self.check_signature({'input': None, 'override': None})

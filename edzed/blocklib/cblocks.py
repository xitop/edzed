"""
Combinational blocks for general use.
"""

from .. import block

__all__ = ['Invert', 'FuncBlock', 'Override']


class Invert(block.CBlock):
    """Boolean negation."""
    def _eval(self):
        return not self.i0

    def start(self):
        super().start()
        self.check_signature({'_': 1})


class FuncBlock(block.CBlock):
    """
    Create a combinational circuit block from a regular function.

    Inputs from blocks as defined by connect()'s positional and keyword
    arguments will be passed to the function as its respective
    positional and keyword arguments.

    When unpack is False, all positional argument will be passed as
    a single tuple. This allows to directly call many useful Python
    functions expecting an iterable like all (logical AND),
    any (logical OR), or sum.
    """

    def __init__(self, *args, func, unpack=True, **kwargs):
        self._func = func
        self._unpack = unpack
        super().__init__(*args, **kwargs)

    def _eval(self):
        kwargs = {name: self.i[name] for name in self.inputs}
        args = kwargs.pop('_', ())
        if self._unpack:
            return self._func(*args, **kwargs)
        return self._func(args, **kwargs)


class Override(block.CBlock):
    """
    Either pass input to output unchanged or override it with value.

    Pass mode: when 'override' input is equal to null_value.
    Override mode: when 'override' input differs from null_value.

    The null_value is configurable and defaults to None.

    Usage: Override(NAME).connect(input=..., override=...)
    """
    def __init__(self, *args, null_value=None, **kwargs):
        self._null = null_value
        super().__init__(*args, **kwargs)

    def _eval(self):
        override = self.i.override
        return self.i.input if override == self._null else override

    def start(self):
        super().start()
        self.check_signature({'input': None, 'override': None})

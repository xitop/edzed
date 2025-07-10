"""
Mutable booleans.

Introduced to provide test&set and test&clear functions.
"""

from __future__ import annotations

from typing import Any
try:
    from typing import Self     # Python 3.11+
except ImportError:
    from typing import TypeVar
    Self = TypeVar("Self", bound="Flag")    # type: ignore[misc,assignment]


class Flag:
    """
    Mutable boolean value.

    All operations are performed logically, NOT bitwise,
    even if operator symbols &, |, and ^ are used.

    1. Methods returning bool (False or True).

        bool(flag)      # return current value
                        # in boolean context this is done automatically
        flag.test_set()     # set, return previous value
        flag.test_clear()   # clear, return previous value
        flag.test_toggle()  # toggle, return previous value

    2A. Methods updating in-place and then returning self:

        flag.set(val)   # assign the boolean value of 'val'
        flag.clear()    # same as:  flag.set(False)
        flag.set()      # same as:  flag.set(True)
        flag.toggle()   # in-place negation
        flag.iand(val)  # in-place AND
        flag.ior(val)   # in-place OR
        flag.ixor(val)  # in-place XOR

    2B. In-place updates as augmented assignments:

        flag &= val     # logical AND
        flag |= val     # logical OR
        flag ^= val     # logical XOR

    3. Operations returning a new instance:

        Flag(val)       # flag_copy = Flag(flag)
        ~flag           # logically negated value
        flag & val      # logical AND, also with swapped operands
        flag | val      # logical OR,  also with swapped operands
        flag ^ val      # logical XOR, also with swapped operands

    4A. Comparison with other Flags and booleans:

        Flag(True) == Flag(True)
        Flag(True) == True
        Flag(True) == 1
        Flag(false) == 0

    4B. DO NOT use instance tests for comparison. They cannot work
        because Flags are mutable:

        Flag(True) is Flag(True)    # WRONG
        flag is False               # WRONG
        flag is True                # WRONG
    """

    def __init__(self, value: Any):
        self._value = bool(value)

    def __bool__(self) -> bool:
        return self._value

    def __int__(self):
        # for compatibility with bool which is a subclass of int
        return int(self._value)

    def __eq__(self, other) -> bool:
        """
        Compare with other Flag, a bool or a numeric bool equivalent.

        Type bool is a subclass of int, False == 0, True == 1.
        """
        if hasattr(other, '__int__'):
            return int(self) == int(other)
        return NotImplemented

    def test_set(self) -> bool:
        """Test and then set."""
        value = self._value
        self._value = True
        return value

    def test_clear(self) -> bool:
        """Test and then clear."""
        value = self._value
        self._value = False
        return value

    def test_toggle(self) -> bool:
        """Test and then toggle."""
        value = self._value
        self._value = not value
        return value

    def set(self, value: bool = True) -> Self:
        """set the flag or set a value."""
        self._value = bool(value)
        return self

    def clear(self) -> Self:
        """clear the flag, i.e. assign False."""
        self._value = False
        return self

    def toggle(self) -> Self:
        """Invert in-place."""
        self._value = not self._value
        return self

    def __and__(self, other) -> Self:
        return (type(self))(self._value and bool(other))

    def __or__(self, other) -> Self:
        return (type(self))(self._value or bool(other))

    def __xor__(self, other) -> Self:
        return (type(self))(self._value is not bool(other))

    __rand__ = __and__
    __ror__  = __or__
    __rxor__ = __xor__

    def __iand__(self, other) -> Self:
        if not other:
            self._value = False
        return self

    def __ior__(self, other) -> Self:
        if other:
            self._value = True
        return self

    def __ixor__(self, other) -> Self:
        if other:
            self._value = not self._value
        return self

    iand = __iand__
    ior  = __ior__
    ixor = __ixor__

    def __invert__(self) -> Self:
        """Implement ~flag."""
        return (type(self))(not self._value)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}({self._value})>"

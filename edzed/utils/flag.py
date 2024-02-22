"""
Mutable booleans.

Introduced to provide test&set and test&clear functions.
"""

class Flag:
    """
    An alternative for bool.
    """

    def __init__(self, value:bool):
        self._value = bool(value)

    def set(self, value:bool = True) -> bool:
        """set the flag or set a value."""
        self._value = bool(value)
        return self._value

    def clear(self) -> bool:
        """clear the flag, i.e. assign False."""
        self._value = False
        return False

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

    # lowercase "and", "or" are  keywords
    def AND(self, other: bool) -> bool:
        """logical AND with other value"""
        if not other:
            self._value = False
        return self._value

    def OR(self, other: bool) -> bool:
        """logical OR with other value"""
        if other:
            self._value = True
        return self._value

    def invert(self) -> bool:
        """Logical negation."""
        self._value = not self._value
        return self._value

    def __bool__(self) -> bool:
        return self._value

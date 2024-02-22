"""
Test the Flag class.
"""

from edzed.utils.flag import Flag

def test_flag():
    for v in (False, True, None, "", "12", 12, 0.0, 3.14):
        assert bool(b := Flag(v)) is (bv := bool(v))
        assert b.invert() is not bv
        assert b.set(v) is bv
        assert b.clear() is False
        assert Flag(v).set() is True
        assert Flag(True).AND(v) is bv
        assert Flag(False).AND(v) is False
        assert Flag(True).OR(v) is True
        assert Flag(False).OR(v) is bv

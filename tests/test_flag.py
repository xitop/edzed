"""
Test the Flag class.
"""

from edzed.utils.flag import Flag

# warning:  X is not True    # X is any object except True
#           X is (not True)  # X is the constant False
# warning:  boolvar is True  # correct test
#           flagvar is True  # WRONG
#           flagvar == True  # correct
# pylint: disable=singleton-comparison

def test_init():
    """Flag(arg) takes the boolean value of arg."""
    for bv in (False, True, None, "", "12", 12, 0.0, 3.14):
        assert bool(Flag(bv)) is bool(bv)


def test_test_op():
    """Test Flag.test_set() and friends."""
    for bv in False, True:
        fl = Flag(bv)
        assert fl.test_clear() is bv
        assert isinstance(fl, Flag) and fl == False
        fl = Flag(bv)
        assert fl.test_set() is bv
        assert isinstance(fl, Flag) and fl == True
        fl = Flag(bv)
        assert fl.test_toggle() is bv
        assert isinstance(fl, Flag) and fl == (not bv)


def test_equality():
    """Test comparison."""
    no = Flag(False)
    # NOT POSSIBLE: assert no is False
    assert no == False
    assert no == 0
    assert no == 0.0
    yes = Flag(True)
    # NOT POSSIBLE: assert yes is True
    assert yes == True
    assert yes == 1
    assert yes == 1.0

    for a in False, True:
        for b in False, True:
            assert (a is b) is (Flag(a) == Flag(b)) is (a == Flag(b))

def test_return_self():
    """All mutating methods return self."""
    f1 = Flag(True)
    f2 = f1.set().clear().toggle().iand(True).ior(True).ixor(True)
    assert f1 is f2
    assert f2 == False


def test_mutating():
    """Test methods."""
    for bv in False, True:
        assert Flag(bv).set() == True
        assert Flag(bv).set(bv) == bv
        assert Flag(bv).clear() == False
        assert Flag(bv).toggle() == (not bv)
        assert Flag(bv) != Flag(not bv)


def test_invert():
    """~flag returns a new object."""
    for bv in False, True:
        f1 = Flag(bv)
        f2 = ~f1
        assert f1 is not f2
        assert isinstance(f2, Flag)
        assert f1 != f2
        assert Flag(bv) == ~Flag(not bv)
        assert Flag(bv) == ~~Flag(bv)


def test_logical_ops():
    for bv in False, True:
        # COPY
        assert bool(rfl := Flag(Flag(Flag(bv)))) is bv
        assert isinstance(rfl, Flag)
        # AND
        assert bool(rfl1 := Flag(True) & bv) is bool(rfl2 := bv & Flag(True)) is bv
        assert bool(rfl3 := Flag(False) & bv) is bool(rfl4 := bv & Flag(False)) is False
        assert rfl1 == rfl2 and rfl3 == rfl4
        assert all(isinstance(rfl, Flag) for rfl in (rfl1, rfl2, rfl3, rfl4))
        # OR
        assert bool(rfl1 := Flag(True) | bv) is bool(rfl2 := bv | Flag(True)) is True
        assert bool(rfl3 := Flag(False) | bv) is bool(rfl4 := bv | Flag(False)) is bv
        assert rfl1 == rfl2 and rfl3 == rfl4
        assert all(isinstance(rfl, Flag) for rfl in (rfl1, rfl2, rfl3, rfl4))
        # XOR
        assert bool(rfl1 := Flag(True) ^ bv) is bool(rfl2 := bv ^ Flag(True)) is (not bv)
        assert bool(rfl3 := Flag(False) ^ bv) is bool(rfl4 := bv ^ Flag(False)) is bv
        assert rfl1 == rfl2 and rfl3 == rfl4
        assert all(isinstance(rfl, Flag) for rfl in (rfl1, rfl2, rfl3, rfl4))


def test_in_place():
    """Test augmented assignments and corresponding methods."""
    for a in False, True:
        for b in False, True:
            f1 = Flag(a)
            f1 &= b
            f2 = Flag(a)
            f3 = f2.iand(b)
            assert isinstance(f1, Flag) and isinstance(f2, Flag) and f3 is f2
            assert f1 == f2 == (a and b)

            f1 = Flag(a)
            f1 |= b
            f2 = Flag(a)
            f3 = f2.ior(b)
            assert isinstance(f1, Flag) and isinstance(f2, Flag) and f3 is f2
            assert f1 == f2 == (a or b)

            f1 = Flag(a)
            f1 ^= b
            f2 = Flag(a)
            f3 = f2.ixor(b)
            assert isinstance(f1, Flag) and isinstance(f2, Flag) and f3 is f2
            assert f1 == f2 == (a is not b)

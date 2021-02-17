"""
Test basic circuit block functionality.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_undef():
    """Undef is a always false and is a singleton."""
    undef = edzed.UNDEF
    assert not undef  # bool value is false
    assert str(undef) == '<UNDEF>'
    undeftype = type(undef)
    assert undeftype() is undeftype()   # singleton


def test_const():
    """Const objects are reused."""
    CONST = 'some value'
    ch1 = edzed.Const(CONST)
    assert ch1.output == CONST
    ch2 = edzed.Const(CONST)
    assert ch1 is ch2                   # ch1 was reused
    # make sure our implementation with a dict of all instances
    # can handle also unhashable values
    UNHASHABLE = [0]
    cu1 = edzed.Const(UNHASHABLE)
    assert cu1.output == UNHASHABLE


def test_reset_circuit(circuit):
    """Reset creates a new empty circuit."""
    assert circuit is edzed.get_circuit()
    assert list(circuit.getblocks()) == []
    blk = Noop('test')
    assert list(circuit.getblocks()) == [blk]

    edzed.reset_circuit()
    newcircuit = edzed.get_circuit()
    assert newcircuit is not circuit
    assert list(newcircuit.getblocks()) == []


def test_no_dup(circuit):
    """Names must be unique."""
    Noop('dup')
    with pytest.raises(ValueError, match="Duplicate"):
        Noop('dup')


def test_invalid_names(circuit):
    """Names must be non-empty strings."""
    with pytest.raises(TypeError):
        Noop(3.14)
    with pytest.raises(TypeError):
        Noop(Noop('name'))
    with pytest.raises(ValueError, match="empty"):
        Noop('')


def test_name(circuit):
    """Default description is added if it is not set."""
    blk1 = Noop('test1', desc='with description')
    blk2 = Noop('test2')
    assert blk1.name == 'test1'
    assert blk1.desc == "with description"
    assert blk2.name == 'test2'
    assert blk2.desc == ""


def test_reserved_names(circuit):
    """All _foo style names (starting with an underscore) are reserved."""
    with pytest.raises(ValueError, match="reserved"):
        Noop('_this_name_is_not_ok')
    with pytest.raises(ValueError, match="reserved"):
        Noop('_')
    with pytest.raises(ValueError, match="reserved"):
        Noop('__')


def test_automatic_names(circuit):
    """None as name will be replaced by some generated name."""
    Noop(None)
    Noop(None)
    Noop(None)
    blocks = list(circuit.getblocks())
    assert len(blocks) == 3
    assert all(blk.name.startswith('_@') for blk in blocks)
    assert blocks[0].name != blocks[1].name != blocks[2].name != blocks[0].name


def test_x_attributes(circuit):
    """x_name attributes are accepted."""
    blk = Noop('test', x_attr1='space', X_YEAR=2001)
    # pylint: disable=no-member
    assert blk.x_attr1 == 'space'
    assert blk.X_YEAR == 2001
    # no other x_attr
    assert sum(1 for name in vars(blk) if name.startswith('x_') or name.startswith('X_')) == 2


def test_getblocks(circuit):
    """Test getblocks() and findblock()."""
    # 1 Const, 2 CBlocks and 2 SBlocks
    edzed.Const(0)
    f1 = edzed.FuncBlock('F1', func=lambda: None)   # CBlock
    f2 = edzed.FuncBlock('F2', func=lambda: None)   # CBlock
    t1 = edzed.Timer('T1')  # SBlock
    t2 = edzed.Timer('T2')  # SBlock
    assert circuit.findblock('F1') is f1
    assert circuit.findblock('T2') is t2
    assert set(circuit.getblocks()) == {f1, f2, t1, t2}
    assert not set(circuit.getblocks(btype=edzed.Const)) # Const blocks are not registered
    assert set(circuit.getblocks(btype=edzed.CBlock)) == {f1, f2}
    assert set(circuit.getblocks(btype=edzed.SBlock)) == {t1, t2}


def test_debug(circuit):
    """Test set_debug()."""
    def blocks_set():
        return [i for i, blk in enumerate(blocks) if blk.debug]
    blocks = [
        edzed.FuncBlock('F1', func=lambda: None),   # CBlock
        edzed.FuncBlock('F2', func=lambda: None),   # CBlock
        edzed.Timer('T1'),  # SBlock
        edzed.Timer('T2'),  # SBlock
        ]

    assert blocks_set() == []
    assert circuit.set_debug(True, '*') == 4
    # check real block count without duplicates
    assert circuit.set_debug(True, '*', *blocks, 'F1', 'F1') == 4
    assert blocks_set() == [0, 1, 2, 3]
    assert circuit.set_debug(False, blocks[0]) == 1
    assert blocks_set() == [1, 2, 3]
    assert circuit.set_debug(False, 'F2') == 1
    assert blocks_set() == [2, 3]
    assert circuit.set_debug(True, edzed.CBlock) == 2
    assert blocks_set() == [0, 1, 2, 3]
    assert circuit.set_debug(False, '?2') == 2
    assert blocks_set() == [0, 2]


def test_is_multiple_and_to_tuple():
    """Check _is_multiple() and _to_tuple() helpers."""
    is_multiple = edzed.block._is_multiple
    to_tuple = edzed.block._to_tuple

    SINGLE_VALUES = ('name', 10, {'a', 'b', 'c'}, set(), None, True, edzed.Const(-1))
    for arg in SINGLE_VALUES:
        assert not is_multiple(arg)
        assert to_tuple(arg, lambda x: None) == (arg,)

    MULTI_VALUES = ((1, 2, 3), [0], (), [])
    for arg in MULTI_VALUES:
        assert is_multiple(arg)
        assert to_tuple(arg, lambda x: None) == tuple(arg)

    # iterators are multiple values and are not consumed by is_multiple
    iterator = (x for x in range(4))   # a generator is always an iterator
    assert is_multiple(iterator)
    # test that the iterator is not exausted yet
    assert to_tuple(iterator, lambda x: None) == (0, 1, 2, 3)

    # check that validators are being called
    to_tuple(1, lambda x: 1/x)
    with pytest.raises(ZeroDivisionError):
        to_tuple(0, lambda x: 1/x)


def disabled_test_addons():
    # RUNNING THIS TEST AFFECTS OTHER TESTS!
    # THE TEST IS DISABLED AND A BUG WAS FILED:
    # https://bugs.python.org/issue38085
    with pytest.raises(TypeError, match="add-on"):
        class CBlockWithAddon1(edzed.AddonAsync, edzed.CBlock):
            def calc_output(self):    # calc_output is abstract
                return None
    with pytest.raises(TypeError, match="add-on"):
        class CBlockWithAddon2(edzed.CBlock, edzed.AddonAsync):
            def calc_output(self):
                return None
    with pytest.raises(TypeError, match="add-on"):
        class SBlockWithAddonWrongOrder(edzed.SBlock, edzed.AddonAsync):
            def calc_output(self):
                return None

def test_has_method():
    class Without(edzed.SBlock):
        pass

    class With(edzed.SBlock):
        def init_from_value(self):
            pass
        async def init_async(self):
            pass
        async def stop_async(self):
            pass

    mno = Without('without_methods')
    myes = With('with_methods')

    for name in ('init_from_value', 'init_async', 'stop_async'):
        # has the dummy method
        assert getattr(mno, name, None) is not None
        assert not mno.has_method(name)
        # has its own method
        assert getattr(myes, name, None) is not None
        assert myes.has_method(name)

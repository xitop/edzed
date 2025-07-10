"""
Test basic circuit block functionality.
"""

# pylint: disable=missing-class-docstring, protected-access

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit, fixture_task_factories
from .utils import Noop


def test_undef():
    """Check UNDEF"""
    undef = edzed.UNDEF
    assert bool(undef) is False
    assert str(undef) == repr(undef) == '<UNDEF>'
    # pylint: disable=unidiomatic-typecheck
    assert type(undef) is edzed.block._UndefType


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


def test_no_undef_const():
    """Const() does not accept UNDEF."""
    edzed.Const(False)
    edzed.Const(None)
    edzed.Const('')
    with pytest.raises(ValueError):
        edzed.Const(edzed.UNDEF)


def test_reset_circuit(circuit):
    """Reset creates a new empty circuit."""
    assert circuit is edzed.get_circuit()
    assert not list(circuit.getblocks())
    blk = Noop('test')
    assert list(circuit.getblocks()) == [blk]

    edzed.reset_circuit()
    newcircuit = edzed.get_circuit()
    assert newcircuit is not circuit
    assert not list(newcircuit.getblocks())


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
    """An empty comment is added if it is not set."""
    blk1 = Noop('test1', comment='with comment')
    blk2 = Noop('test2')
    assert blk1.name == 'test1'
    assert blk1.comment == "with comment"
    assert blk2.name == 'test2'
    assert blk2.comment == ""


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
    edzed.Not(None)
    blocks = set(circuit.getblocks())
    assert len(blocks) == 4
    assert {b.name for b in blocks} == {'_Noop_0', '_Noop_1', '_Noop_2', '_Not_0'}


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


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_is_multiple_and_to_tuple():
    """Check _is_multiple() and _to_tuple() helpers."""
    is_multiple = edzed.block._is_multiple
    to_tuple = edzed.block._to_tuple
    def accept_all(anything):
        pass    # permissive validator

    # None is special case
    assert not is_multiple(None)
    assert to_tuple(None, accept_all) == ()

    SINGLE_VALUES = ('name', 10, {'a', 'b', 'c'}, set(), True, edzed.Const(-1))
    for arg in SINGLE_VALUES:
        assert not is_multiple(arg)
        assert to_tuple(arg, accept_all) == (arg,)

    MULTI_VALUES = ((1, 2, 3), [0], (), [])
    for arg in MULTI_VALUES:
        assert is_multiple(arg)
        assert to_tuple(arg, accept_all) == tuple(arg)

    # iterators are multiple values and are not consumed by is_multiple
    # iterators are deprecated since 23.2.14
    iterator = (x for x in range(4))   # a generator is always an iterator
    assert is_multiple(iterator)
    # test that the iterator is not exausted by _is_multiple()
    # iterators are deprecated since 23.2.14
    assert to_tuple(iterator, accept_all) == (0, 1, 2, 3)
    assert to_tuple(iterator, accept_all) == ()

    # check that validators are being called
    to_tuple(1, lambda x: 1/x)
    with pytest.raises(ZeroDivisionError):
        to_tuple(0, lambda x: 1/x)


# RUNNING THIS TEST MAY AFFECT OTHER TESTS!
# https://bugs.python.org/issue38085
# until a bugfix, the following three tests must be run in a separate process
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.forked
def test_incorrect_addon1():
    with pytest.raises(TypeError, match="add-on"):
        # pylint: disable=unused-variable
        class CBlockWithAddon1(edzed.AddonAsync, edzed.CBlock):
            def calc_output(self):    # calc_output is abstract
                return None

@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.forked
def test_incorrect_addon2():
    with pytest.raises(TypeError, match="add-on"):
        # pylint: disable=unused-variable
        class CBlockWithAddon2(edzed.CBlock, edzed.AddonAsync):
            def calc_output(self):
                return None

@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.forked
def test_incorrect_addon3():
    with pytest.raises(TypeError, match="add-on"):
        # pylint: disable=inconsistent-mro, unused-variable
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

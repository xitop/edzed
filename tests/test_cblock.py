"""
Test CBlocks functionality.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_connect_only_once(circuit):
    """Connect my be called only once."""
    blk = Noop('test')
    blk.connect(True)
    with pytest.raises(edzed.EdzedInvalidState):
        blk.connect(True)


def test_unnamed_inputs(circuit):
    """
    Unnamed inputs are processed in order as they are connected.

    Const blocks are created on the fly.
    """
    d4 = edzed.FuncBlock(
        '4 digits', func=lambda a, b, c, d: 1000*a + 100*b + 10*c + d
        ).connect(1, 9, 8, edzed.Const(4))
    init(circuit)

    d4.eval_block()
    assert d4.output == 1984


def test_named_inputs(circuit):
    """
    Named inputs are ordered by name.

    This test also covers that no unnamed inputs is a special case in FuncBlock.
    """
    d4 = edzed.FuncBlock(
        '4 digits', func=lambda a, b, c, d: 1000*a + 100*b + 10*c + d
        ).connect(d=9, c=edzed.Const(1), a=2, b=edzed.Const(0))
    init(circuit)

    d4.eval_block()
    assert d4.output == 2019


def test_input_groups(circuit):
    """Input group is a sequence of input values."""
    d4 = edzed.FuncBlock(
        '4 digits', func=lambda f4: 1000*f4[0] + 100*f4[1] + 10*f4[2] + f4[3]
        ).connect(f4=[edzed.Const(3), 5, 7, 9])
    init(circuit)

    d4.eval_block()
    assert d4.output == 3579


def test_missing_funcblock_inputs(circuit):
    """Incorrect number of inputs are an error."""
    errblks = [
        edzed.FuncBlock(
            'test1', desc='2 expected, 3 given', func=lambda a1, a2: None
            ).connect(1, 2, 3),
        edzed.FuncBlock(
            'test2', desc='2 expected, 1 given', func=lambda a1, a2: None
            ).connect(1),
        edzed.FuncBlock(
            'test3', desc='a1 name missing', func=lambda a1, a2: None
            ).connect(a2=2),
        edzed.FuncBlock(
            'test4', desc='a3 name unexpected', func=lambda a1, a2: None
            ).connect(a1=1, a2=2, a3=3),
        ]

    circuit.finalize()

    for blk in errblks:
        with pytest.raises(TypeError, match="does not match the connected inputs"):
            blk.start()


def test_input_by_name(circuit):
    """
    Input block may be specified by name.

    This implies that string constants require explicit Const('...')
    """
    Noop('blk_X').connect('blk_Y', edzed.Const('blk_Z'))    # blk_Z is just a string
    Noop('blk_Y').connect(a=('blk_X', None))
    init(circuit)


def test_no_unknown_inputs(circuit):
    """Test unknown block error. """
    Noop('blk_X').connect('blk_Y', edzed.Const('blk_Z'))
    Noop('blk_Y').connect(a=('blk_X', 'blk_Z'))     # there is no blk_Z
    with pytest.raises(Exception, match="not found"):
        init(circuit)


def test_no_cross_circuit_inputs(circuit):
    """No cross circuit connections. Constants are an exception."""
    noop1 = Noop('noop')
    msg1 = edzed.Const("hello!")
    init(circuit)

    edzed.reset_circuit()
    noop2 = Noop('noop').connect(noop1)
    circuit2 = edzed.get_circuit()
    with pytest.raises(ValueError, match="not in the current circuit"):
        init(circuit2)

    # Const objects do not belong to specific circuit
    edzed.reset_circuit()
    noop3 = Noop('noop').connect(msg1)
    circuit3 = edzed.get_circuit()
    init(circuit3)


def test_input_access(circuit):
    """Test various methods to access input values."""
    class MyBlock(edzed.CBlock):
        def _eval(self):
            return [
                self._in['_'],       # tuple of all unnanmed inputs
                self._in['ctrl'],    # input name as a key
                self._in.ctrl,       # input name as an attr
                ]

    blk = MyBlock('test').connect(50, 51, 52, 53, 54, ctrl=edzed.Const('CTRL'))
    init(circuit)

    blk.eval_block()
    assert blk.output == [
        (50, 51, 52, 53, 54),
        'CTRL',
        'CTRL',
        ]


def test_connection_attrs(circuit):
    """Check the iconnections and oconnections."""
    inp0 = Noop('inp0', desc="not connected to main").connect(-1)
    inp1 = Noop('inp1').connect('inp0', loopback='inp1')
    inp2 = Noop('inp2')
    inp3 = Noop('inp3').connect(x=(inp1, 'inp0'))
    inp4 = Noop('inp4', desc="not connected to anything").connect(x=inp3)
    main = Noop('main').connect(True, inp1, a=False, b=inp2, c=(10, 20, 'inp3'))
    init(circuit)

    assert not inp0.iconnections    # Const excl.
    assert inp1.iconnections == {inp0, inp1}
    assert not inp2.iconnections
    assert inp3.iconnections == {inp0, inp1}
    assert inp4.iconnections == {inp3}
    assert main.iconnections == {inp1, inp2, inp3}

    assert inp0.oconnections == {inp1, inp3}
    assert inp1.oconnections == {inp1, inp3, main}
    assert inp2.oconnections == {main}
    assert inp3.oconnections == {inp4, main}
    assert not inp4.oconnections
    assert not main.oconnections


def test_signature_exc(circuit):
    """Test exception getting a signature of an unconnected block."""
    blk = Noop('noname')
    with pytest.raises(edzed.EdzedInvalidState):
        blk.input_signature()
    blk.connect(foo=(0,0,0))
    assert blk.input_signature() == {'foo': 3}


def test_signature_and_get_conf(circuit):
    """Test input signature related functions."""
    blk1 = Noop('test1', desc=' without unnamed inputs').connect(
        inp2=20, inp3=30, inp1=10)

    blk2 = Noop('test2', desc='with unnamed inputs', ).connect(
        100, 101, 102, 103,         # unnamed (group '_')
        inpA=edzed.Const('A2'),     # named single input
        inpB=[edzed.Const('B2')],   # named sequence
        inpC=range(5),              # named iterator
        )
    assert 'inputs' not in blk1.get_conf()  # no data before finalization
    init(circuit)

    assert blk1.input_signature() == ({'inp1': None, 'inp2': None, 'inp3': None,})
    conf1 = blk1.get_conf()
    conf1ok = {
        # future versions may add additional keys to get_conf()
        'class': 'Noop',
        'debug': False,
        'desc': ' without unnamed inputs',
        'inputs': {
            'inp1': "<Const 10>",
            'inp2': "<Const 20>",
            'inp3': "<Const 30>",
            },
        'name': 'test1',
        'type': 'combinational',
        }
    assert all(conf1[key] == value for key, value in conf1ok.items())

    assert blk2.input_signature() == ({'inpA': None, '_': 4, 'inpB': 1, 'inpC': 5})
    assert blk2.get_conf()['inputs'] == {
        '_': ('<Const 100>', '<Const 101>', '<Const 102>', '<Const 103>'),
        'inpA': "<Const 'A2'>",
        'inpB': ("<Const 'B2'>",),      # a 1-tuple
        'inpC': ('<Const 0>', '<Const 1>', '<Const 2>', '<Const 3>', '<Const 4>'),
        }

    blk2.check_signature({'inpA': None, '_': 4, 'inpB': 1, 'inpC': 5})
    blk2.check_signature({'inpA': None, '_': [4, 5], 'inpB': [None, None], 'inpC': [0, 5]})

    with pytest.raises(ValueError, match="missing: 'extra'"):
        blk2.check_signature({'inpA': None, 'extra': None, '_': 4, 'inpB': 1, 'inpC': 5})
    with pytest.raises(ValueError, match="unexpected: 'inpA'"):
        blk2.check_signature({'_': 4, 'inpB': 1, 'inpC': 5})
    with pytest.raises(ValueError, match="count is 5, expected was 10"):
        blk2.check_signature({'inpA': None, '_': 4, 'inpB': 1, 'inpC': 10})
    with pytest.raises(ValueError, match="did you mean 'inp_A'"):
        blk2.check_signature({'inp_A': None, '_': 4, 'inpB': 1, 'inpC': 5})
    with pytest.raises(ValueError, match="count is 1, minimum is 2"):
        blk2.check_signature({'inpA': None, '_': 4, 'inpB': [2, None], 'inpC': 5})
    with pytest.raises(ValueError, match="count is 4, maximum is 3"):
        blk2.check_signature({'inpA': None, '_': (2, 3), 'inpB': [0, 1], 'inpC': 5})
    with pytest.raises(ValueError, match="invalid"):
        blk2.check_signature({'inpA': None, '_': 4.5, 'inpB': 1, 'inpC': 5})
    with pytest.raises(ValueError, match="invalid"):
        blk2.check_signature({'inpA': None, '_': [4], 'inpB': 1, 'inpC': 5})
    with pytest.raises(ValueError, match="invalid"):
        blk2.check_signature({'inpA': None, '_': [0, 1, 2, 3], 'inpB': 1, 'inpC': 5})


def test_eponymous(circuit):
    """Test name='' shortcut."""
    edzed.Input('white', initdef='W')
    edzed.Input('black', initdef='B')
    combine = edzed.FuncBlock(
        'combine',
        func=lambda black, white: black + '&' + white).connect(
            white='', black='') # i.e. white='white', black='black'
    init(circuit)
    combine.eval_block()
    assert combine.output == 'B&W'


def test_override(circuit):
    """Test the override block."""
    SENTINEL = 999
    inp = edzed.Input('inp', initdef=None)
    override = edzed.Input('ctrl', initdef=SENTINEL)
    out = edzed.Override('test', null_value=SENTINEL).connect(input=inp, override=override)
    init(circuit)

    TEST_VALUES = (17, 3.14, SENTINEL, True, False, None, "LAST")

    for value in TEST_VALUES:
        inp.event('put', value=value)
        out.eval_block()
        assert out.output == value

    for value in TEST_VALUES:
        override.event('put', value=value)
        out.eval_block()
        assert out.output == (value if value != SENTINEL else "LAST")   # parenthesis required


def test_compare(circuit):
    """Test the compare block."""

    with pytest.raises(ValueError, match="threshold"):
        edzed.Compare(None, low=10, high=5)

    inp = edzed.Input('inp', initdef=8.1)
    cmp1 = edzed.Compare('cmp1', low=7.0, high=9.0).connect(inp)    # 8.0 +- 1
    cmp2 = edzed.Compare('cmp2', low=8.0, high=9.0).connect(inp)    # 8.5 +- 0.5
    cmp3 = edzed.Compare('cmp3', low=8.0, high=8.0).connect(inp)    # 8.0 no hysteresis
    init(circuit)

    cmp1.eval_block()
    cmp2.eval_block()
    cmp3.eval_block()
    assert cmp1.output
    assert not cmp2.output
    assert cmp3.output

    # pylint: disable=bad-whitespace
    TEST1 = (8.1,  7.5,  6.0,   7.5,   100,  7.5,  7.0,  6.999, 7.0,   7.5,   9.0,  777)
    CMP1 =  (True, True, False, False, True, True, True, False, False, False, True, True)

    for t, c in zip(TEST1, CMP1):
        inp.put(t)
        cmp1.eval_block()
        assert cmp1.output == c
    assert inp.output == 777    # tested with all values?

    # pylint: disable=bad-whitespace
    TEST3 = (8.1,  7.9,   8.0,  100,  8.0,  7.0,   777)
    CMP3 =  (True, False, True, True, True, False, True)

    for t, c in zip(TEST3, CMP3):
        inp.put(t)
        cmp3.eval_block()
        assert cmp3.output == c
    assert inp.output == 777


def test_and_or(circuit):
    """Test unpack=False on AND/OR logical gates."""
    inp0 = edzed.Input('inp0', initdef=False)
    inp1 = edzed.Input('inp1', initdef=False)
    and_gate = edzed.FuncBlock('AND', func=all, unpack=False).connect(inp0, inp1, True)
    or_gate = edzed.FuncBlock('OR', func=any, unpack=False).connect(inp0, inp1, False)
    init(circuit)
    for v0, v1 in ((0, 0), (0, 1), (1, 0), (1, 1)):
        inp0.put(v0)
        inp1.put(v1)
        and_gate.eval_block()
        or_gate.eval_block()
        assert and_gate.output == bool(v0 and v1)
        assert or_gate.output == bool(v0 or v1)


def test_and_or_empty(circuit):
    """Test unpack=False with no inputs."""
    and_gate = edzed.FuncBlock('AND', func=all, unpack=False)
    or_gate = edzed.FuncBlock('OR', func=any, unpack=False)
    init(circuit)
    and_gate.eval_block()
    or_gate.eval_block()
    assert and_gate.output
    assert not or_gate.output


def test_invert(circuit):
    """Test explicitly created Invert blocks."""
    src = edzed.Input('src', allowed=(True, False), initdef=True)
    notsrc = edzed.Invert('notsrc').connect(src)
    src2 = edzed.Invert('src2').connect(notsrc)
    init(circuit)

    # Invert blocks are a special case in finalize()
    assert notsrc.iconnections == {src}
    assert notsrc.oconnections == {src2}
    for value in (True, False, True, False):
        src.put(value)
        notsrc.eval_block()
        src2.eval_block()
        assert notsrc.output is not value
        assert src2.output is value

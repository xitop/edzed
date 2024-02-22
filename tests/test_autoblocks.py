"""
Test automatically created blocks.
"""

import pytest

import edzed

# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import init, Noop

def test_invert(circuit):
    """Shortcut '_not_blk' creates an inverter block connected to blk."""
    src = edzed.Input('src', allowed=(True, False), initdef=False)
    id1 = edzed.FuncBlock('identity1', func=lambda x: x).connect('src')
    id2 = edzed.FuncBlock('identity2', func=lambda x: x).connect('_not_src')
    # verify that _not_src shortcut may be used multiple times
    id3 = edzed.FuncBlock('identity3', func=lambda x: x).connect('_not_src')

    # _not_src does not exist yet
    assert sum(1 for blk in circuit.getblocks()) == 4
    with pytest.raises(KeyError):
        circuit.findblock('_not_src')
    init(circuit)
    # _not_src was just created automatically by finalize()
    assert sum(1 for blk in circuit.getblocks()) == 5
    invert = circuit.findblock('_not_src')

    srcput = edzed.ExtEvent(src, 'put').send
    for value in (True, False, True, False):
        srcput(value)
        invert.eval_block()
        id1.eval_block()
        id2.eval_block()
        id3.eval_block()
        assert id1.output is value
        assert id2.output is id3.output is not value


def test_no_invert_invert(circuit):
    """_not__not_name has no special meaning."""
    edzed.Not('src').connect(edzed.Const(True))
    edzed.FuncBlock('F', func=lambda x: x).connect('_not_src')
    edzed.FuncBlock('T', func=lambda x: x).connect('_not__not_src')
    with pytest.raises(Exception, match="not found"):
        init(circuit)


def test_control_block_1(circuit):
    """A control block named _ctrl will be created on demand."""
    Noop('dummy').connect('_ctrl')
    init(circuit)
    ctrl = circuit.findblock('_ctrl')
    # pylint: disable-next=unidiomatic-typecheck
    assert type(ctrl) is edzed.ControlBlock


def test_control_block_2(circuit):
    """A control block named _ctrl will be created on demand."""
    Noop('dummy', on_output=edzed.Event('_ctrl', 'abort'))
    init(circuit)
    ctrl = circuit.findblock('_ctrl')
    # pylint: disable-next=unidiomatic-typecheck
    assert type(ctrl) is edzed.ControlBlock

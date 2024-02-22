"""
Test the Input block.
"""

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import init


def test_noinit(circuit):
    """Test missing init."""
    edzed.Input('no_init')
    with pytest.raises(edzed.EdzedCircuitError, match='not initialized'):
        init(circuit)


def test_init(circuit):
    """Initial value is assigned on init."""
    INITIAL = 'default_value'
    inp = edzed.Input('input', initdef=INITIAL)
    assert inp.output is edzed.UNDEF
    init(circuit)

    assert inp.output == INITIAL
    inp.event('put', value=3.14)
    assert inp.output == 3.14
    inp.event('put', value=inp.initdef)     # reset to default
    assert inp.output == INITIAL


def test_events(circuit):
    """Inputs support only the put event."""
    inp = edzed.Input('input', initdef=None)
    init(circuit)

    inp.event('put', value=1)
    assert inp.output == 1
    inp.event('put', value=2, junk=-1)  # extra keys ignored
    assert inp.output == 2
    inp.put(3)              # shortcut for .event('put', value=X), deprecated since 23.8.25
    assert inp.output == 3
    with pytest.raises(TypeError):
        inp.event('put')    # missing value
    with pytest.raises(edzed.EdzedUnknownEvent):
        inp.event('sleep')  # unknown event


def test_schema(circuit):
    """schema validator test."""
    inp = edzed.Input('input', schema=lambda x: int(x)+100, initdef=23)
    init(circuit)

    assert inp.output == 123    # schema is applied also to the default
    assert inp.event('put', value='string') is False
    assert inp.output == 123
    assert inp.event('put', value='68') is True
    assert inp.output == 168


def test_check(circuit):
    """check validator test."""
    inp = edzed.Input('input', check=lambda x: x % 5 == 0, initdef=5)
    init(circuit)

    inp_put = edzed.ExtEvent(inp).send
    assert inp.output == 5
    assert inp_put(25) is True
    assert inp.output == 25
    assert inp_put(68) is False
    assert inp.output == 25


def test_check_initdef(circuit):
    """initdef value is checked immediately."""
    with pytest.raises(ValueError, match="rejected"):
        # default of 23 does not pass the modulo 5 check
        edzed.Input('input', check=lambda x: x % 5 == 0, initdef=23)


def test_allowed(circuit):
    """allowed validator test."""
    ALLOWED = (False, 'YES', 2.5)
    NOT_ALLOWED = (True, None, '', 'hello', 99)
    inp = edzed.Input('input', allowed=ALLOWED, initdef=False)
    init(circuit)

    for v in ALLOWED:
        assert inp.event('put', value=v) is True
        assert inp.output == v
    last = inp.output
    for v in NOT_ALLOWED:
        assert inp.event('put', value=v) is False
        assert inp.output == last


def test_validators(circuit):
    """Test multiple validators."""
    # order = check, allowed, schema
    inputs = [
        edzed.Input('input1', allowed=[False, True], initdef=False),
        edzed.Input(
            'input2',
            check=lambda x: isinstance(x, bool), allowed=[False, True], initdef=False),
        edzed.Input('input3', schema=bool, allowed=[False, True], initdef=False),
        edzed.Input('input4', schema=bool, initdef=False),
        ]
    init(circuit)

    VALUES = (None, 1, 99)
    ACCEPTED = [
        (False, True, False),   # because 1 == True, i.e. 1 is in allowed
        (False, False, False),  # no value passes the strict type checking
        (False, True, False),   # similar to input1
        (True, True, True),     # each value will be converted to bool
        ]
    OUTPUT = [
        (False, 1, 1),
        (False, False, False),
        (False, True, True),
        (False, True, True),
        ]
    for inp, acc_list, out_list in zip(inputs, ACCEPTED, OUTPUT):
        inp.event('put', value=inp.initdef)     # reset to default
        for val, acc, out in zip(VALUES, acc_list, out_list):
            assert inp.event('put', value=val) is acc
            assert inp.output == out

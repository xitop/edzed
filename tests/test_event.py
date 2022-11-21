"""
Test SBlock events and event filters.
"""

# pylint: disable=missing-docstring, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_delivery(circuit):
    """Test event delivery."""
    dest = EventMemory('dest')
    init(circuit)

    assert dest.output is None
    dest.event('E1', mark=1)
    assert dest.output == ('E1', {'mark': 1})
    dest.event('E2', mark=2, extra=True)
    assert dest.output == ('E2', {'mark': 2, 'extra': True})
    dest.event('put', value=10)
    assert dest.output == ('put', {'value': 10})
    dest.put(42)   # shortcut for dest.event('put', value=42)
    assert dest.output == ('put', {'value': 42})


def test_error_checking(circuit):
    dest = edzed.Input('dest', initdef=0)
    init(circuit)

    with pytest.raises(TypeError, match="string"):
        dest.event(333)     # event name must be a string or a EventType
    with pytest.raises(ValueError, match="empty"):
        dest.event('')
    with pytest.raises(edzed.EdzedUnknownEvent):
        dest.event("no_such_event")
    with pytest.raises(edzed.EdzedUnknownEvent):
        dest.event("no_such_event")


def test_send(circuit):
    """Test event sending."""
    dest = EventMemory('dest')
    event = edzed.Event(dest, 'msg')
    src = Noop('mysrc', comment="fake event source")
    init(circuit)

    event.send(src)      # 'source' is added automatically
    assert dest.output == ('msg', {'source': 'mysrc'})
    # pylint: disable=redundant-keyword-arg
    event.send(src, source='fake_source')   # will be replaced by real source
    assert dest.output == ('msg', {'source': 'mysrc'})
    event.send(src, msg='error', level=10)
    assert dest.output == ('msg', {'source': 'mysrc', 'msg': 'error', 'level': 10})


def test_any_name(circuit):
    """No reserved names (workaround for a limitation of Python < 3.8 was required)."""
    dest = EventMemory('dest')
    event = edzed.Event(dest, 'msg')
    src = Noop('mysrc', comment="fake event source")
    init(circuit)

    # pylint: disable=redundant-keyword-arg
    event.send(src, self='SELF', etype='ETYPE', source='anything')
    assert dest.output == ('msg', {'source': 'mysrc', 'self': 'SELF', 'etype': 'ETYPE'})


def test_no_cross_circuit_events(circuit):
    inp1 = edzed.Input('inp', comment="circuit 1", initdef=None)
    event = edzed.Event(inp1)
    init(circuit)
    event.send(inp1, value=1)
    assert inp1.output == 1

    edzed.reset_circuit()
    inp2 = edzed.Input('inp', comment="circuit 2", initdef=None)
    init(circuit)
    with pytest.raises(edzed.EdzedCircuitError, match="not in the current circuit"):
        event.send(inp2, value=2)


def test_dest_name(circuit):
    """Destination block names gets resolved."""
    edzed.Input('src', on_output=edzed.Event('event_dest_block_name'), initdef='ok')
    dest = EventMemory('event_dest_block_name')
    init(circuit)

    assert dest.output == (
        'put', {'source': 'src', 'trigger': 'output', 'previous': edzed.UNDEF, 'value': 'ok'})


def test_on_output(circuit):
    """Test that on_output generates events."""
    dest = EventMemory('dest')
    src = edzed.Input(
        'src',
        check=lambda x: x != 'NO!',
        on_output=edzed.Event(dest, etype='ev'),
        initdef=None)
    init(circuit)

    CDATA = {'source': 'src', 'trigger': 'output'}
    src.put(0)
    assert dest.output == ('ev', {**CDATA, 'previous': None, 'value': 0})
    src.put(911)
    assert dest.output == ('ev', {**CDATA, 'previous': 0, 'value': 911})
    src.put('string')
    assert dest.output == ('ev', {**CDATA, 'previous': 911, 'value': 'string'})

    dest.event('clear')
    src.put('string')    # same value, no change, no output event
    assert dest.output == ('clear', {})
    src.put('NO!')       # forbidden value (check=...), no output event
    assert dest.output == ('clear', {})

    src.put(0)
    assert dest.output == ('ev', {**CDATA, 'previous': 'string', 'value': 0})


def test_on_every_output(circuit):
    """Test that on_output generates events."""
    dest = EventMemory('dest')
    dest_every = EventMemory('dest_every')
    src = edzed.Input(
        'src',
        on_output=edzed.Event(dest, etype='ev'),
        on_every_output=edzed.Event(dest_every, etype='ev'),
        initdef=None)
    init(circuit)

    CDATA = {'source': 'src', 'trigger': 'output'}
    src.put(0)
    assert dest.output == dest_every.output == ('ev', {**CDATA, 'previous': None, 'value': 0})
    src.put(911)
    assert dest.output == dest_every.output == ('ev', {**CDATA, 'previous': 0, 'value': 911})
    dest.event('ev', cleared=True)
    dest_every.event('ev', cleared=True)
    src.put(911)
    assert dest.output == ('ev', {'cleared': True})
    assert dest_every.output == ('ev', {**CDATA, 'previous': 911, 'value': 911})


def test_multiple_events(circuit):
    """Test multiple events."""
    dest1 = EventMemory('dest2')
    dest2 = EventMemory('dest1')
    src = edzed.Input(
        'src', on_output=[
            edzed.Event(dest=dest1, etype='ev1'),
            edzed.Event(dest=dest2, etype='ev2')
            ],
        initdef=None)
    init(circuit)

    CDATA = {'source': 'src', 'trigger': 'output'}
    src.put(0)
    assert dest1.output == ('ev1', {**CDATA, 'previous': None, 'value': 0})
    assert dest2.output == ('ev2', {**CDATA, 'previous': None, 'value': 0})
    src.put(911)
    assert dest1.output[1] == dest2.output[1] == {**CDATA, 'previous': 0, 'value': 911}
    src.put('last')
    assert dest1.output[1] == dest2.output[1] == {**CDATA, 'previous': 911, 'value': 'last'}


def test_conditional_events(circuit):
    """Test conditional events."""
    assert edzed.EventCond('T', 'F') == edzed.EventCond(efalse='F', etrue='T')

    cnt = edzed.Counter('counter')
    init(circuit)

    assert cnt.output == 0
    cnt.event(edzed.EventCond('inc', 'dec'), value=True)
    assert cnt.output == 1
    cnt.event(edzed.EventCond('inc', 'dec'), value=10)
    assert cnt.output == 2
    cnt.event(edzed.EventCond('inc', None), value='yes')
    assert cnt.output == 3
    cnt.event(edzed.EventCond(None, 'inc'), value=33)
    assert cnt.output == 3
    cnt.event(edzed.EventCond('inc', 'dec'), value=False)
    assert cnt.output == 2
    cnt.event(edzed.EventCond('inc', None), value=0)
    assert cnt.output == 2
    cnt.event(edzed.EventCond(None, None), value=True)
    assert cnt.output == 2
    cnt.event(edzed.EventCond(None, None), value=False)
    assert cnt.output == 2


def test_nested_conditional_events(circuit):
    """Test tested conditional events (an edge case that nobody needs)."""
    cnt = edzed.Counter('counter')
    init(circuit)

    assert cnt.output == 0
    cnt.event(edzed.EventCond(edzed.EventCond('inc', 'ERR'), None), value=True)
    assert cnt.output == 1
    cnt.event(edzed.EventCond(
        'ERR', edzed.EventCond(None, edzed.EventCond('ERR', 'dec'))), value=0)
    assert cnt.output == 0


def test_init_by_event(circuit):
    """Test initialization by an event."""
    src = edzed.Input('src', on_output=edzed.Event('dest'), initdef='ok')
    dest = edzed.Input('dest', on_output=edzed.Event('mem'))    # note: no inittdef=... !
    mem = EventMemory('mem')
    init(circuit)

    assert src.output == dest.output == 'ok'
    assert mem.output == (
        'put', {'source': 'dest', 'trigger': 'output', 'previous': edzed.UNDEF, 'value': 'ok'})


def test_no_circular_init_by_event(circuit):
    """Circular (recursive in general) events are forbidden."""
    inp_a = edzed.Input('inp_a', on_output=edzed.Event('inp_b'), initdef='ok')
    inp_b = edzed.Input('inp_b', on_output=edzed.Event('inp_a'))    # cannot send back to inp_a

    with pytest.raises(edzed.EdzedCircuitError, match="Forbidden recursive event"):
        init(circuit)

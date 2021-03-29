"""
Test SBlock events and event filters.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
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
    with pytest.raises(ValueError):
        dest.event("no_such_event")
    with pytest.raises(ValueError):
        dest.event("no_such_event")


def test_send(circuit):
    """Test event sending."""
    dest = EventMemory('dest')
    event = edzed.Event(dest, 'msg')
    src = Noop('mysrc', comment="fake event source")
    init(circuit)

    event.send(src)      # 'source' is added automatically
    assert dest.output == ('msg', {'source': 'mysrc'})
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
    with pytest.raises(edzed.EdzedError, match="not in the current circuit"):
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

    with pytest.raises(edzed.EdzedError, match="Forbidden recursive event"):
        init(circuit)


def test_filter(circuit):
    """Test event filter."""
    def even_numbers_only(data):
        return data.get('value', 1) % 2 == 0

    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input('src', on_output=edzed.Event(dest, efilter=even_numbers_only), initdef=0)
    init(circuit)

    assert src.output == 0
    assert dest.output == 0
    src.put(1)
    assert src.output == 1
    assert dest.output == 0
    src.put(8)
    assert src.output == 8
    assert dest.output == 8
    src.put(33)
    assert src.output == 33
    assert dest.output == 8


def test_filter_pipe(circuit):
    """Test a pipe of event filters."""
    def new_X(data):
        return {'new': 'X', **data}
    def add_Y(data):
        return {**data, 'new': data['new'] + 'Y'}
    def add_Z(data):
        # modify in place
        data['new'] += 'Z'
        return data
    def add_qmark(data):
        return {**data, 'new': data['new'] + '?'}
    def del_previous(data):
        del data['previous']
        return data

    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            'dest',
            efilter=(new_X, add_Y, add_Z, add_qmark, add_qmark, del_previous)),
        initdef=None)
    dest = EventMemory('dest')
    init(circuit)

    src.put('V')
    assert dest.output == (
        'put', {'source': 'src', 'trigger': 'output', 'value': 'V', 'new': 'XYZ??'})


def test_no_chained_edit():
    """Chaining of event data edit functions is disallowed."""
    with pytest.raises(AttributeError):
        edzed.DataEdit.add(a=0).delete('b')
    with pytest.raises(AttributeError):
        edzed.DataEdit.permit('a', 'b').add(c=1).require('d')


def test_dataedit_filter(circuit):
    """Test the DataEdit helper."""
    def check(expected):
        def _check(data):
            assert data == expected
            return data
        return _check

    CDATA = {'source': 'src', 'trigger': 'output'}
    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            'dest',
            efilter=(
                edzed.not_from_undef,
                check({**CDATA, 'previous': None, 'value': 'V'}),
                edzed.DataEdit.copy('value', 'saved'),
                check({**CDATA, 'previous': None, 'value': 'V', 'saved': 'V'}),
                edzed.DataEdit.add(a=1, b=2, c=3),
                check({
                    **CDATA,
                    'previous': None, 'value': 'V', 'saved': 'V', 'a': 1, 'b': 2, 'c': 3}),
                edzed.DataEdit.permit('source', 'saved', 'a'),
                check({'source': 'src', 'saved': 'V', 'a': 1}),
                edzed.DataEdit.copy('saved', 'value'),
                check({'source': 'src', 'saved': 'V', 'value': 'V', 'a': 1}),
                edzed.DataEdit.default(saved='NO'),
                check({'source': 'src', 'saved': 'V', 'value': 'V', 'a': 1}),
                edzed.DataEdit.delete('saved'),
                check({'source': 'src', 'value': 'V', 'a': 1}),
                edzed.DataEdit.modify('a', lambda x: x+50),
                check({'source': 'src', 'value': 'V', 'a': 51}),
                edzed.DataEdit.default(saved='YES'),
                check({'source': 'src', 'saved': 'YES', 'value': 'V', 'a': 51}),
                edzed.DataEdit.default(saved='MAYBE'),
            )),
        initdef=None)
    dest = EventMemory('dest')
    init(circuit)

    src.put('V')
    assert dest.output == ('put', {'source': 'src', 'value': 'V', 'a': 51, 'saved': 'YES'})


def test_edge_detector_from_undef(circuit):
    """Test the edge detector's parameters u_rise, u_fall."""
    setup = []
    i = 0
    for value in (False, True):
        for ur in (False, True, None):
            for uf in (False, True):
                for r in (False, True):
                    dest = edzed.Input(f'test_event_{i}', initdef=None)
                    edzed.Input(
                        f"test_edge_{i}",
                        on_output=edzed.Event(
                            dest, efilter=edzed.Edge(rise=r, u_rise=ur, u_fall=uf)),
                        initdef=value
                        )
                    if ur is None:
                        ur = r
                    event = ur if value else uf
                    result = value if event else None
                    setup.append((dest, result, (value, ur, uf, r)))
                    i += 1
    init(circuit)
    for dest, result, args in setup:
        assert dest.output is result, f"failed for (value, u_rise, u_fall, rise) = {args}"


def test_edge_detector(circuit):
    """Test the edge detector's parameters rise and fall."""
    SEQ1 = (False, True, False, True, False, True, False, True)
    SEQ2 = (True, False, True, False, True)

    cnt = edzed.Counter('counter')
    i = 0
    setup = []
    for r in (False, True):
        for f in (False, True):
            inp1 = edzed.Input(
                f"test{i}_seq1",
                on_output=edzed.Event(cnt, 'inc', efilter=edzed.Edge(rise=r, fall=f)),
                initdef=SEQ1[0]
                )
            inp2 = edzed.Input(
                f"test{i}_seq2",
                on_output=edzed.Event(cnt, 'inc', efilter=edzed.Edge(rise=r, fall=f)),
                initdef=SEQ2[0]
                )
            s1 = s2 = 0     # s1, s2 = expected event count for SEQ1, SEQ2
            if r:
                s1 += 4     # 4 rising edges
                s2 += 2     # 3 rising edges, but 1 of them is initial
                            # and is counted immediately at the block creation
            if f:
                s1 += 3     # 4 falling edges, but 1 of them is initial
                            # and is suppressed by uf=False (default)
                s2 += 2     # 2 falling edges
            setup.append((inp1, SEQ1, s1, (r, f)))
            setup.append((inp2, SEQ2, s2, (r, f)))
            i += 1
    init(circuit)
    assert cnt.output == 2  # 2 times the initial rising edge of S2R1F10 and S2R1F1

    for inp, seq, result, args in setup:
        cnt.put(0)
        assert cnt.output == 0
        for val in seq:
            inp.put(val)
        assert cnt.output == result, f"failed for {inp.name}, (rise, fall) = {args}"


def test_not_from_undef(circuit):
    """Test the not_from_undef filter."""
    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input(
        'src',
        on_output=edzed.Event(dest, efilter=edzed.not_from_undef),
        initdef=1)
    init(circuit)

    assert src.output == 1
    assert dest.output is None  # UNDEF -> 1 suppressed by the filter
    src.put(3)
    assert src.output == 3
    assert dest.output == 3
    src.put(5)
    assert src.output == 5
    assert dest.output == 5


def test_delta(circuit):
    """Test the Delta filter."""
    trace = []
    def tee(data):
        trace.append(data['value'])
        return data

    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input(
        'src',
        on_output=edzed.Event(dest, efilter=[edzed.Delta(1.7), tee]),
        initdef=0)
    init(circuit)

    for num in (0, 1, 0, 2, 3.69, 3.71, 5, 6, 7, 8, 15, 13.5, 16.5, 12):
        src.put(num)
    assert trace == [0, 2, 3.71, 6, 8, 15, 12]
    assert dest.output == 12


def test_event_handlers(circuit):
    """test event_ETYPE."""
    class B0:
        # not defined in a SBlock or Addon subclass -> ignored
        def _event_X(self, **data):
            return

    class B1(edzed.SBlock):
        def _event_add(self, value=0, **data):
            self.set_output(self.output + value)

        def _event_sub(self, value=0, **data):
            self.set_output(self.output - value)

        def init_regular(self):
            self.set_output(0)

    class B2(B0, B1):
        def _event_sub(self, value=0, **data):
            # redefining sub
            self.set_output(self.output - 2*value)

    addsub = B2('addsub')
    init(circuit)

    assert addsub.output == 0
    addsub.event('add', value=10)
    assert addsub.output == 10
    addsub.event('sub', value=1)
    assert addsub.output == 8       # 2*value
    with pytest.raises(ValueError):
        addsub.event('X')


def test_reset(circuit):
    """Verify that events to be resolved are cleared by reset_circuit."""
    Noop('c1')
    ev1 = edzed.Event('c1')

    # simulation not started, event destination names remain unresolved
    assert ev1 in edzed.Event.instances
    edzed.reset_circuit()
    assert ev1 not in edzed.Event.instances

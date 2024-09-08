"""
Test SBlock events and event filters.
"""

# pylint: disable=missing-class-docstring, protected-access

import pytest

import edzed

# pylint: disable-=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import init, Noop, EventMemory


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
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
    dest.put(42)   # shortcut for dest.event('put', value=42), deprecated since 23.8.25
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


def test_attrs(circuit):
    """Test Event attributes."""
    etype = 'abc'
    ev_name = edzed.Event('input', etype)   # forward references supported
    inp = edzed.Input('input', initdef=0)
    ev_obj = edzed.Event(inp, etype)

    assert ev_obj.etype == ev_name.etype == etype
    assert ev_obj.dest == inp
    with pytest.raises(edzed.EdzedInvalidState):    # names not resolved yet
        assert ev_name.dest == inp
    init(circuit)
    assert ev_name.dest == inp                      # names resolved
    with pytest.raises(AttributeError):     # read-only
        ev_obj.etype = None
    with pytest.raises(AttributeError):     # read-only
        ev_obj.dest = None


def test_ext_args(circuit):
    """Test ExtEvent args."""
    with pytest.raises(LookupError):        # forward references not supported
        edzed.ExtEvent('input', 'ename')
    inp = edzed.Input('input', initdef=0)
    edzed.ExtEvent('input', 'ename')
    cond = edzed.EventCond(None, None)
    edzed.Event(inp, cond)                  # Event + EventType = OK, but ...
    with pytest.raises(TypeError):
        edzed.ExtEvent(inp, cond)           # ... ExtEvent + EventType = error!
    with pytest.raises(TypeError):
        edzed.ExtEvent(inp, source=113)     # not a string


def test_ext_attrs(circuit):
    """Test ExtEvent attributes."""
    etype = 'eee'
    inp = edzed.Input('input', initdef=0)
    ev_name = edzed.ExtEvent('input', etype)
    ev_obj = edzed.ExtEvent(inp, etype)
    assert ev_obj.etype == ev_name.etype == etype
    assert ev_obj.dest == ev_name.dest == inp
    with pytest.raises(AttributeError):     # read-only
        ev_obj.etype = None
    with pytest.raises(AttributeError):     # read-only
        ev_obj.dest = None


def test_ext_source(circuit):
    """Test ExtEvent source handling."""
    dest = EventMemory('dest')
    init(circuit)

    assert edzed.ExtEvent(dest)._source == '_ext_'
    assert edzed.ExtEvent(dest, source='device')._source == '_ext_device'
    assert edzed.ExtEvent(dest, source='_ext_HAL9000')._source == '_ext_HAL9000'

    srcput = edzed.ExtEvent(dest, source='default').send
    nosrcput = edzed.ExtEvent(dest, etype='put').send
    srcput(1)
    assert dest.output == ('put', {'source':'_ext_default', 'value':1})
    srcput(2, source='send')
    assert dest.output == ('put', {'source':'_ext_send', 'value':2})
    srcput(source='send3', value=3)
    assert dest.output == ('put', {'source':'_ext_send3', 'value':3})
    srcput(x=4, source='send4')
    assert dest.output == ('put', {'source':'_ext_send4', 'x':4})
    nosrcput(5)
    assert dest.output == ('put', {'source':'_ext_', 'value':5})
    nosrcput(source='send6', y=6)
    assert dest.output == ('put', {'source':'_ext_send6', 'y':6})
    nosrcput(7, source='_ext_send7', b=True)
    assert dest.output == ('put', {'source':'_ext_send7', 'value':7, 'b':True})


def test_send(circuit):
    """Test event sending."""
    dest = EventMemory('dest')
    event = edzed.Event(dest, 'msg')
    src = Noop('mysrc', comment="fake event source")
    init(circuit)

    event.send(src)      # 'source' is added automatically
    assert dest.output == ('msg', {'source': 'mysrc'})
    # pylint: disable=kwarg-superseded-by-positional-arg
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

    # pylint: disable=kwarg-superseded-by-positional-arg
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
    eput = edzed.ExtEvent(src).send
    eput(0)
    assert dest.output == ('ev', {**CDATA, 'previous': None, 'value': 0})
    eput(911)
    assert dest.output == ('ev', {**CDATA, 'previous': 0, 'value': 911})
    eput('string')
    assert dest.output == ('ev', {**CDATA, 'previous': 911, 'value': 'string'})

    edzed.ExtEvent(dest, 'clear').send(source='master')
    eput('string')    # same value, no change, no output event
    assert dest.output == ('clear', {'source':'_ext_master'})
    eput('NO!')       # forbidden value (check=...), no output event
    assert dest.output == ('clear', {'source':'_ext_master'})

    eput(0)
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

    src_put = edzed.ExtEvent(src).send
    CDATA = {'source': 'src', 'trigger': 'output'}
    src_put(0)
    assert dest.output == dest_every.output == ('ev', {**CDATA, 'previous': None, 'value': 0})
    src_put(911)
    assert dest.output == dest_every.output == ('ev', {**CDATA, 'previous': 0, 'value': 911})
    dest.event('ev', cleared=True)
    dest_every.event('ev', cleared=True)
    src_put(911)
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

    src_put = edzed.ExtEvent(src).send
    CDATA = {'source': 'src', 'trigger': 'output'}
    src_put(0)
    assert dest1.output == ('ev1', {**CDATA, 'previous': None, 'value': 0})
    assert dest2.output == ('ev2', {**CDATA, 'previous': None, 'value': 0})
    src_put(911)
    assert dest1.output[1] == dest2.output[1] == {**CDATA, 'previous': 0, 'value': 911}
    src_put('last')
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
    # pylint: disable=unused-variable
    inp_a = edzed.Input('inp_a', on_output=edzed.Event('inp_b'), initdef='ok')
    inp_b = edzed.Input('inp_b', on_output=edzed.Event('inp_a'))    # cannot send back to inp_a

    with pytest.raises(edzed.EdzedCircuitError, match="Forbidden recursive event"):
        init(circuit)


def test_event_handlers(circuit):
    """Test event_ETYPE."""
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

    assert addsub._ct_handlers.keys() == {'add', 'sub'}

    assert addsub.output == 0
    addsub.event('add', value=10)
    assert addsub.output == 10
    addsub.event('sub', value=1)
    assert addsub.output == 8       # 2*value
    with pytest.raises(edzed.EdzedUnknownEvent):
        addsub.event('X')


@pytest.mark.asyncio
async def test_recipe(circuit):
    """Test the recipe from docs."""

    class ExtEventAuth(edzed.ExtEvent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not getattr(self.dest, 'x_input', False):
                raise ValueError(
                    f"Block {self.dest.name} is not accepting external inputs")

    inp_a = edzed.Input('inp_a', initdef=0, x_input=True)
    inp_b = edzed.Input('inp_b', initdef=1)

    async def tester():
        ExtEventAuth(inp_a, source='tester').send(value=6, wer='Steinscheißer Karl')
        assert inp_a.output == 6
        ExtEventAuth(inp_a).send(7)
        assert inp_a.output == 7
        with pytest.raises(ValueError):
            ExtEventAuth(inp_b).send(value=8)
        assert inp_b.output == 1

    await edzed.run(tester())

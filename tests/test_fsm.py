"""
Test FSM blocks.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_basic_state_transition(circuit):
    """Test the basic FSM function."""
    class B123(edzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', ['S1'], 'S2'),
            ['step', None, 'S3'],   # default rule has lower precedence
            ('step', 'S3', 'S1')    # single state does need to be within a sequence
            ]
        def calc_output(self):
            return int(self.state[1]) # 1, 2 or 3

    b123x = B123('b123fsm_S1')
    b123y = B123('b123fsm_S3', initdef='S3')  # test initial state
    init(circuit)

    assert b123x.state == 'S1'
    assert b123x.output == 1

    b123x.event('step')
    assert b123x.state == 'S2'
    assert b123x.output == 2

    b123x.event('step')
    assert b123x.state == b123y.state == 'S3'
    assert b123x.output == b123y.output == 3

    b123x.event('step')
    b123y.event('step')
    assert b123x.state == b123y.state == 'S1'
    assert b123x.output == b123y.output == 1


def test_no_states(circuit):
    with pytest.raises(ValueError, match="no states"):
        class E1(edzed.FSM):
            pass


def test_invalid_names(circuit):
    with pytest.raises(ValueError, match='empty'):
        class E1(edzed.FSM):
            STATES = ['']

    with pytest.raises(ValueError, match='empty'):
        class E2(edzed.FSM):
            STATES = ['X']
            EVENTS = [('', 'X', 'X')]

    with pytest.raises(ValueError, match='Ambiguous'):
        class E3(edzed.FSM):
            STATES = ['X']
            EVENTS = [('FOO', 'X', 'X')]        # FSM event 'FOO'
            def _event_FOO(self, **kwargs):     # non-FSM event 'FOO'
                pass

    with pytest.raises(TypeError):
        class E4(edzed.FSM):
            STATES = [5]
            EVENTS = [('E', 'X', 'X')]

    with pytest.raises(TypeError):
        class E5(edzed.FSM):
            STATES = ['X']
            EVENTS = [(None, 'X', 'X')]


def test_goto(circuit):
    """Test the Goto special event."""
    class B123(edzed.FSM):
        STATES = ('S1', 'S2', 'S3')
        EVENTS = [
            ('step', 'S1', 'S2'),
            ('step', 'S2', 'S3'),
            ('step', 'S3', 'S1')
            ]

    b123 = B123('b123fsm')
    init(circuit)

    assert b123.state == 'S1'

    b123.event('step')
    assert b123.state == 'S2'

    b123.event(edzed.Goto('S1'))
    assert b123.state == 'S1'

    with pytest.raises(ValueError, match="Unknown state"):
        b123.event(edzed.Goto('S99'))


def test_conditional_goto(circuit):
    """Test the EventCond + Goto combination."""
    # Note: Goto(EventCond(...)) is wrong, Goto expects an FSM state, not an event
    class B4(edzed.FSM):
        STATES = ('A', 'B', 'C', 'D')

    b4 = B4('4states')
    init(circuit)

    event = edzed.EventCond(edzed.Goto('B'), edzed.Goto('D'))
    b4.event(event, value=False)
    assert b4.state == 'D'
    b4.event(event, value=True)
    assert b4.state == 'B'


def test_enter_exit_cb(circuit):
    """Test the state action callbacks."""
    log = []

    class B123(edzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', 'S1', 'S2'),
            ('step', 'S2', 'S3'),
            ('step', 'S3', 'S1')
            ]
        def enter_S1(self):
            log.append('+S1m')
        def exit_S1(self):
            log.append('-S1m')
        def enter_S2(self):
            log.append('+S2m')
        def exit_S2(self):
            log.append('-S2m')

    b123 = B123(
        'b123fsm',
        enter_S2=lambda: log.append('+S2f'),
        enter_S3=lambda: log.append('+S3f'), exit_S3=lambda: log.append('-S3f'))

    init(circuit)

    assert log == ['+S1m']
    log.clear()

    b123.event('step')
    # f (function) before m (method) or vice versa
    assert log in (['-S1m', '+S2f', '+S2m'], ['-S1m', '+S2m', '+S2f'])
    log.clear()

    b123.event('step')
    assert log == ['-S2m', '+S3f']
    log.clear()

    b123.event('step')
    assert log == ['-S3f', '+S1m']


def test_no_callback_without_state():
    """Test the state action callbacks."""
    class B123(edzed.FSM):
        STATES = ['S0']

    with pytest.raises(TypeError, match="invalid keyword argument"):
        B123('wrong_callback1', enter_S99=lambda: None)
    with pytest.raises(TypeError, match="invalid keyword argument"):
        B123('wrong_callback2', exit_S7=lambda: None)


def test_cond(circuit):
    """Test the cond_EVENT."""
    enable = True
    class B123(edzed.FSM):
        STATES = 'S1 S2 S3'.split()
        EVENTS = [
            ('step', 'S1', 'S2'),
            ('step', 'S2', 'S3'),
            ('step', 'S3', 'S1')
            ]
        def cond_step(self):
            data = edzed.fsm_event_data.get()
            return data.get('passwd') == 'secret123'

    b123 = B123('b123fsm', cond_step=lambda: enable)
    init(circuit)

    assert b123.state == 'S1'

    assert not b123.event('step')   # rejected
    assert b123.state == 'S1'
    assert not b123.event('step', passwd='guess')   # rejected
    assert b123.state == 'S1'
    assert b123.event('step', passwd='secret123')   # accepted
    assert b123.state == 'S2'
    enable = False
    assert not b123.event('step', passwd='secret123')   # rejected
    assert b123.state == 'S2'


def test_transition_chaining(circuit):
    """Test the chained transition A->B->C->D."""
    class ABCD(edzed.FSM):
        STATES = ['A', 'B', 'C', 'D']
        EVENTS = [
            ('start', ['A'], 'B')
            ]
        def enter_B(self):
            self.event(edzed.Goto('C'))
        def enter_C(self):
            self.event(edzed.Goto('D'))
        def calc_output(self):
            assert self.state not in ('B', 'C')    # no output for intermediate states
            return f'in_{self.state}'

    abcd = ABCD(
        'abcd',
        on_enter_B=edzed.Event('mem', '+B'),
        on_exit_B=edzed.Event('mem', '-B'),
        on_enter_C=edzed.Event('mem', '+C'),
        on_exit_C=edzed.Event('mem', '-C'),
        on_exit_D=edzed.Event('mem', '-D'),
        )
    mem = EventMemory('mem')
    init(circuit)

    assert abcd.state == 'A'
    assert abcd.output == 'in_A'
    assert mem.output is None
    abcd.event('start')
    assert abcd.state == 'D'
    assert abcd.output == 'in_D'
    assert mem.output is None   # no events for intermediate states
    abcd.event(edzed.Goto('A'))
    assert abcd.state == 'A'
    assert abcd.output == 'in_A'
    assert mem.output == (
        '-D',
        {'source': 'abcd', 'trigger': 'exit', 'state': 'D', 'sdata': {}, 'value': 'in_D'}
        )


def test_no_multiple_next_states(circuit):
    """Only one event call is allowed when chaining transitions."""
    class ABC(edzed.FSM):
        STATES = ['A', 'B', 'C']
        EVENTS = [
            ('start', ['A'], 'B')
            ]
        def enter_B(self):
            self.event(edzed.Goto('C'))     # this is OK
            self.event(edzed.Goto('C'))     # but only once!

    abc = ABC('abc')
    init(circuit)

    with pytest.raises(edzed.EdzedCircuitError, match="event multiplication"):
        abc.event('start')


def test_no_transition_chaining1(circuit):
    """Test forbidden chained transition"""
    class ABC(edzed.FSM):
        STATES = ['A', 'B', 'C']
        EVENTS = [
            ('start', ['A'], 'B')
            ]
        def exit_A(self):
            self.event(edzed.Goto('C'))     # can't do this in exit_STATE (only in enter_STATE)

    abc = ABC('abc')
    init(circuit)

    with pytest.raises(edzed.EdzedCircuitError, match='Forbidden recursive event'):
        abc.event('start')


def test_no_transition_chaining2(circuit):
    """Test forbidden chained transition"""
    class ABC(edzed.FSM):
        STATES = ['A', 'B', 'C']
        EVENTS = [
            ('start', ['A'], 'B')
            ]

    # a FSM can't send events to itself this way
    abc = ABC('abc', on_enter_B=edzed.Event('abc', edzed.Goto('C')))
    init(circuit)

    with pytest.raises(edzed.EdzedCircuitError, match='Forbidden recursive event'):
        abc.event('start')


def test_no_infinite_loop(circuit):
    """Test the chained transition limit."""
    class AB(edzed.FSM):
        STATES = ['init', 'A', 'B']
        EVENTS = [
            ('start', ['init'], 'A')
            ]
        def enter_A(self):
            self.event(edzed.Goto('B'))
        def enter_B(self):
            self.event(edzed.Goto('A'))

    ab = AB('ab loop')
    init(circuit)

    with pytest.raises(edzed.EdzedCircuitError, match='infinite loop?'):
        ab.event('start')


def test_persistent_state(circuit):
    class Dummy(edzed.FSM):
        STATES = list("ABCDEF")

    def forbidden():
        assert False

    mem = EventMemory('mem')
    fsm = Dummy(
        'test', persistent=True,
        enter_D=forbidden, on_enter_D=edzed.Event(mem, '+D'),
        on_exit_D=edzed.Event(mem, '-D')
        )
    assert fsm.key == "<Dummy 'test'>"
    storage = {fsm.key: ['D', None, {'x':'y', '_z':3}]}    # (state, timer, sdata)
    circuit.set_persistent_data(storage)
    # enter_D and on_enter_D will be suppressed
    init(circuit)
    assert fsm.sdata == {'x':'y', '_z':3}

    assert fsm.state == 'D'
    assert mem.output is None

    fsm.event(edzed.Goto('F'))
    assert mem.output == (
        '-D',
        # '_z' is not present in 'sdata', because it is considered private
        {'source': 'test', 'trigger': 'exit', 'state': 'D', 'sdata': {'x':'y'}, 'value': 'D'}
        )
    del fsm.sdata['x']
    assert storage == {fsm.key: ('F', None, {'_z':3})}


def test_read_only_data(circuit):
    class Simple(edzed.FSM):
        STATES = ['st0', 'st1']
        EVENTS = [('ev01', None, 'st1')]

        def cond_ev01(self):
            data = edzed.fsm_event_data.get()
            with pytest.raises(TypeError):
                data['new_item'] = 0
            assert data['a'] == 1
            return True

    simple = Simple('simple')
    init(circuit)
    assert simple.state == 'st0'
    simple.event('ev01', a=1)
    assert simple.state == 'st1'


def test_context(circuit):
    """Each event being handled has its own context."""
    class Simple(edzed.FSM):
        STATES = ['st0', 'st1']
        EVENTS = [('ev01', None, 'st1')]

        def cond_ev01(self):
            data = edzed.fsm_event_data.get()
            assert data['sent_to'] == self.name
            return True

    afsm = Simple(
        'A', on_enter_st1=edzed.Event('B', 'ev01', efilter=edzed.DataEdit.add(sent_to='B')))
    bfsm = Simple(
        'B', on_enter_st1=edzed.Event('C', 'ev01', efilter=edzed.DataEdit.add(sent_to='C')))
    cfsm = Simple('C')

    init(circuit)
    afsm.event('ev01', sent_to='A')     # A -> B -> C
    assert cfsm.state == 'st1'

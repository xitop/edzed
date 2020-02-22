"""
Event driven finite-state machine (FSM) extended with optional timers.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import asyncio
import collections
import collections.abc as cabc
import contextvars
from dataclasses import dataclass
import time
import types
from typing import Optional, Sequence, Tuple, Union

from . import addons
from . import block
from .exceptions import EdzedError
from .utils import looptimes
from .utils import timeunits


__all__ = ['convert_duration', 'fsm_event_data', 'FSM', 'Goto', 'INF_TIME']

INF_TIME = float('+inf')
fsm_event_data = contextvars.ContextVar('fsm_event_data')


def convert_duration(duration: Union[None, int, float, str]) -> Optional[float]:
    """Convenience wrapper for timeunits.convert()."""
    if duration is None:
        return None
    if isinstance(duration, int):
        duration = float(duration)
    if isinstance(duration, float):
        return max(0.0, duration)
    if isinstance(duration, str):
        return timeunits.convert(duration)
    raise ValueError(f"Invalid duration value: {duration!r}")


@dataclass(frozen=True)
class Goto(block.EventType):
    """A special event causing a direct state transition."""
    __slots__ = ['str']
    state: str


class FSM(addons.AddonPersistence, block.SBlock):
    """
    A base class for a Finite-state Machine with optional timers.
    """

    # subclasses should define:
    STATES = ()
    TIMERS = {}
    EVENTS = ()

    @classmethod
    def _check_state(cls, state):
        if state not in cls._ct_states:
            raise ValueError(f"Unknown state '{state}'")

    @classmethod
    def _build_tables(cls):
        """
        Build control tables from STATES, TIMERS and EVENTS.

        The original tables are left unchanged.
        """
        def add_transition(event, from_state, next_state):
            if from_state is not None:
                cls._check_state(from_state)
            key = (event, from_state)
            if key in cls._ct_transition:
                raise ValueError(
                    "Multiple transition definition for "
                    f"event {event!r} in state {from_state!r}")
            cls._ct_transition[key] = next_state

        # control tables must be created for each subclass
        # '_ct' (control table) prefix chosen to make a name clash unlikely
        cls._ct_states = set(cls.STATES).union(cls.TIMERS)  # all known states
        cls._ct_events = set()      # all known events
        cls._ct_transition = {}     # {(event, state): next_state}
        cls._ct_default_duration = {}   # {timed_state: duration_in_seconds_or_None}
        cls._ct_timed_event = {}        # {timed_state: event_on_timer_expiration}
        cls._ct_methods = {
            'enter': {},            # {state: enter_cb}
            'exit': {},             # {state: exit_cb}
            'cond': {},             # {event: cond_cb}
            }

        # prepare data for keyword argument parsing in __init__
        cls._ct_prefixes = [
            # prefix, prefix length, valid names (i.e. without the prefix) to check
            ('t_', 2, cls._ct_default_duration),
            ('cond_', 5, cls._ct_events),
            ('enter_', 6, cls._ct_states),
            ('exit_', 5, cls._ct_states),
            ('on_enter_', 9, cls._ct_states),
            ('on_exit_', 8, cls._ct_states),
            ]

        if isinstance(cls.STATES, str):
            # catch a frequent error: 'x' or ('x') instead of ('x',)
            # Note that this condition does not mean a single
            # state FSM - other states may be timed.
            raise ValueError(
                f"STATES: expected is a sequence of strings, did you mean: [{cls.STATES}] ?")

        if cls.STATES:
            cls._ct_default_state = cls.STATES[0]
        else:
            if not cls.TIMERS:
                raise ValueError("Cannot create a state machine with no states")
            # the TIMERS is a dict and dicts are ordered since Python 3.7
            cls._ct_default_state = next(iter(cls.TIMERS))  # the first key

        for state in cls._ct_states:
            block.checkname(state, "FSM state name")
        cls._ct_chainlimit = 3 * len(cls._ct_states)    # limit for chained transitions

        for event, from_states, next_state in cls.EVENTS:
            block.checkname(event, "FSM event name")
            if event in cls._ct_handlers:
                raise ValueError(
                    f"Ambiguous event '{event}': "
                    "the name is used for both FSM and SBlock event")
            cls._ct_events.add(event)
            if next_state is not None:
                cls._check_state(next_state)
            if from_states is None or isinstance(from_states, str):
                add_transition(event, from_states, next_state)
            else:
                for fstate in from_states:
                    add_transition(event, fstate, next_state)

        for state, (duration, event) in cls.TIMERS.items():
            try:
                cls._ct_default_duration[state] = convert_duration(duration)
            except ValueError as err:
                raise ValueError(f"TIMERS['{state}']: {err}") from None
            if isinstance(event, Goto):
                cls._check_state(event.state)
            elif event not in cls._ct_events:
                raise ValueError(
                    f"TIMERS['{state}']: undefined event '{event}'")
            cls._ct_timed_event[state] = event

        for method_name, method in vars(cls).items():
            try:
                cb_type, name = method_name.split('_', 1)
                cb_dict = cls._ct_methods[cb_type]
            except (ValueError, KeyError):
                continue
            valid_names = cls._ct_events if cb_type == 'cond' else cls._ct_states
            if name in valid_names and callable(method):
                cb_dict[name] = method

    # TODO: https://bugs.python.org/issue38085
    def __init_subclass__(cls, *args, **kwargs):
        """
        Build control tables.
        """
        # call super().__init_subclass__ first, we will later check for possible
        # event name clashes with the _ct_handlers
        super().__init_subclass__(*args, **kwargs)

        try:
            cls._build_tables()
        except Exception as err:
            fmt = f"Cannot create FSM subclass {cls.__name__}: {{}}"
            err.args = (fmt.format(err.args[0] if err.args else "<NO ARGS>"), *err.args[1:])
            raise

    def __init__(self, *args, on_notrans=(), **kwargs):
        """
        Create FSM.

        Keyword arguments named t_STATE (where STATE is a timed state)
        override the default durations of corresponding timers for this
        single instance.

        Keyword arguments named on_enter_STATE and on_exit_STATE (where
        STATE is a known state) define events to be sent when the STATE
        is entered or exited.

        Keyword arguments named cond_EVENT (where EVENT is a known
        event) define functions with the same semantics as cond_EVENT
        methods.

        Keyword argument on_notrans defines events to be sent when
        a transition is not defined.

        FSM initialization takes place in init_regular().
        """
        if type(self) is FSM:   # pylint: disable=unidiomatic-typecheck
            raise TypeError("Can't instantiate abstract FSM class")
        prefixed = collections.defaultdict(list)
        for arg in kwargs:
            for prefix, length, valid_names in self._ct_prefixes:
                if arg.startswith(prefix):
                    name = arg[length:]  # strip prefix
                    if name in valid_names:
                        prefixed[prefix].append((name, arg))
        self._duration = self._ct_default_duration
        for name, arg in prefixed['t_']:
            self._set_duration(name, kwargs.pop(arg))
        self._fsm_functions = {
            'cond': {name: kwargs.pop(arg) for name, arg in prefixed['cond_']},
            'enter': {name: kwargs.pop(arg) for name, arg in prefixed['enter_']},
            'exit': {name: kwargs.pop(arg) for name, arg in prefixed['exit_']},
            }
        self._state_events = {
            'on_enter': {
                name: block.event_tuple(kwargs.pop(arg))
                for name, arg in prefixed['on_enter_']},
            'on_exit': {
                name: block.event_tuple(kwargs.pop(arg))
                for name, arg in prefixed['on_exit_']},
            }

        self._on_notrans = block.event_tuple(on_notrans)
        self._state = block.UNDEF
        self._active_timer = None
        self._fsm_event_active = False
        self._next_event = None     # scheduled event in chained state transition
        kwargs.setdefault('initdef', self._ct_default_state)
        super().__init__(*args, **kwargs)

    @property
    def state(self) -> str:
        """Return the FSM state."""
        return self._state

    def get_state(self) -> Tuple[str, Optional[float]]:
        """
        Return the block's internal state.

        Internal state is a pair:
            FSM state, timer state
        The timer state is either None or an expiration time given
        as UNIX timestamp.

        Returned data can be restored with _restore_state.
        """
        timer = self._active_timer
        if timer is None or timer.cancelled():
            exp_timestamp = None
        else:
            exp_timestamp = looptimes.loop_to_unixtime(timer.when())
        return (self._state, exp_timestamp)

    def _restore_state(self, istate: Sequence) -> None:
        """
        Restore the internal state created by get_state().

        cond_STATE, enter_STATE and on_enter_STATE are not executed,
        because the state was entered already in the past. Now it is
        only restored.
        """
        state, exp_timestamp = istate
        self._check_state(state)
        if exp_timestamp is not None:
            remaining = exp_timestamp - time.time()
            if remaining <= 0.0:
                self.log("restore state: ignoring expired state")
                return
            try:
                timed_event = self._ct_timed_event[state]
            except KeyError:
                raise EdzedError(
                    f"cannot set a timer for a not timed state '{state}'") from None
            self._set_timer(remaining, timed_event)
        self._state = state
        self.log("state: <UNDEF> -> %s", state)
        output = self._eval()
        if output is not block.UNDEF:
            self.set_output(output)

    def init_from_value(self, value: str) -> None:
        """Initialize the internal state."""
        self.event(Goto(value))

    def stop(self) -> None:
        """Cleanup."""
        self._stop_timer()
        super().stop()

    def _set_duration(self, timed_state: str, value: Union[None, int, float, str]) -> None:
        """
        Set the duration of a timed_state.

        _set_duration() accepts various value formats, see the docs
        for TIMERS.

        Reset to default if value is None.
        """
        ct_duration = type(self)._ct_default_duration
        if timed_state not in ct_duration:
            raise ValueError(f"{timed_state!r} is not a timed state")
        if self._duration is ct_duration:
            self._duration = ct_duration.copy()   # copy in write
        self._duration[timed_state] = \
            ct_duration[timed_state] if value is None else convert_duration(value)

    def get_duration(self, timed_state: str) -> Optional[float]:
        """
        Return the timed state duration in seconds.

        Return None if the duration is not set. This includes the case
        when the state is not timed.
        """
        return self._duration.get(timed_state)

    def _set_timer(self, duration, timed_event):
        """Start the timer (low-level)."""
        self.log("timer: %.3fs before %s", duration, timed_event)
        self._active_timer = asyncio.get_running_loop().call_later(
            duration, self.event, timed_event)

    def _start_timer(self, duration, timed_event):
        """Start the timer."""
        if duration is not None:
            duration = convert_duration(duration)
        else:
            duration = self.get_duration(self._state)
            if duration is None:
                raise EdzedError(f"Timer duration for state '{self._state}' not set")
        if duration == INF_TIME:
            return
        if duration <= 0.0:
            self.log("timer: zero delay before %s", timed_event)
            self.event(timed_event)
            return
        self._set_timer(duration, timed_event)

    def _stop_timer(self):
        """Stop the timer, if any."""
        timer = self._active_timer
        if timer is not None:
            if not timer.cancelled():
                timer.cancel()
                # do not rely on the private attribute '_scheduled'
                if getattr(timer, '_scheduled', True):
                    self.log("timer: cancelled")
            self._active_timer = None

    def _send_events(self, trigger_type, state):
        """Send events triggered by 'on_enter_STATE' or 'on_exit_STATE'."""
        state_events = self._state_events[trigger_type]
        try:
            events = state_events[state]
        except KeyError:
            return
        trigger = f'{trigger_type}_{state}'
        for event in events:
            event.send(self, trigger=trigger)

    def _run_cb(self, cb_type, name):
        """
        Run methods and callbacks 'cond', 'enter' or 'exit'.

        Access to event data is provided through the context variable
        'fsm_event_data'.

        Try the external function and the class method. Return a list
        with 0, 1 or 2 return values depending on how many functions
        were actually defined.

        Do not rely on the order of calls (the function first or
        the method first), it may change in future releases.
        """
        retvals = []
        self_cb = self._fsm_functions[cb_type]
        try:
            cb = self_cb[name]
        except KeyError:
            pass
        else:
            retvals.append(cb())
        cls_cb = self._ct_methods[cb_type]
        try:
            cb = cls_cb[name].__get__(self)      # bind the method
        except KeyError:
            pass
        else:
            retvals.append(cb())
        return retvals

    def _event_ctx(self, etype, data):
        """
        Handle event. Check validity and conditions.

        Timed states look for 'duration' key in the data. If it is
        present, the value overrides the default timer duration.

        Return value:
            True = transition accepted, either executed or scheduled
                   for execution
            False = transition rejected
        """
        if isinstance(data, cabc.MutableMapping):
            # make read-only to prevent any ugly hacks
            rodata = types.MappingProxyType(data)
        else:
            rodata = data
        fsm_event_data.set(rodata)

        if isinstance(etype, Goto):
            newstate = etype.state
            self._check_state(newstate)
        else:
            if etype not in self._ct_events:
                return NotImplemented
            try:
                newstate = self._ct_transition[(etype, self.state)]
            except KeyError:
                newstate = self._ct_transition.get((etype, None), None)
            if newstate is None:
                self.log("No transition defined for event %s in state %s", etype, self._state)
                for event in self._on_notrans:
                    event.send(self, event=etype, state=self._state)
                return False
            if self.is_initialized() and not all(self._run_cb('cond', etype)):
                self.log(
                    "not executing event %s (%s -> %s), condition not satisfied",
                    etype, self.state, newstate)
                return False

        if self._fsm_event_active:
            # recursive call:
            #   - event ->  enter_STATE -> new event, or
            #   - timed event with zero duration -> next event
            if self._next_event is not None:
                raise EdzedError(
                    "Forbidden event multiplication; "
                    f"Two events ({self._next_event[0]} and {etype}) were generated "
                    "while handling a single event")
            self._next_event = (etype, data, newstate)
            return True

        self._fsm_event_active = True
        try:
            if self.is_initialized():
                self._run_cb('exit', self._state)
                self._send_events('on_exit', self._state)
                self._stop_timer()
            assert self._next_event is None
            for _ in range(self._ct_chainlimit):
                if self._next_event:
                    # intermediate state: skip generated events and exit the state immediately
                    self._run_cb('exit', self._state)
                    etype, data, newstate = self._next_event
                    self._next_event = None
                self.log("state: %s -> %s (event: %s)", self._state, newstate, etype)
                self._state = newstate
                with self._enable_event:
                    self._run_cb('enter', self._state)
                if self._next_event:
                    continue
                try:
                    timed_event = self._ct_timed_event[newstate]
                except KeyError:
                    pass    # new state is not a timed state
                else:
                    with self._enable_event:
                        self._start_timer(data.get('duration'), timed_event)
                    if self._next_event:
                        continue
                break
            else:
                raise EdzedError('Chained state transition limit reached (infinite loop?)')
            output = self._eval()
            if output is not block.UNDEF:
                self.set_output(output)
            self._send_events('on_enter', self._state)
            return True
        finally:
            self._fsm_event_active = False


    def _event(self, etype, data):
        """Wrapper creating a separate context, see _event_ctx for docs."""
        return contextvars.copy_context().run(self._event_ctx, etype, data)


    def _eval(self):    # pylint: disable=no-self-use
        """
        Compute and return the output value.

        Return UNDEF to leave the output unchanged.

        The output of a FSM is often unused. For these cases
        the default _eval just returns False.
        """
        return False

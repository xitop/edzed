"""
Event driven finite-state machine (FSM) extended with optional timers.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import asyncio
import collections
from collections.abc import Callable, Iterable, Iterator, Mapping, MutableMapping, Sequence
import contextvars
from dataclasses import dataclass
import time
import types
from typing import Any, Optional, Literal

from . import addons
from . import block
from . import utils
from .exceptions import add_note, EdzedCircuitError, EdzedUnknownEvent
from .utils import looptimes


__all__ = ['fsm_event_data', 'FSM', 'Goto', 'INF_TIME']

INF_TIME = float('+inf')
fsm_event_data = contextvars.ContextVar('fsm_event_data')


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
    STATES: Sequence[str] = ()
    TIMERS: Mapping[str, Sequence] = {}
    EVENTS: Iterable[Sequence] = ()
    # and edzed will translate that to:
    _ct_chainlimit: int
        # limit for chained transitions
    _ct_default_duration: dict[str, Optional[float]]
        # {timed_state: duration_in_seconds_or_None}
    _ct_events: set[str]
        # all valid events
    _ct_default_state: str
        # the default initial state
    _ct_methods: dict[Literal['enter', 'exit', 'cond'], dict[str, Callable]]
        # summary of enter_STATE, exit_STATE, cond_EVENT methods
    _ct_prefixes: list[tuple[str, int, Iterable]]
        # auxilliary data for keyword argument parsing
    _ct_states: set[str]
        # all valid states
    _ct_timed_event: dict[str, str|block.EventType]
        # {timed_state: event_on_timer_expiration}
    _ct_transition: dict[tuple[str, str|None], str]
        # the transition table: {(event, state): next_state}

    @classmethod
    def _check_state(cls, state):
        if state not in cls._ct_states:
            raise ValueError(f"Unknown state {state!r}")

    @classmethod
    def _build_tables(cls):
        """
        Build control tables from STATES, TIMERS and EVENTS.

        The original tables are left unchanged.
        """
        def add_transition(event: str, from_state: Optional[str], next_state: str) -> None:
            if from_state is not None:
                cls._check_state(from_state)
            key = (event, from_state)
            if key in cls._ct_transition:
                raise ValueError(
                    f"Multiple transitions defined for event {event!r} in state {from_state!r}")
            cls._ct_transition[key] = next_state

        # control tables must be created for each subclass
        # '_ct' (control table) prefix chosen to make a name clash unlikely
        cls._ct_states = set(cls.STATES).union(cls.TIMERS)
        cls._ct_events = set()
        cls._ct_transition = {}
        cls._ct_default_duration = {}
        cls._ct_timed_event = {}
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
        cls._ct_chainlimit = 3 * len(cls._ct_states)

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
                cls._ct_default_duration[state] = utils.time_period(duration)
            except (ValueError, TypeError) as err:
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
            add_note(err, f"FSM type {cls.__name__}, validation of control tables")
            # DO NOT catch this error until https://bugs.python.org/issue38085 is fixed
            raise

    def __init__(
            self, *args,
            on_notrans: Optional[block.Event|Iterator[block.Event]|Sequence[block.Event]]=None,
            **kwargs):
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

        FSM initialization takes place in init_from_value().
        """
        if type(self) is FSM:   # pylint: disable=unidiomatic-typecheck
            raise TypeError("Can't instantiate abstract FSM class")
        prefixed = collections.defaultdict(list)
        for arg in kwargs:
            for prefix, length, valid_names in self._ct_prefixes:
                if arg.startswith(prefix):
                    name = arg[length:]  # strip prefix
                    if name not in valid_names:
                        valid_names_str = ', '.join(
                            f"'{prefix}{suffix}'" for suffix in valid_names)
                        raise TypeError(
                            f"{arg!r} is an invalid keyword argument for "
                            f"{type(self).__name__}(); accepted are: {valid_names_str}"
                            )
                    prefixed[prefix].append((name, arg))
        if prefixed['t_']:
            self._duration = self._ct_default_duration.copy()   # copy on write
            for timed_state, arg in prefixed['t_']:
                if timed_state not in self._duration:
                    raise ValueError(f"{timed_state!r} is not a timed state")
                duration = utils.time_period(kwargs.pop(arg))
                if duration is not None:
                    self._duration[timed_state] = duration
        else:
            self._duration = self._ct_default_duration
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
        self._state: str|block._UndefType = block.UNDEF
        self._active_timer: asyncio.TimerHandle|None = None
        self._fsm_event_active = False
        self._next_event: str|None = None     # scheduled event in chained state transition
        self.sdata: dict[str, Any] = {}
        kwargs.setdefault('initdef', self._ct_default_state)
        super().__init__(*args, **kwargs)

    @property
    def state(self) -> str|block._UndefType:
        """
        Return the FSM state (string) or UNDEF if not initialized.
        """
        return self._state

    def get_state(self) -> tuple[str, Optional[float], dict[str, Any]]:
        """
        Return the block's internal state.

        The internal state is a 3-tuple:
            FSM state, timer state, additional state data
        The timer state is either None or an expiration time given
        as UNIX timestamp.

        Returned data can be restored with _restore_state.
        """
        timer = self._active_timer
        if timer is None or timer.cancelled():
            exp_timestamp = None
        else:
            exp_timestamp = looptimes.loop_to_unixtime(timer.when())
        return (self._state, exp_timestamp, self.sdata)

    def _restore_state(self, istate: Sequence, /) -> None:
        """
        Restore the internal state created by get_state().

        cond_STATE, enter_STATE and on_enter_STATE are not executed,
        because the state was entered already in the past. Now it is
        only restored.
        """
        if len(istate) == 2:
            # compatibility with versions < 21.1.31
            istate = [*istate, {}]
        state, exp_timestamp, sdata = istate
        self._check_state(state)
        if exp_timestamp is not None:
            remaining = exp_timestamp - time.time()
            if remaining <= 0.0:
                self.log_debug("restore state: ignoring expired state")
                return
            try:
                timed_event = self._ct_timed_event[state]
            except KeyError:
                raise EdzedCircuitError(
                    f"cannot set a timer for a not timed state {state!r}") from None
            self._set_timer(remaining, timed_event)
        self._state = state
        self.sdata = sdata
        self.log_debug("state: <UNDEF> -> %s", state)
        output = self.calc_output()
        if output is not block.UNDEF:
            self.set_output(output)

    def init_from_value(self, value: str) -> None:
        """Initialize the internal state."""
        self.event(Goto(value))

    def stop(self) -> None:
        """Cleanup."""
        self._stop_timer()
        super().stop()

    def _set_timer(self, duration: float, timed_event: str|block.EventType) -> None:
        """Start the timer (low-level)."""
        self.log_debug("timer: %.3fs before %s", duration, timed_event)
        self._active_timer = asyncio.get_running_loop().call_later(
            duration, self.event, timed_event)

    def _start_timer(
            self, duration: Optional[int|float|str], timed_event: str|block.EventType) -> None:
        """Start the timer."""
        if duration is not None:
            duration = utils.time_period(duration)
        else:
            duration = self._duration.get(self._state)
            if duration is None:    # not found or explicitly set to None
                raise EdzedCircuitError(f"Timer duration for state {self._state!r} not set")
        if duration == INF_TIME:
            return
        if duration <= 0.0:
            self.log_debug("timer: zero delay before %s", timed_event)
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
                    self.log_debug("timer: cancelled")
            self._active_timer = None

    def _send_events(self, trigger_type: Literal['on_enter', 'on_exit']) -> None:
        """Send events triggered by 'on_enter_STATE' or 'on_exit_STATE'."""
        state_events = self._state_events[trigger_type]
        state = self._state
        try:
            events = state_events[state]
        except KeyError:
            return
        for event in events:
            event.send(
                self,
                sdata={k: v for k, v in self.sdata.items() if not k.startswith('_')},
                trigger=trigger_type[3:],   # strip 'on_' from trigger_type
                state=state,
                value=self._output,
                )

    def _run_cb(self, cb_type: Literal['cond', 'enter', 'exit'], name: str) -> list[Any]:
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
            # bind the method
            cb = cls_cb[name].__get__(self)     # type: ignore
        except KeyError:
            pass
        else:
            retvals.append(cb())
        return retvals

    def _event_ctx(self, etype: str|block.EventType, data: Mapping) -> bool:
        """
        Handle event. Check validity and conditions.

        Timed states look for 'duration' key in the data. If it is
        present, the value overrides the default timer duration.

        Return value:
            True = transition accepted, either executed or scheduled
                   for execution
            False = transition rejected
        """
        if isinstance(data, MutableMapping):
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
                raise EdzedUnknownEvent(f"{self}: Unknown event type {etype!r}")
            assert isinstance(etype, str)   # mypy type narrowing
            try:
                newstate = self._ct_transition[(etype, self.state)]
            except KeyError:
                newstate = self._ct_transition.get((etype, None), None)
            if newstate is None:
                self.log_debug(
                    "No transition defined for event %s in state %s", etype, self._state)
                for event in self._on_notrans:
                    event.send(self, trigger='notrans', event=etype, state=self._state)
                return False
            if self.is_initialized() and not all(self._run_cb('cond', etype)):
                self.log_debug(
                    "not executing event %s (%s -> %s), condition not satisfied",
                    etype, self.state, newstate)
                return False

        if self._fsm_event_active:
            # recursive call:
            #   - event ->  enter_STATE -> new event, or
            #   - timed event with zero duration -> next event
            if self._next_event is not None:
                raise EdzedCircuitError(
                    "Forbidden event multiplication; "
                    f"Two events ({self._next_event[0]} and {etype}) were generated "
                    "while handling a single event")
            self._next_event = (etype, data, newstate)
            return True

        self._fsm_event_active = True
        try:
            if self.is_initialized():
                self._run_cb('exit', self._state)
                self._send_events('on_exit')
                self._stop_timer()
            assert self._next_event is None
            for _ in range(self._ct_chainlimit):
                if self._next_event:
                    # intermediate state: skip generated events and exit the state immediately
                    self._run_cb('exit', self._state)
                    etype, data, newstate = self._next_event
                    self._next_event = None
                self.log_debug("state: %s -> %s (event: %s)", self._state, newstate, etype)
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
                raise EdzedCircuitError(
                    'Chained state transition limit reached (infinite loop?)')
            output = self.calc_output()
            if output is not block.UNDEF:
                self.set_output(output)
            self._send_events('on_enter')
            return True
        finally:
            self._fsm_event_active = False


    def _event(self, etype: str|block.EventType, data: Mapping) -> bool:
        """Wrapper creating a separate context, see _event_ctx for docs."""
        return contextvars.copy_context().run(self._event_ctx, etype, data)


    def calc_output(self) -> Any:   # pylint: disable=no-self-use
        """
        Compute and return the output value.

        Return UNDEF to leave the output unchanged.

        The output of a FSM is often unused. For these cases
        the default calc_output just returns the state.
        """
        return self._state

"""
Sequential blocks for general use.
"""

import asyncio
import logging

from .. import addons
from .. import block
from .. import fsm
from ..utils import shield_cancel


__all__ = ['Input', 'InputExp', 'OutputAsync', 'OutputFunc']

_logger = logging.getLogger(__package__)


class Input(addons.AddonPersistence, block.SBlock):
    """
    Input with optional value validation.

    Arguments:
        initdef -- default value (initialization value of last resort)
        persistent -- if true, initialize from the last known value
        schema, check, allowed -- optional validators of input values

    Validators of new input values (optional):
        check -- a value test function,
            If the function's return value evaluates to true,
            new value is accepted, otherwise it is rejected.
        allowed -- a sequence or set of allowed values,
            This is roughly equivalent to:
                check=lambda value: value in ALLOWED
        schema -- a function possibly modifying the value:
            If the function raises, value is rejected,
            otherwise the input is set to the returned value.

        It is recommended NOT to use more than one validator, but any
        combination of schema, check and allowed may be used.

        Schema is the only method capable of changing the value.
        It is called last to ensure all validators test the original
        input value.

        The default is validated only when it is used as input value.

    Usage:
        input.put(<VALUE>) -- return True if the new value was accepted,
                              False otherwise.
        Note: it is a shortcut for input.event('put', value=<VALUE>)
    """

    def __init__(self, *args, schema=None, check=None, allowed=None, **kwargs):
        self._schema = schema
        self._check = check
        self._allowed = None if allowed is None else frozenset(allowed)
        super().__init__(*args, **kwargs)
        if self.initdef is not block.UNDEF:
            self._validate(self.initdef)

    def init_from_value(self, value):
        self.put(value)

    def _validate(self, value):
        if self._allowed is not None and value not in self._allowed:
            raise ValueError(
                f"Value {value!r} validation error: value not among allowed values")
        if self._check is not None and not self._check(value):
            raise ValueError(f"Value {value!r} validation error: check function not passed")
        if self._schema is not None:
            try:
                value = self._schema(value)
            except Exception as err:
                raise ValueError(f"Value {value!r} schema validation error: {err}") from None
        return value

    def _event_put(self, *, value, **_data):
        try:
            value = self._validate(value)
        except ValueError as err:
            self.warn("%s", err)
            return False
        self.set_output(value)
        return True

    _restore_state = init_from_value


class InputExp(Input, fsm.FSM):
    """
    Input with an expiration time.

    After 'duration' replace the stored value with 'expired' value.
    """
    STATES = ['expired', 'valid']
    TIMERS = {
        'valid': (None, fsm.Goto('expired')),
        }
    EVENTS = (
        ('start', None, 'valid'),
        )

    def __init__(self, *args, duration, expired=None, **kwargs):
        super().__init__(*args, t_valid=duration, **kwargs)
        self._validate(expired)
        self._expired = expired

    def enter_expired(self):
        Input._event_put(self, value=self._expired)

    def _event_put(self, *, value, **data):
        if not Input._event_put(self, value=value):
            return False    # value not accepted by validators
        with self._enable_event:
            # value is missing in data, but we need only the optional 'duration' item
            self.event(fsm.Goto('expired') if value == self._expired else 'start', **data)
        return True

    def init_from_value(self, value):
        self.put(value)

    def _eval(self):    # pylint: disable=no-self-use
        """Stop the FSM part from setting the output."""
        return block.UNDEF

    def get_state(self):
        """Combine states of both parts."""
        return {
            'input': Input.get_state(self),
            'fsm': fsm.FSM.get_state(self),
        }

    def _restore_state(self, state):
        fsm.FSM._restore_state(self, state['fsm'])
        if self._state is not block.UNDEF:
            Input._event_put(self, value=state['input'])


_STOP_CMD = object()

class OutputAsync(addons.AddonAsync, block.SBlock):
    """
    Run a coroutine as an output task when a value arrives.

    The coroutine is called with a single argument, the 'value'
    item from the event data.

    There are two operation modes: the noqueue mode (qmode is False,
    this is the default) and the queue mode (qmode is True). The
    difference is in the behavior when a new value arrives before
    processing of the previous one has finished.

      - In noqueue mode the task processing the previous value will be
        cancelled (and awaited) if it is still running. All unprocessed
        values except the last one are dropped from the output queue.

      - In queue mode all values are enqueued and processed one by one
        in order they have arrived. This may introduce delays. Make sure
        the coroutine can keep up with the rate of incoming values.

    The output of an OutputAsync block is a boolean busy flag:
    True, when the OutputAsync block is active; False when idle.

    The block can be instructed to trigger on_success/on_error events
    depending on the result of the coroutine. Any returned value is
    considered a success (on_success event data key: 'value'), and
    an exception (other than CancelledError) means an error
    (on_error event data key: 'error'). A cancelled coroutine does
    not trigger any events.

    By default on_error is set to Event('_ctrl', 'error') which
    shuts down the simulation (see the ControlBlock). To handle the
    error differently or to ignore it, set the on_error explicitly.

    If the 'stop_value' is defined, it is inserted into the queue
    and processed as the last item before stopping. This allows to leave
    the controlled process in a well defined state. As this happen
    during the stop phase, make sure the stop_timeout gives enough time
    for a successful output coroutine run.

    'guard_time' is the duration of a mandatory and uncancellable sleep
    after each run of the output coroutine. No output activity can
    happen during the sleep. The purpose is to limit the frequency
    of output changes, for instance when controlling a hardware switch.
    Default value is 0.0 [seconds], i.e. no guard_time. The 'guard_time'
    must not be longer than the 'stop_timeout'.

    Usage:
        out = OutputAsync(NAME, coro=CORO())
        out.put(VALUE)
    """

    def __init__(
            self, *args,
            coro, guard_time=0.0,
            qmode=False, on_success=(), on_error=None, stop_value=block.UNDEF,
            **kwargs):
        self._on_success = block.event_tuple(on_success)
        if on_error is None:
            on_error = block.Event('_ctrl', 'error')
        self._on_error = block.event_tuple(on_error)
        self._coro = coro
        self._guard_time = guard_time
        self._qmode = bool(qmode)
        self._stop_value = stop_value
        self._ctask = None
        self._queue = None
        super().__init__(*args, **kwargs)
        if guard_time > self.stop_timeout:
            raise ValueError(
                f"guard_time {guard_time:.3f} must not exceed "
                f"stop_timeout {self.stop_timeout:.3f} seconds.")

    def _event_put(self, *, value, **_data):
        self._queue.put_nowait(value)
        self.set_output(True)

    async def _output_task_wrapper(self, value):
        self.log("output task started for value %s", value)
        if self._qmode:
            qsize = self._queue.qsize()
            if qsize > 0:
                self.warn("%d value(s) waiting in output queue", qsize)
        try:
            retval = await self._coro(value)
        except asyncio.CancelledError:
            # it is assumed that the coroutine was cancelled by the control task
            self.log("output task cancelled")
        except Exception as err:
            self.warn("output task failed for input value %r: %r", value, err)
            for ev in self._on_error:
                ev.send(self, error=err)
        else:
            self.log("output task returned value %r", retval)
            for ev in self._on_success:
                ev.send(self, value=retval)
        if self._queue.empty():
            self.set_output(False)
        if self._guard_time > 0.0:
            try:
                await shield_cancel.shield_cancel(asyncio.sleep(self._guard_time))
            except asyncio.CancelledError:
                # shield_cancel re-reaises any CancelledError when it stops shielding
                pass

    async def _control_noqmode(self):
        """
        Start output task for values from the queue.

        Only one task may be running at a time. Pending values
        are processed asap, cancelling the current task if necessaty.

        Stop serving after receiving _STOP_CMD sentinel value.
        """
        task = None
        stop = False
        queue = self._queue
        while True:
            if not stop:
                value = await queue.get()
                if value is _STOP_CMD:
                    stop = True
            if task and not task.done():
                if not stop:
                    task.cancel()
                await task
            if stop:
                break
            while not queue.empty():
                new_value = queue.get_nowait()
                if new_value is _STOP_CMD:
                    stop = True
                    break
                self.warn("Dropping %r from output queue", value)
                value = new_value
            task = asyncio.create_task(self._task_wrapper(self._output_task_wrapper(value)))

    async def _control_qmode(self):
        """
        Start output task for values from the queue.

        Only one task may be running at a time. Pending values wait
        in the queue.

        Stop serving after receiving _STOP_CMD sentinel value.
        """
        while True:
            value = await self._queue.get()
            if value is _STOP_CMD:
                break
            await self._output_task_wrapper(value)

    def start(self):
        super().start()
        self._queue = asyncio.Queue()
        cfunc = self._control_qmode if self._qmode else self._control_noqmode
        self._ctask = asyncio.create_task(self._task_wrapper(cfunc()))

    def init_regular(self):
        self.set_output(False)

    def stop(self):
        if self._ctask is None:
            return  # start wasn't called
        if self._stop_value is not block.UNDEF:
            self.put(self._stop_value)
        self._queue.put_nowait(_STOP_CMD)   # this will not cancel a running output task
        super().stop()

    async def stop_async(self):
        if self._ctask is None:
            return  # start wasn't called
        try:
            await self._ctask
        except asyncio.CancelledError:
            pass
        finally:
            self._ctask = None
        await super().stop_async()


class OutputFunc(block.SBlock):
    """
    Run a function when a value arrives.

    The function is called with a single argument, the 'value'
    item from the event data.

    The output of an OutputFunc block is always False.

    The block can be instructed to trigger on_success/on_error events
    depending on the result of the function call. A returned value is
    considered a success (on_success event data key: 'value'),
    an exception means an error (on_error event data key: 'error').

    By default on_error is set to Event('_ctrl', 'error') which
    shuts down the simulation (see the ControlBlock). To handle the
    error differently or to ignore it, set the on_error explicitly.

    If the 'stop_value' is defined, it is fed into the block
    and processed as the last item before stopping. This allows
    to leave the controlled process in a well defined state.

    Usage:
        out = OutputFunc(NAME, func=FUNC)
        out.put(VALUE)
    """

    def __init__(
            self, *args, func, on_success=(), on_error=None, stop_value=block.UNDEF, **kwargs):
        self._on_success = block.event_tuple(on_success)
        if on_error is None:
            on_error = block.Event('_ctrl', 'error')
        self._on_error = block.event_tuple(on_error)
        self._func = func
        self._stop_value = stop_value
        super().__init__(*args, **kwargs)

    def _event_put(self, *, value, **_data):
        try:
            retval = self._func(value)
        except Exception as err:
            self.warn("output function failed for input value %r: %r", value, err)
            for ev in self._on_error:
                ev.send(self, error=err)
        else:
            self.log("output function returned value %r", retval)
            for ev in self._on_success:
                ev.send(self, value=retval)

    def init_regular(self):
        """Initialize the internal state."""
        self.set_output(False)

    def stop(self):
        if self._stop_value is not block.UNDEF:
            self.put(self._stop_value)
        super().stop()

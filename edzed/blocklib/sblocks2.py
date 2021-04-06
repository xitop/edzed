"""
Sequential blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import asyncio

from .. import addons
from .. import block
from .. import fsm
from .. import utils


__all__ = ['Input', 'InputExp', 'OutputAsync', 'OutputFunc']


class _Validation:
    """Value validation mix-in."""

    def __init__(self, *args, schema=None, check=None, allowed=None, **kwargs):
        self._schema = schema
        self._check = check
        self._allowed = None if allowed is None else frozenset(allowed)
        super().__init__(*args, **kwargs)

    def _validate(self, value):
        """
        Validate a value.

        Return the result if the value is accepted.
        Raise a ValueError if not.
        """
        if self._allowed is not None and value not in self._allowed:
            raise ValueError(f"Validation error: {value!r} is not among allowed values")
        if self._check is not None and not self._check(value):
            raise ValueError(f"Validation function rejected value {value!r}")
        if self._schema is not None:
            try:
                value = self._schema(value)
            except Exception as err:
                raise ValueError(
                    f"Validation schema rejected value {value!r} with error: {err}") from None
        return value


class Input(_Validation, addons.AddonPersistence, block.SBlock):
    """
    Input with optional value validation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initdef is not block.UNDEF:
            self._validate(self.initdef)

    def init_from_value(self, value):
        self.put(value)

    def _event_put(self, *, value, **_data):
        try:
            value = self._validate(value)
        except ValueError as err:
            self.log_warning("%s", err)
            return False
        self.set_output(value)
        return True

    _restore_state = init_from_value


class InputExp(_Validation, fsm.FSM):
    """
    Input with an expiration time.
    """

    STATES = ['expired', 'valid']
    TIMERS = {
        'valid': (None, fsm.Goto('expired')),
        }
    EVENTS = (
        ('put', None, 'valid'),
        )

    def __init__(self, *args, duration, expired=None, initdef=block.UNDEF, **kwargs):
        # meaning of the initdef parameter:
        # - in InputExp: initial value
        # - in the underlying FSM: initial state
        has_init_value = initdef is not block.UNDEF
        super().__init__(
            *args,
            t_valid=duration,
            initdef = 'valid' if has_init_value else 'expired',
            **kwargs)
        if has_init_value:
            self.sdata['input'] = self._validate(initdef)
        self._expired = self._validate(expired)

    def cond_put(self):
        data = fsm.fsm_event_data.get()
        value = data['value']
        try:
            value = self._validate(value)
        except ValueError as err:
            self.log_warning("%s", err)
            return False
        self.sdata['input'] = value
        return True

    def on_enter_expired(self):
        self.sdata.pop('input', None)

    def calc_output(self):
        """Stop the FSM part from setting the output."""
        return self.sdata['input'] if self._state == 'valid' else self._expired


class OutputAsync(addons.AddonAsync, block.SBlock):
    """
    Run a coroutine as an output task when a value arrives.
    """
    _STOP_CMD = object()

    def __init__(
            self, *args,
            coro, guard_time=0.0,
            qmode=False, on_success=None, on_cancel=None, on_error,
            stop_value=block.UNDEF,
            **kwargs):
        self._on_success = block.event_tuple(on_success)
        self._on_cancel = block.event_tuple(on_cancel)
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
        self.log_debug("output task started for value %s", value)
        if self._qmode:
            qsize = self._queue.qsize()
            if qsize > 0:
                self.log_info("%d value(s) waiting in output queue", qsize)
        try:
            retval = await self._coro(value)
        except asyncio.CancelledError:
            # it is assumed that the coroutine was cancelled by the control task
            self.log_debug("output task cancelled")
            for ev in self._on_cancel:
                ev.send(self, trigger='cancel', arg=value)
        except Exception as err:
            self.log_error("output task failed for input value %r: %r", value, err)
            for ev in self._on_error:
                ev.send(self, trigger='error', error=err, arg=value)
        else:
            self.log_debug("output task returned value %r", retval)
            for ev in self._on_success:
                ev.send(self, trigger='success', value=retval, arg=value)
        if self._queue.empty():
            self.set_output(False)
        if self._guard_time > 0.0:
            try:
                await utils.shield_cancel(asyncio.sleep(self._guard_time))
            except asyncio.CancelledError:
                # shield_cancel re-reaises any CancelledError when it stops shielding
                pass

    async def _control_noqmode(self):
        """
        Start an output task for values from the queue.

        Only one task may be running at a time. New values
        are processed asap, cancelling the current task if necessary.

        Stop serving after receiving the _STOP_CMD sentinel value.
        """
        task = None
        stop = False
        queue = self._queue
        while True:
            if not stop:
                value = await queue.get()
                if value is self._STOP_CMD:
                    stop = True
            if task and not task.done():
                if not stop:
                    task.cancel()
                await task
            if stop:
                break
            while not queue.empty():
                new_value = queue.get_nowait()
                self.log_info("Dropping %r from queue", value)
                if new_value is self._STOP_CMD:
                    stop = True
                    break
                value = new_value
            task = asyncio.create_task(self._task_wrapper(self._output_task_wrapper(value)))

    async def _control_qmode(self):
        """
        Start an output task for values from the queue.

        Only one task may be running at a time. New values wait
        in the queue.

        Stop serving after receiving the _STOP_CMD sentinel value.
        """
        while True:
            value = await self._queue.get()
            if value is self._STOP_CMD:
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
        if self._stop_value is not block.UNDEF:
            # prohibit output events, because other blocks could be already stopped
            self._on_success = self.on_cancel = self._on_error = ()
            self.put(self._stop_value)
        self._queue.put_nowait(self._STOP_CMD)   # this will not cancel a running output task
        super().stop()

    async def stop_async(self):
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
    """

    def __init__(
            self, *args, func, on_success=None, on_error, stop_value=block.UNDEF, **kwargs):
        self._on_success = block.event_tuple(on_success)
        self._on_error = block.event_tuple(on_error)
        self._func = func
        self._stop_value = stop_value
        super().__init__(*args, **kwargs)

    def _event_put(self, *, value, **_data):
        try:
            result = self._func(value)
        except Exception as err:
            self.log_error("output function failed for input value %r: %r", value, err)
            for ev in self._on_error:
                ev.send(self, trigger='error', error=err)
            return ('error', err)
        else:
            self.log_debug("output function returned value %r", result)
            for ev in self._on_success:
                ev.send(self, trigger='success', value=result)
            return ('result', result)

    def init_regular(self):
        """Initialize the internal state."""
        self.set_output(False)

    def stop(self):
        if self._stop_value is not block.UNDEF:
            # prohibit output events, because other blocks could be already stopped
            self._on_success = self._on_error = ()
            self._event_put(value=self._stop_value)
        super().stop()

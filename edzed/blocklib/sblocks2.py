"""
Sequential blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import asyncio
import collections.abc as cabc
import concurrent.futures
import itertools
import weakref

from .. import addons
from .. import block
from .. import fsm
from .. import utils


__all__ = ['InitAsync', 'Input', 'InputExp', 'InExecutor', 'OutputAsync', 'OutputFunc']


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


def _check_arg(name, arg):
    """
    Check OutputXY arguments.

    An early check should prevent difficult to understand error messages.
    """
    if isinstance(arg, str) or not isinstance(arg, cabc.Sequence) \
            or any(not isinstance(k, str) for k in arg):
        raise TypeError(
            f"Argument {name!r} should be a sequence (e.g. a list or tuple) of strings, "
            f"but got {arg!r}")


def _args_as_string(args, kwargs):
    """Convert args and kwargs to a printable string."""
    return '(' + ', '.join(itertools.chain(
        (repr(a) for a in args),
        (f"{k}={v!r}" for k, v in kwargs.items()))) + ')'


class OutputAsync(addons.AddonAsync, block.SBlock):
    """
    Run a coroutine as an output task when a value arrives.
    """

    def __init__(
            self, *args,
            coro, mode,
            f_args=('value',), f_kwargs=(),
            guard_time=0.0,
            on_success=None, on_cancel=None, on_error,
            stop_data=None,
            **kwargs):
        _check_arg('f_args', f_args)
        _check_arg('f_kwargs', f_args)
        self._on_success = block.event_tuple(on_success)
        self._on_cancel = block.event_tuple(on_cancel)
        self._on_error = block.event_tuple(on_error)
        self._coro = coro
        if mode == 'c' or mode == "cancel":
            self._ctrl_coro = self._ctrl_cancel
        elif mode == 'w' or mode == "wait":
            self._ctrl_coro = self._ctrl_wait
        elif mode == 's' or mode == "start":
            self._ctrl_coro = self._ctrl_start
            if guard_time > 0.0:
                self.log_warning("using guard_time in 'start' mode is ineffective!")
        else:
            raise ValueError(
                "Argument 'mode' must be one of: 'cancel', 'start', 'wait' "
                f"(may be abbreviated to 'c', 's', or 'w'), but got {mode!r}")
        self._f_args = f_args
        self._f_kwargs = f_kwargs
        self._guard_time = guard_time
        self._stop_data = stop_data
        self._ctrl_task = None
        self._queue = None
        super().__init__(*args, **kwargs)
        if guard_time > self.stop_timeout:
            raise ValueError(
                f"guard_time {guard_time:.3f} must not exceed "
                f"stop_timeout {self.stop_timeout:.3f} seconds.")

    def _event_put(self, **data):
        self._queue.put_nowait(data)

    async def _output_coro(self, data):
        args = tuple(data[k] for k in self._f_args)
        kwargs = {k: data[k] for k in self._f_kwargs}
        if self.debug:
            self.log_debug("output task started; args: %s", _args_as_string(args, kwargs))
        try:
            retval = await self._coro(*args, **kwargs)
        except asyncio.CancelledError:
            # it is assumed that the coroutine was cancelled by the control task
            self.log_debug("output task cancelled")
            for ev in self._on_cancel:
                ev.send(self, trigger='cancel', put=data)
        except Exception as err:
            self.log_error(
                "output task failed; args: %s; error: %r", _args_as_string(args, kwargs), err)
            for ev in self._on_error:
                ev.send(self, trigger='error', error=err, put=data)
        else:
            self.log_debug("output task returned value %r", retval)
            for ev in self._on_success:
                ev.send(self, trigger='success', value=retval, put=data)
        if self._guard_time > 0.0:
            try:
                await utils.shield_cancel(asyncio.sleep(self._guard_time))
            except asyncio.CancelledError:
                # shield_cancel re-reaises any CancelledError when it stops shielding
                pass

    async def _output_coro_wrapper(self, data):
        """Count the active tasks."""
        self.set_output(self.output + 1)
        try:
            await self._output_coro(data)
        finally:
            self.set_output(self.output - 1)


    async def _ctrl_cancel(self):
        """
        Start an output task for data from the queue.

        Only one task may be running at a time. New data
        are processed asap, cancelling the current task if necessary.

        Stop serving after receiving the None sentinel value.
        """
        task = None
        stop = False
        queue = self._queue
        while True:
            if not stop:
                data = await queue.get()
                if data is None:
                    stop = True
            if task and not task.done():
                if not stop:
                    task.cancel()
                # do not use try/await task/except here, because the _output_coro
                # catches all exceptions from user-supplied 'coro'
                await task
            if stop:
                break
            while not queue.empty():
                new_data = queue.get_nowait()
                if new_data is None:
                    stop = True
                    break
                self.log_debug("Discarding: %r", data)
                for ev in self._on_cancel:
                    ev.send(self, trigger='cancel', put=data)
                data = new_data
            # we are already running as monitored task
            task = asyncio.create_task(self._output_coro_wrapper(data))

    async def _ctrl_wait(self):
        """
        Start an output task for values from the queue.

        Only one task may be running at a time. New values wait
        in the queue.

        Stop serving after receiving the None sentinel value.
        """
        while True:
            data = await self._queue.get()
            if self.debug:
                qsize = self._queue.qsize()
                if qsize > 0:
                    self.log_debug("%d value(s) waiting in output queue", qsize)
            if data is None:
                break
            await self._output_coro_wrapper(data)

    async def _ctrl_start(self):
        """
        Start an output task for values from the queue asap.

        Stop serving after receiving the None sentinel value.
        """
        tasks = weakref.WeakSet()
        while True:
            data = await self._queue.get()
            if data is None:
                break
            tasks.add(asyncio.create_task(self._output_coro_wrapper(data)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def start(self):
        super().start()
        self._queue = asyncio.Queue()
        self._ctrl_task = self._create_monitored_task(self._ctrl_coro())

    def init_regular(self):
        self.set_output(0)

    def stop(self):
        # do not compare self._ctrl_coro using "is" (descriptors are in play)
        if self._stop_data is not None and self._ctrl_coro != self._ctrl_start:
            # stop_data processing in start mode moved to stop_async, because
            # that mode does not guarantee that stop_data will be processed last
            self._event_put(**self._stop_data)
        self._queue.put_nowait(None)    # stop serving
        super().stop()

    async def stop_async(self):
        try:
            await self._ctrl_task
        except asyncio.CancelledError:
            pass
        finally:
            self._ctrl_task = None
        if self._stop_data is not None and self._ctrl_coro == self._ctrl_start:
            await self._output_coro_wrapper(self._stop_data)
        await super().stop_async()


class InExecutor:
    """
    Convert a blocking function into a coroutine usable with OutputAsync.

    The function will be executed in an executor.
    """
    def __init__(self, func, executor=concurrent.futures.ThreadPoolExecutor):
        self._func = func
        self._executor = executor

    async def __call__(self, *args):
        loop = asyncio.get_running_loop()
        with self._executor() as pool:
            return await loop.run_in_executor(pool, self._func, *args)


class OutputFunc(block.SBlock):
    """
    Run a function when a value arrives.
    """

    def __init__(
            self, *args,
            func, f_args=('value',), f_kwargs=(),
            on_success=None, on_error,
            stop_data=None,
            **kwargs):
        _check_arg('f_args', f_args)
        _check_arg('f_kwargs', f_kwargs)
        self._on_success = block.event_tuple(on_success)
        self._on_error = block.event_tuple(on_error)
        self._func = func
        self._f_args = f_args
        self._f_kwargs = f_kwargs
        self._stop_data = stop_data
        super().__init__(*args, **kwargs)

    def _event_put(self, **data):
        args = tuple(data[k] for k in self._f_args)
        kwargs = {k: data[k] for k in self._f_kwargs}
        try:
            result = self._func(*args, **kwargs)
        except Exception as err:
            self.log_error(
                "output function failed; args: %s; error: %r",
                _args_as_string(args, kwargs), err)
            for ev in self._on_error:
                ev.send(self, trigger='error', error=err)
            return ('error', err)
        else:
            self.log_debug("output function returned: %r", result)
            for ev in self._on_success:
                ev.send(self, trigger='success', value=result)
            return ('result', result)

    def init_regular(self):
        """Initialize the internal state."""
        self.set_output(False)

    def stop(self):
        if self._stop_data is not None:
            self._event_put(**self._stop_data)
        super().stop()


class InitAsync(addons.AddonAsync, block.SBlock):
    """
    Run a coroutine once during the circuit initialization.
    """

    def __init__(self, *args, init_coro: list, **kwargs):
        if not isinstance(init_coro, cabc.Sequence):
            raise TypeError(
                "Parameter 'init_coro' must be a sequence (list, tuple, ...), "
                f"but got {init_coro!r}")
        if not init_coro:
            raise ValueError("Parameter 'init_coro' cannot be empty.")
        self._init_coro = init_coro
        super().__init__(*args, **kwargs)

    def init_regular(self):
        if self.is_initialized() or self.initdef is not block.UNDEF:
            return      # is initialized or will be initialized
        # initialize only to prevent a startup failure
        self._output_events = ()    # do not send output events
        self.set_output(None)

    def init_from_value(self, value):
        self.set_output(value)

    async def init_async(self):
        coro, *args = self._init_coro
        result = await coro(*args)
        self.set_output(result)

"""
Sequential blocks for general use.
"""

import asyncio

from .. import addons
from .. import block
from ..exceptions import EdzedError
from .. import fsm


__all__ = ['ControlBlock', 'Counter', 'Repeat', 'ValuePoll']


class ControlBlock(block.SBlock):
    """
    Simulator control block.

    The output value is fixed to None and has no meaning. There is
    no reason to have more than one control block in any circuit.

    Usage:
        ctrl.event('shutdown') -- stop the simulation
        ctrl.event('error', source=NAME, error=ERROR) -- stop due to
            an error; ERROR could be an Exception object or just an
            error message.

    A ControlBlock named '_ctrl' will be automatically created if
    there is a reference to this name in the circuit.
    """

    def _event_shutdown(self, *, source='<no-source-data>', **_data):
        exc = asyncio.CancelledError(f"{self}: shutdown requested by '{source}'")
        self.circuit.abort(exc)

    def _event_error(self, *, source='<no-source-data>', error='<no-error-data>', **_data):
        exc = EdzedError(f"{self}: error reported by '{source}': {error!r}")
        if isinstance(error, Exception):
            exc.__cause__ = error
        self.circuit.abort(exc)

    def init_regular(self):
        self.set_output(None)


class Counter(addons.AddonPersistence, block.SBlock):
    """
    Counter. If modulo is set to a number M, count modulo M.

    For a positive integer M it means to count only from 0 to M-1
    and then wrap around.

    If modulo is not set, the output may reach any positive or
    negative number.

    Usage:
        counter.event('inc')            # increment by 1
        counter.event('inc', amount=N)  # increment by N
        counter.event('dec')            # decrement by 1
        counter.event('dec', amount=N)  # decrement by N
        counter.put(value)              # set to value (mod M)

    The counter can process floating point numbers.
    """

    def __init__(self, *args, modulo=None, initdef=0, **kwargs):
        """
        Set the optional modulo and the initial counter value (default = 0).
        """
        if modulo == 0:
            raise ValueError("modulo must not be zero")
        self._mod = modulo
        super().__init__(*args, initdef=initdef, **kwargs)

    def _setmod(self, value):
        self.set_output(value if self._mod is None else value % self._mod)

    def _event_inc(self, *, amount=1, **_data):
        self._setmod(self._output + amount)

    def _event_dec(self, *, amount=1, **_data):
        self._setmod(self._output - amount)

    def _event_put(self, *, value, **_data):
        self._setmod(value)

    init_from_value = _setmod
    _restore_state = _setmod


class Repeat(addons.AddonMainTask, block.SBlock):
    """
    Periodically repeat the last received event.

    For a predictable operation only one event type is repeated.
    All other events are ignored.

    Repeat adds a 'repeat' value to the event data. The original event
    is sent with repeat=False, subsequent repetitions are sent with
    repeat=True. This repeat value is also copied to the output.
    Initial output is False.

    A Repeat block also saves the 'source' to 'orig-source'.

    Arguments:
        dest -- dest SBlock, an instance or a name
        etype -- type of events to process, default is 'put'
        interval -- time interval in seconds or as a string
            with d, h, m and s units (see utils.timeunits).
    """

    def __init__(self, *args, dest, etype='put', interval, **kwargs):
        self._repeated_event = block.Event(dest, etype)
        interval = fsm.convert_duration(interval)
        if interval is None or interval <= 0.0:
            raise ValueError("interval must be positive")
        self._interval = interval
        self._queue = None
        super().__init__(*args, **kwargs)

    async def _maintask(self):
        repeat = False
        self.set_output(False)
        data = await self._queue.get()
        data['orig-source'] = data.get('source')
        while True:
            self.set_output(repeat)
            self._repeated_event.send(self, **data, repeat=repeat)
            repeat = True
            try:
                data = await asyncio.wait_for(self._queue.get(), self._interval)
            except asyncio.TimeoutError:
                pass
            else:
                repeat = False

    def _event(self, etype, data):
        if etype == self._repeated_event.etype:
            self._queue.put_nowait(data)

    def start(self):
        super().start()
        self._queue = asyncio.Queue()


class ValuePoll(addons.AddonMainTask, block.SBlock):
    """
    A source of measured or computed values.

    Output the result of acquisition function 'func' every 'interval'
    seconds. The interval may be written also as a string with
    d, h, m and s units (see edzed.utils.timeunits). The func may be
    a regular or an async function.

    The interval is measured between function calls. The duration
    of the call itself represents an additional delay.

    A func error (i.e. unhandled exception) stops the simulation.
    If a real value is not available, the function has basically
    these three options:
        - return some default value
        - return some sentinel value understood by connected
          circuit blocks
        - return UNDEF. If it returns UNDEF, it will be ignored and
          no output change will happen in the current loop iteration.

    Initialization rules:
    If the very first value is not obtained within the init_timeout
    limit, the initdef value will be used as a default. It initdef
    is not defined, the initialization fails.
    """

    def __init__(self, *args, interval, func, **kwargs):
        self._func = func
        self._interval = fsm.convert_duration(interval)
        self._init_done = asyncio.Event()
        super().__init__(*args, **kwargs)

    async def _maintask(self):
        """Data acquisition task: repeatedly obtain a value."""
        initialized = False
        while True:
            value = self._func()
            if asyncio.iscoroutine(value):
                value = await value
            if value is not block.UNDEF:
                self.set_output(value)
                if not initialized:
                    self._init_done.set()
                    initialized = True
            await asyncio.sleep(self._interval)

    async def init_async(self):
        await self._init_done.wait()

    def init_from_value(self, value):
        self.set_output(value)

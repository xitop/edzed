"""
Sequential blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
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
    """

    def __init__(self, *args, func, interval, **kwargs):
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

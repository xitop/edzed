"""
Sequential blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, NoReturn, Optional

from .. import addons
from .. import block
from .. import utils
from ..exceptions import EdzedCircuitError


__all__ = ['ControlBlock', 'Counter', 'Repeat', 'ValuePoll']


class ControlBlock(block.SBlock):
    """
    Simulator control block.
    """

    def _event_shutdown(
            self, *,
            source: str = '<no-source-data>',
            **_data) -> None:
        exc = asyncio.CancelledError(f"{self}: shutdown requested by '{source}'")
        self.circuit.abort(exc)

    def _event_abort(
            self, *,
            source: str = '<no-source-data>',
            error: BaseException|str = '<no-error-data>',
            **_data) -> None:
        exc = EdzedCircuitError(f"{self}: error reported by '{source}': {error!r}")
        if isinstance(error, Exception):
            exc.__cause__ = error
        self.circuit.abort(exc)

    def init_regular(self) -> None:
        self.set_output(None)


class Counter(addons.AddonPersistence, block.SBlock):
    """
    Counter. If modulo is set to a number M, count modulo M.
    """

    def __init__(
            self, *args,
            modulo: Optional[int|float] = None,
            initdef: int|float = 0,
            **kwargs):
        """
        Set the optional modulo and the initial counter value (default = 0).
        """
        if modulo == 0:
            raise ValueError("modulo must not be zero")
        self._mod = modulo
        super().__init__(*args, initdef=initdef, **kwargs)

    def _setmod(self, value: int|float) -> int|float:
        output = value if self._mod is None else value % self._mod
        self.set_output(output)
        return output

    def _event_inc(self, *, amount: int|float = 1, **_data) -> int|float:
        return self._setmod(self._output + amount)

    def _event_dec(self, *, amount: int|float = 1, **_data) -> int|float:
        return self._setmod(self._output - amount)

    def _event_put(self, *, value: int|float, **_data) -> int|float:
        return self._setmod(value)

    def _event_reset(self, **_data) -> int|float:
        return self._setmod(self.initdef)

    init_from_value = _setmod
    _restore_state = _setmod


class Repeat(addons.AddonMainTask, block.SBlock):
    """
    Periodically repeat the last received event.
    """

    def __init__(
            self, *args,
            dest: str|block.SBlock,
            etype: str|block.EventType = 'put',
            interval: int|float|str,
            count: Optional[int] = None,
            **kwargs):
        if isinstance(etype, block.EventCond):
            raise ValueError("An EventCond event cannot be repeated.")
        self._repeated_event = block.Event(dest, etype)
        self._interval = utils.time_period(interval)
        if self._interval is None or self._interval <= 0.0:
            raise ValueError("interval must be positive")
        if count is not None and count < 0:
            # count = 0 (no repeating) is accepted
            raise ValueError("argument 'count' must not be negative")
        self._queue: asyncio.Queue
        self._count = count
        self._warning_logged = False
        super().__init__(*args, **kwargs)

    def init_regular(self) -> None:
        self.set_output(0)

    async def _maintask(self) -> NoReturn:
        repeating = False
        while True:
            if repeating:
                try:
                    data = await asyncio.wait_for(self._queue.get(), self._interval)
                    repeat = 0
                except asyncio.TimeoutError:
                    repeat += 1
            else:
                # avoid wait_for() overhead when not repeating an event
                data = await self._queue.get()
                repeat = 0

            if repeat > 0:  # skip the original event
                self.set_output(repeat)
                self._repeated_event.send(self, **data, repeat=repeat)
            repeating = self._count is None or repeat < self._count

    def _event(self, etype: str|block.EventType, data) -> None:
        if etype != self._repeated_event.etype:
            if not self._warning_logged:
                self.log_warning(
                    f"Unexpected event type {etype} (this error is logged only once)")
                self._warning_logged = True
            return
        # send the original event synchronously in order
        # not to conceal a possible forbidden loop
        data['orig_source'] = data.get('source')
        self.set_output(0)
        self._repeated_event.send(self, **data, repeat=0)
        self._queue.put_nowait(data)

    def start(self) -> None:
        super().start()
        self._queue = asyncio.Queue()


class ValuePoll(addons.AddonMainTask, addons.AddonAsyncInit, block.SBlock):
    """
    A source of measured or computed values.
    """

    def __init__(self, *args, func: Callable[[], Any], interval: int|float|str, **kwargs):
        self._func = func
        self._interval = utils.time_period(interval)
        if self._interval is None or self._interval <= 0.0:
            raise ValueError("interval must be positive")
        super().__init__(*args, **kwargs)

    async def _maintask(self) -> NoReturn:
        """Data acquisition task: repeatedly obtain a value."""
        while True:
            value = self._func()
            if asyncio.iscoroutine(value):
                value = await value
            if value is not block.UNDEF:
                self.set_output(value)
            await asyncio.sleep(self._interval)

    def init_from_value(self, value: Any) -> None:
        self.set_output(value)

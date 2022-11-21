"""
Add-ons extending SBlocks' capabilities.

For each add-on there is usually also a supporting code in
the simulator.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Coroutine
import time
from typing import Any, Optional

from . import block
from .exceptions import add_note, EdzedCircuitError
from . import utils


__all__ = ['AddonAsync', 'AddonAsyncInit', 'AddonMainTask', 'AddonPersistence']


class AddonPersistence(block.Addon, metaclass=abc.ABCMeta):
    """
    Add support for persistent state to a SBlock.
    """

    def __init__(
            self,
            *args,
            persistent: bool = False,
            sync_state: bool = True,
            expiration: Optional[int|float|str] = None,
            **kwargs):
        self.persistent = bool(persistent)
        self.sync_state = bool(sync_state)
        self.expiration = utils.time_period(expiration)
        super().__init__(*args, **kwargs)
        # str(self) (as defined in superclass!) is used as a key instead of
        # just the name, because it contains also the block type name.
        self.key = str(self)

    def event(self, etype: str|block.EventType, /, **data) -> Any:
        """Save persistent state after a possible state change."""
        try:
            retval = super().event(etype, **data)
        except Exception:
            if self.persistent and not self.circuit.is_ready():
                # The internal state data may be corrupted, because it looks like
                # event() decided to stop the simulation in reaction to this exception.
                # (Never mind if it wasn't this exception but some previous one.)
                self.log_warning("Disabling persistent state due to an error")
                self.persistent = False
            raise
        if self.persistent and self.sync_state:
            self.save_persistent_state()
        return retval

    def save_persistent_state(self) -> None:
        """
        Save the state to persistent storage if enabled. Suppress errors.
        """
        if not self.persistent:
            return
        try:
            self.circuit.persistent_dict[self.key] = self.get_state()
        except Exception as err:
            self.log_warning("Persistent data save error: %s", err)
            self.circuit.persistent_dict.pop(self.key, None)  # remove stale data

    @abc.abstractmethod
    def _restore_state(self, state: Any, /) -> None:
        """
        Initialize by restoring the state (low-level).
        """

    def init_from_persistent_data(self) -> None:
        """
        Initialize by restoring the saved state (high-level).

        Load the state from persistent storage and apply it.
        Errors are suppressed.
        """
        try:
            state = self.circuit.persistent_dict[self.key]
        except KeyError:
            return
        except Exception as err:
            self.log_warning("Persistent data retrieval error: %s", err)
            return
        exp = self.expiration
        if exp is not None:
            if exp <= 0.0:
                return
            ts = self.circuit.persistent_ts
            if ts is not None and ts + exp < time.time():
                self.log_debug("The internal state has expired.")
                return
        try:
            self._restore_state(state)
        except Exception as err:
            self.log_warning("Error restoring saved state: %s; state: %s", err, state)

    def get_conf(self) -> dict[str, Any]:
        return {
            'persistent': self.persistent,
            **super().get_conf()
        }


DEFAULT_INIT_TIMEOUT = 10.0
DEFAULT_STOP_TIMEOUT = 10.0
class AddonAsync(block.Addon):
    """
    Asynchronous support add-on.
    """

    def __init__(self, *args, **kwargs):
        """
        Parameters:
            init_timeout:
                init_async() timeout in seconds (default=10),
                valid only if the init_async method is defined.
                Value 0.0 (or negative) disables the init_async().
            stop_timeout:
                stop_async() timeout in seconds (default=10),
                valid only if the stop_async() method is defined.
                Value 0.0 (or negative) disables the stop_async().

        All timeouts are in seconds (int or float). Value None or a
        missing argument are replaced by the default timeout.
        """
        init = self.has_method('init_async')
        if init:
            self.init_timeout = utils.time_period(kwargs.pop('init_timeout', None))
        elif 'init_timeout' in kwargs:
            raise TypeError(
                "'init_timeout' argument rejected, because init_async() method is missing")
        stop = self.has_method('stop_async')
        if stop:
            self.stop_timeout = utils.time_period(kwargs.pop('stop_timeout', None))
        elif 'stop_timeout' in kwargs:
            raise TypeError(
                "'stop_timeout' argument rejected, because stop_async() method is missing")
        super().__init__(*args, **kwargs)
        # cannot use self.log before Block.__init__()
        if init and self.init_timeout is None:
            self.log_debug("init_timeout not set, default is %.3fs", DEFAULT_INIT_TIMEOUT)
            self.init_timeout = DEFAULT_INIT_TIMEOUT
        if stop and self.stop_timeout is None:
            self.log_debug("stop_timeout not set, default is %.3fs", DEFAULT_STOP_TIMEOUT)
            self.stop_timeout = DEFAULT_STOP_TIMEOUT

    async def _task_monitor(self, coro: Coroutine, is_service: bool = False) -> Any:
        """
        A coroutine wrapper delivering exceptions to the simulator.

        Couroutines marked as services (is_service=True) are supposed
        to run until cancelled - even a normal exit is treated as an error.

        Cancellation is not considered an error.
        """
        try:
            retval = await coro
            if is_service:
                raise EdzedCircuitError("Unexpected task termination")
        except Exception as err:
            add_note(err, f"block {self}, coroutine: {coro.__qualname__}")
            self.circuit.abort(err)
            raise
        return retval

    def _create_monitored_task(
            self,
            coro: Coroutine, is_service: bool = False, **task_kwargs) -> asyncio.Task:
        return asyncio.create_task(self._task_monitor(coro, is_service), **task_kwargs)


class AddonMainTask(AddonAsync, metaclass=abc.ABCMeta):
    """
    An add-on running a '_maintask' from start() till stop().
    """

    def __init__(self, *args, **kwargs):
        self._mtask = None
        super().__init__(*args, **kwargs)

    @abc.abstractmethod
    async def _maintask(self):
        pass

    def start(self) -> None:
        super().start()
        assert self._mtask is None
        self._mtask = self._create_monitored_task(
            self._maintask(), is_service=True, name=f"edzed: main task for block {self.name!r}")

    async def stop_async(self) -> None:
        self._mtask.cancel()
        try:
            await self._mtask
        except asyncio.CancelledError:
            pass
        finally:
            self._mtask = None
        await super().stop_async()


class AddonAsyncInit(AddonAsync, metaclass=abc.ABCMeta):
    """
    Add init_async() waiting for the first output value.
    """

    def __init__(self, *args, **kwargs):
        self._init_event = None
        super().__init__(*args, **kwargs)

    def start(self) -> None:
        super().start()
        self._init_event = asyncio.Event()

    def set_output(self, value: Any) -> None:
        super().set_output(value)
        if not self._init_event.is_set():
            self._init_event.set()

    async def init_async(self) -> None:
        await self._init_event.wait()

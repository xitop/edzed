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
from typing import Any, Optional, TYPE_CHECKING

from . import block
from .exceptions import add_note, EdzedCircuitError, EdzedInvalidState
from . import utils


__all__ = ['AddonAsync', 'AddonAsyncInit', 'AddonMainTask', 'AddonPersistence']


if TYPE_CHECKING:
    Addon = block.SBlock        # pretend to be a subclass, not a mix-in
    assert not TYPE_CHECKING    # for static type checking only, cannot run in this mode
else:
    Addon = block.Addon


class AddonPersistence(Addon, metaclass=abc.ABCMeta):
    """
    Add support for persistent state to a SBlock.
    """

    def __init__(
            self,
            *args,
            persistent: bool = False,
            sync_state: bool = True,
            expiration: Optional[float|str] = None,
            **kwargs) -> None:
        self.persistent: bool = bool(persistent)
        self.sync_state: bool = bool(sync_state)
        self.expiration: float = utils.time_period(expiration)
        super().__init__(*args, **kwargs)
        # str(self) (as defined in superclass!) is used as a key instead of
        # just the name, because it contains also the block type name.
        self.key: str = str(self)

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
        persistent_dict = self.circuit.persistent_dict
        # during the finalization the persistent flag gets disabled if there is no storage
        assert persistent_dict is not None, f"{self}: circuit not finalized"
        try:
            persistent_dict[self.key] = self.get_state()
        except Exception as err:
            self.log_warning("Persistent data save error: %s", err)
            persistent_dict.pop(self.key, None)  # remove stale data

    @abc.abstractmethod
    def _restore_state(self, state: Any, /) -> Any:
        """
        Initialize by restoring the state (low-level).

        The return value is ignored.
        """

    def init_from_persistent_data(self) -> None:
        """
        Initialize by restoring the saved state (high-level).

        Load the state from persistent storage and apply it.
        Errors are suppressed.
        """
        assert self.circuit.persistent_dict is not None
        try:
            state = self.circuit.persistent_dict[self.key]
        except KeyError:
            return
        except Exception as err:
            self.log_warning("Persistent data retrieval error: %s", err)
            return
        if (exp := self.expiration) is not None:
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
class AddonAsync(Addon):
    """
    Asynchronous support add-on.
    """

    def __init__(self, *args, **kwargs) -> None:
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
        self.init_timeout: float
        self.stop_timeout: float
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

        Coroutines marked as services (is_service=True) are supposed
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
            coro: Coroutine,
            is_service: bool = False, **task_kwargs) -> asyncio.Task:
        return asyncio.create_task(self._task_monitor(coro, is_service), **task_kwargs)


class AddonMainTask(AddonAsync, metaclass=abc.ABCMeta):
    """
    An add-on running a '_maintask' from start() till stop().
    """

    def __init__(self, *args, **kwargs) -> None:
        self._mtask: Optional[asyncio.Task] = None
        task_keys = [key for key in kwargs if key.startswith("task_")]
        self._task_kwargs = {key[5:]: kwargs.pop(key) for key in task_keys}
        super().__init__(*args, **kwargs)
        if "task_name" not in task_keys:
            # self.name is defined by super().__init__
            self._task_kwargs["name"] = f"edzed: main task for block {self.name!r}"

    @abc.abstractmethod
    async def _maintask(self):
        pass

    async def _maintask_with_wait_init(self):
        try:
            await self.circuit.wait_init()
        except EdzedInvalidState:
            # this error is handled elsewhere, do not add more error messages
            return
        await self._maintask()

    def start(self) -> None:
        super().start()
        assert self._mtask is None, f"{self}: start() called twice?"
        wait_init = AddonAsyncInit not in type(self).__mro__
        self._mtask = self._create_monitored_task(
            self._maintask_with_wait_init() if wait_init else self._maintask(),
            is_service=True,
            **self._task_kwargs)

    async def stop_async(self) -> None:
        assert self._mtask is not None, f"{self}: start() not called"
        self._mtask.cancel()
        try:
            await self._mtask
        except asyncio.CancelledError:
            pass
        finally:
            self._mtask = None
        # super() refers to an SBlock, pylint cannot know that
        # pylint: disable=no-value-for-parameter
        await super().stop_async()


class AddonAsyncInit(AddonAsync, metaclass=abc.ABCMeta):
    """
    Add init_async() waiting for the first output value.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._init_event: Optional[asyncio.Event] = None
        super().__init__(*args, **kwargs)

    def start(self) -> None:
        self._init_event = asyncio.Event()
        super().start()

    def set_output(self, value: Any) -> None:
        assert self._init_event is not None, f"{self}: start() not called"
        super().set_output(value)
        if not self._init_event.is_set():
            self._init_event.set()

    async def init_async(self) -> None:
        assert self._init_event is not None, f"{self}: start() not called"
        await self._init_event.wait()

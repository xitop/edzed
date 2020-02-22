"""
Add-ons extending SBlocks' capabilities.

For each add-on there is usually also a supporting code in
the simulator.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import abc
import asyncio
from typing import Any, Awaitable, Mapping, Union

from . import block
from .exceptions import EdzedError


__all__ = ['AddonAsync', 'AddonMainTask', 'AddonPersistence']


class AddonPersistence(block.Addon, metaclass=abc.ABCMeta):
    """
    Add support for persistent state to a SBlock.
    """

    def __init__(self, *args, persistent: bool = False, sync_state: bool = True, **kwargs):
        self.persistent = bool(persistent)
        self.sync_state = bool(sync_state)
        super().__init__(*args, **kwargs)
        # str(self) (as defined in superclass!) is used as a key instead of
        # just the name, because it contains also the block type name.
        self.key = str(self)

    # TODO in Python3.8+ (see Block.event for an explanation):
    #   def event(self, etype: Union[str, block.EventType], /, **data) -> Any:
    # pylint: disable=no-method-argument
    def event(*args, **data) -> Any:
        """Save persistent state after a possible state change."""
        self, etype = args
        try:
            # TODO in Python3.8+: super().event
            retval = super(AddonPersistence, self).event(etype, **data)
        except Exception:
            if self.persistent and not self.circuit.is_ready():
                # The internal state data may be corrupted, because it looks like
                # event() decided to stop the simulation in reaction to this exception.
                # (Never mind if it wasn't this exception but some previous one.)
                self.warn("Disabling persistent state due to an error")
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
            self.warn("Persistent data save error: %s", err)
            self.circuit.persistent_dict.pop(self.key, None)  # remove stale data

    @abc.abstractmethod
    def _restore_state(self, state: Any) -> None:
        """
        Initialize by restoring the state (low-level).
        """

    def init_from_persistent_data(self) -> None:
        """
        Initialize by restoring the saved state (high-level).

        Load the state from persistent storage and apply it.

        IMPORTANT: output change events are temporarily disabled
        when loading the saved state.

        Errors are suppressed.
        """
        try:
            state = self.circuit.persistent_dict[self.key]
        except KeyError:
            return
        except Exception as err:
            self.warn("Persistent data retrieval error: %s", err)
            return
        try:
            self._restore_state(state)
        except Exception as err:
            self.warn("Error restoring saved state: %s; state: %s", err, state)

    def get_conf(self) -> Mapping[str, Any]:
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
            self.init_timeout = kwargs.pop('init_timeout', None)
        stop = self.has_method('stop_async')
        if stop:
            self.stop_timeout = kwargs.pop('stop_timeout', None)
        super().__init__(*args, **kwargs)
        # cannot use self.log before Block.__init__()
        if init and self.init_timeout is None:
            self.log("init_timeout not set, default is %.3fs", DEFAULT_INIT_TIMEOUT)
            self.init_timeout = DEFAULT_INIT_TIMEOUT
        if stop and self.stop_timeout is None:
            self.log("stop_timeout not set, default is %.3fs", DEFAULT_STOP_TIMEOUT)
            self.stop_timeout = DEFAULT_STOP_TIMEOUT

    async def _task_wrapper(self, coro: Awaitable, is_service: bool = False) -> Any:
        """
        A coroutine wrapper delivering exceptions to the simulator.

        Couroutines marked as services (is_service=True) are supposed
        to run until cancelled - a normal exit is treated as an error.

        Cancellation is not considered an error.
        """
        try:
            retval = await coro
            if is_service:
                raise EdzedError("coroutine providing a service has exited")
        # not needed in Python 3.8+
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except Exception as err:
            # add context to the error message
            fmt = f"{self}: error in {coro.__qualname__}: {{}}"
            err.args = (fmt.format(err.args[0] if err.args else "<NO ARGS>"), *err.args[1:])
            self.circuit.abort(err)
            raise
        return retval


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
        self._mtask = asyncio.create_task(self._task_wrapper(self._maintask(), is_service=True))

    async def stop_async(self) -> None:
        if self._mtask is None:
            return
        self._mtask.cancel()
        try:
            await self._mtask
        except asyncio.CancelledError:
            pass
        finally:
            self._mtask = None
        await super().stop_async()

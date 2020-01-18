"""
Add-ons extending SBlocks' capabilities.

For each add-on there is usually also a supporting code in
the simulator.
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

    The internal state (as returned by get_state()) can be saved to
    persistent storage provided by the circuit. Instances can enable
    persistent state feature with the 'persistent' parameter.

    The saved state is restored by _restore_state(). That function is
    a counterpart to get_state(). The default _restore_state matches
    the default get_state and sets the block's output. Blocks with
    different internal state must customize both their get_state
    and _restore_state.

    If enabled, the state is saved:
        - by calling save_persistent_state() explicitly
        - at the end of a simulation
        - by default also after each event, this can be disabled
          with 'sync_state=False'.

    Saving of persistent state is disabled after an error in event()
    in order to prevent saving of possibly corrupted state.
    """

    def __init__(self, *args, persistent: bool = False, sync_state: bool = True, **kwargs):
        self.persistent = bool(persistent)
        self.sync_state = bool(sync_state)
        #self._loading_persistent_state = False
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
            self.circuit.persistent_data[self.key] = self.get_state()
        except Exception as err:
            self.warn("Persistent data save error: %s", err)
            self.circuit.persistent_data.pop(self.key, None)  # remove stale data

    @abc.abstractmethod
    def _restore_state(self, state: Any) -> None:
        """
        Initialize by restoring the state (low-level).

        It is assumed that the state was created by get_state().

        Restore the state and the output. If the data is not valid,
        log a warning and leave the block uninitialized; do not raise.

        Note that _restore_state() is often identical to
        init_from_value().
        """

    def init_from_persistent_data(self) -> None:
        """
        Initialize by restoring the saved state (high-level).

        Load the state from persistent storage and apply it.

        IMPORTANT: output change events are temporarily disabled
        when loading the saved state.

        Errors are suppressed. Use self.is_initialized() to check
        the outcome.

        The simulator calls this function only if it is required
        and the persistent data feature is enabled.
        """
        try:
            state = self.circuit.persistent_data[self.key]
        except KeyError:
            return
        except Exception as err:
            self.warn("Persistent data retrieval error: %s", err)
            return
        #self._loading_persistent_state = True
        try:
            self._restore_state(state)
        except Exception as err:
            self.warn("Error restoring saved state: %s; state: %s", err, state)
        #self._loading_persistent_state = False

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

    Contents:
        init_async() - optional async initialization
        stop_async() - optional async cleanup
        _task_wrapper() - an error handling helper

    init_async
    ----------
    If needed, define the async initialization coroutine:
        async def init_async(self):

    The async initialization is intended to interact with external
    systems and as such should be utilized solely by circuit inputs.

    init_async() is run as a task and is waited for 'init_timeout'
    seconds. When a timeout occurs, the task is cancelled and the
    initialization continues with the next step.

    Implementation detail: The simulator may wait longer than
    specified if it is also concurrently initializing another
    AddonAsync block with a longer init_timeout.

    Should an event arrive during the async initialization, the block
    will get a regular Circuit.init_sblock() initialization in order to
    be able to process the event immediately. If a block is accepting
    events, init_async() should be able to handle this case.

    stop_async
    ----------
    If needed, define the async cleanup coroutine:
        async def stop_async(self):

    This coroutine is awaited after regular stop().

    stop_async() is run as a task and is waited for 'stop_timeout'
    seconds. When a timeout occurs, the task is cancelled.
    The simulator logs the error and continues the cleanup.

    Tip: use edzed.utils.shield_cancel() to protect small critical
    task sections from immediate cancellation.
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

        It is not possible to completely disable a timeout, but a large
        value (e.g. 1 day = 86400) has a similar effect.
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

        Cancellation is not considered an error, of course.
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

"""
Simple event-driven zero-delay logic/digital circuit simulation.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import asyncio
import fnmatch
import logging
import operator
from typing import Any, Iterator, Mapping, Optional

from . import addons
from . import block
from .blocklib import cblocks
from .blocklib import sblocks1
from .exceptions import EdzedError, EdzedInvalidState


__all__ = ['get_circuit', 'reset_circuit']

# limit for oscillation/instability detection:
_MAX_EVALS_PER_BLOCK = 3


_logger = logging.getLogger(__package__)
_current_circuit = None


def get_circuit() -> 'Circuit':
    """Get the current circuit. Create one if it does not exist."""
    global _current_circuit

    if _current_circuit is None:
        _current_circuit = Circuit()
    return _current_circuit


def reset_circuit() -> None:
    """
    Clear the circuit and create a new one.
    """
    global _current_circuit

    if _current_circuit is None:
        return
    try:
        _current_circuit.abort(EdzedError('forced circuit reset'))  # ignored if not running
    except Exception as err:
        # e.g. RuntimeError: Event loop is closed
        _logger.warning("reset_circuit(): %r error ignored", err)
    block.Event.instances.clear()
    _current_circuit = Circuit()


class Circuit:
    """
    A container of all blocks and their interconnections.

    Not to be instantiated directly, rather call edzed.get_circuit().

    There exist only one circuit at a time and all created blocks
    belongs to it.

    In this implementation, circuit blocks can be added, but not removed.
    """

    def __init__(self):
        self._blocks = {}           # all blocks belonging to this circuit by name
        self._simtask = None        # task running run_forever
        self._finalized = False     # no circuit modification after the initialization
        self._error = None          # exception that terminated the simulator or None
        self.persistent_dict = None # persistent state data back-end
        self.sblock_queue = None    # a Queue for notifying about changed SBlocks,
                                    # the queue will be created when simulation starts, because
                                    # it has a side effect of creating an event_loop if one
                                    # was not created yet. That may lead to errors in rare
                                    # scenarios with asyncio.new_event_loop().
        self._init_done = None      # an Event for wait_init() synchronization

    def is_current_task(self) -> bool:
        """Return True if the simulator task is the current asyncio task."""
        if self._simtask is None:
            return False
        try:
            return self._simtask == asyncio.current_task()
        except Exception:
            # for instance RuntimeError('no running event loop')
            return False

    def is_finalized(self) -> bool:
        """Return True only if finalize() was called."""
        return self._finalized

    def is_ready(self) -> bool:
        """Return True only if ready to accept external events."""
        return self._simtask is not None and self._error is None

    @property
    def error(self) -> Optional[BaseException]:
        return self._error

    async def _check_started(self) -> None:
        """Raise if the simulation was not started yet."""
        if self._simtask is None:
            # just created?
            await asyncio.sleep(0)
            if self._simtask is None:
                raise EdzedInvalidState("The simulation task was not started")

    async def wait_init(self) -> None:
        """Wait until a running circuit is fully initialized."""
        await self._check_started()
        await asyncio.wait(
            [asyncio.create_task(self._init_done.wait()), self._simtask],
            return_when=asyncio.FIRST_COMPLETED)
        if self._simtask.done():
            if self._simtask.cancelled():
                msg = "The simulation task is finished"
            else:
                # normal simtask exit is not possible
                msg = f"The simulation task failed with error: {self._simtask.exception()}"
            raise EdzedInvalidState(msg)

    def check_not_finalized(self) -> None:
        """Raise an error if the circuit has been finalized."""
        if self._error:
            # there is an even bigger problem
            raise EdzedInvalidState("The circuit was shut down")
        if self._finalized:
            raise EdzedInvalidState("No changes allowed in a finalized circuit")

    def set_persistent_data(self, persistent_dict: Optional[Mapping[str, Any]]) -> None:
        """Setup the persistent state data storage."""
        self.check_not_finalized()
        self.persistent_dict = persistent_dict

    def addblock(self, blk: block.Block) -> None:
        """
        Add a circuit block. Not an ad blocker :-)

        Application code does not call this method, because
        blocks register themselves automatically when created.
        """
        self.check_not_finalized()
        if not isinstance(blk, block.Block):
            raise TypeError(f"Expected a Block object, got {blk!r}")
        if blk.name in self._blocks:
            raise ValueError(f"Duplicate block name {blk.name}")
        self._blocks[blk.name] = blk

    def getblocks(self, btype: Optional[block.Block] = None) -> Iterator:
        """Return an iterator of all blocks or btype blocks only."""
        allblocks = self._blocks.values()
        if btype is None:
            return allblocks
        return (blk for blk in allblocks if isinstance(blk, btype))

    def findblock(self, name: str) -> block.Block:
        """Get block by name. Raise a KeyError when not found."""
        try:
            return self._blocks[name]
        except KeyError:
            # add an error message
            raise KeyError(f"Block '{name}' not found") from None

    def set_debug(self, value: bool, *args) -> int:
        """
        Set debug flag to given value (True/False) for selected blocks.
        """
        todo = set()
        for arg in args:
            if isinstance(arg, str):
                if any(ch in arg for ch in '*?['):
                    for blk in self.getblocks():
                        if fnmatch.fnmatchcase(blk.name, arg):
                            todo.add(blk)
                else:
                    todo.add(self.findblock(arg))
            elif isinstance(arg, block.Block):
                todo.add(arg)
            # issubclass works only for classes
            elif isinstance(arg, type) and issubclass(arg, block.Block):
                for blk in self.getblocks(arg):
                    todo.add(blk)
            else:
                raise TypeError(f"Expected block name, Block object or subclass, got {arg!r}")
        value = bool(value)
        for blk in todo:
            blk.debug = value
        return len(todo)

    def _check_persistent_data(self):
        """Check persistent state related settings."""
        persistent_blocks = [
            blk for blk in self.getblocks(addons.AddonPersistence) if blk.persistent]
        if self.persistent_dict is None:
            if persistent_blocks:
                _logger.warning(
                    "Disabling all persistent state, because the data storage was not set")
                for blk in persistent_blocks:
                    blk.persistent = False
        else:
            # clear the unused items
            used_keys = {blk.key for blk in persistent_blocks}
            for key in list(self.persistent_dict):
                if key not in used_keys:
                    _logger.info("Removing unused persistent state for '%s'", key)
                    del self.persistent_dict[key]

    def _validate_blk(self, blk):
        """
        Process a block specification. Return a valid block object.

        If the block is given by name, get the corresponding block.
        If a value is given, create a Const block from it.
        """
        if isinstance(blk, block.Const):
            return blk
        if isinstance(blk, str):
            # '_not_' + any 'NAME' except '_NAME'
            if blk.startswith('_') and blk not in self._blocks:
                # automatic blocks:
                if blk == '_ctrl':
                    return sblocks1.ControlBlock(
                        blk, desc="Simulation Control Block", _reserved=True)
                if blk.startswith('_not_') and blk[5:6] != '_':
                    return cblocks.Invert(
                        blk, desc=f"Inverted output of {blk}", _reserved=True
                        ).connect(blk[5:])
            return self.findblock(blk)
        if not isinstance(blk, block.Block):
            return block.Const(blk)
        if blk not in self.getblocks():
            raise ValueError(f"{blk} is not in the current circuit")
        return blk

    def _resolve_events(self):
        """Resolve temporary references by name in Event objects."""
        for event in block.Event.instances:
            if isinstance(event.dest, str):
                event.dest = self._validate_blk(event.dest)
            if not isinstance(event.dest, block.SBlock):
                raise ValueError(
                    f"Event destination block {event.dest} is not a sequential block")
        block.Event.instances.clear()   # free some memory

    def _finalize(self):
        """
        Complete the initialization of circuit block interconnections.

        For each block:
          - resolve temporary references by name
          - create Invert blocks for _not_name shortcuts
          - update connection data
        """
        def validate_output(iblk, oblk):
            """Validate oblk as a block to be connected to iblk."""
            try:
                return self._validate_blk(oblk)
            except Exception as err:
                fmt = f"Cannot connect {oblk} --> {iblk}: {{}}"
                err.args = (fmt.format(err.args[0]) if err.args else "<NO ARGS>", *err.args[1:])
                raise

        for btype in (block.CBlock, cblocks.Invert):
            # doing two passes because the first one may create new Invert blocks
            # some Invert blocks may be processed twice, that's acceptable
            for blk in list(self.getblocks(btype)):
                all_inputs = []
                for iname, inp in blk.inputs.items():
                    if isinstance(inp, tuple):
                        newinp = tuple(validate_output(blk, i) for i in inp)
                        all_inputs.extend(newinp)
                    else:
                        newinp = validate_output(blk, inp)
                        all_inputs.append(newinp)
                    blk.inputs[iname] = newinp

                for inp in all_inputs:
                    if not isinstance(inp, block.Const):
                        blk.iconnections.add(inp)
                        self._blocks[inp.name].oconnections.add(blk)

    def finalize(self):
        """A wrapper for _finalize()."""
        if not self._finalized:
            self._finalize()
            self._finalized = True

    async def _run_tasks(self, jobname, btt_list):
        """
        Run multiple tasks concurrently. Log errors.

        jobname is a description (e.g. "init" or "stop") used
        in messages. btt_list is a list of (block, task, timeout).
        It must not be empty.
        """
        assert btt_list
        errcnt = 0
        get_time = asyncio.get_running_loop().time
        start_time = get_time()
        for blk, task, timeout in sorted(btt_list, key=operator.itemgetter(2), reverse=True):
            # sorted from longest timeout
            if not task.done():
                try:
                    await asyncio.wait_for(task, timeout - get_time() + start_time)
                except asyncio.TimeoutError:
                    errcnt += 1
                    blk.warn("%s timeout, check timeout value (%.1fs)", jobname, timeout)
            if task.done() and not task.cancelled():
                err = task.exception()
                if err is not None:
                    errcnt += 1
                    blk.warn("%s error: %s", jobname, err, exc_info=err)
        if errcnt:
            _logger.error("%d block %s error(s) suppressed", errcnt, jobname)

    async def _init_sblocks_async(self):
        """Initialize all sequential blocks, the async part."""
        start_tasks = [
            (blk, asyncio.create_task(blk.init_async()), blk.init_timeout)
            for blk in self.getblocks(addons.AddonAsync)
            if blk.has_method('init_async') and blk.init_timeout > 0.0]
        if start_tasks:
            _logger.debug("Initializing async sequential blocks")
            await self._run_tasks("async init", start_tasks)

    @staticmethod
    def init_sblock(blk: block.Block) -> None:
        """
        Initialize a SBlock skipping any async code.

        Initialization order:
            - call init_from_persistent_data - if applicable
            - if not initialized, call init_regular
            - if not initialized, call init_from_value with the initdef
              value - if applicable

        After the init_sblock, a block:
            - MAY NOT be initialized, but
            - MUST be able to process events. An event is block's last
              chance to get its initialization. The simulation will
              fail unless all blocks are initialized properly.
        """
        if blk.is_initialized():
            return
        try:
            if isinstance(blk, addons.AddonPersistence) and blk.persistent:
                blk.init_from_persistent_data()
                if blk.is_initialized():
                    blk.log("initialized from saved state")
                    return
            blk.init_regular()
            if not blk.is_initialized() and  blk.has_method('init_from_value') \
                    and blk.initdef is not block.UNDEF:
                blk.init_from_value(blk.initdef)
        except Exception as err:
            # add the block name
            fmt = f"{blk}: error during initialization: {{}}"
            err.args = (fmt.format(err.args[0]) if err.args else "<NO ARGS>", *err.args[1:])
            raise

    def _init_sblocks_sync(self):
        """Initialize all sequential blocks, the non async part."""
        for blk in self.getblocks(block.SBlock):
            self.init_sblock(blk)
            if not blk.is_initialized():
                raise EdzedError(f"{blk}: not initialized")
        # save the internal states after initialization
        if self.persistent_dict is not None:
            for blk in self.getblocks(addons.AddonPersistence):
                blk.save_persistent_state()
        # clear the queue, the simulator knows that it needs to evaluate everything
        queue = self.sblock_queue
        while not queue.empty():
            queue.get_nowait()

    async def _stop_sblocks(self):
        """
        Stop all sequential blocks. Wait until all blocks are stopped.

        Suppress errors.
        """
        for blk in self.getblocks(block.SBlock):
            try:
                blk.stop()
            except Exception:
                _logger.error("%s: ignored error in stop()", blk, exc_info=True)
        await asyncio.sleep(0)
        wait_tasks = [
            (blk, asyncio.create_task(blk.stop_async()), blk.stop_timeout)
            for blk in self.getblocks(addons.AddonAsync)
            if blk.has_method('stop_async') and blk.stop_timeout > 0.0]
        if wait_tasks:
            _logger.debug("Waiting for async cleanup")
            await self._run_tasks("stop", wait_tasks)

    async def _simulate(self):
        """
        Simulate the circuit until cancelled.

        On first run evaluate all blocks with inputs (i.e. CBlocks).
        Then evaluate all blocks directly connected to:
            - changed sequential blocks
            - changed evaluated blocks
        """
        def select_blk(block_set):
            """
            Return one block from the given set with minimum number of
            its inputs connected to another block within the set.
            The set must not be empty.
            """
            min_idep = min_blk = None
            for blk in block_set:
                idep = sum(1 for inp in blk.iconnections if inp in block_set)
                if idep == 0:
                    # 0 is the absolute minimum, no need to search further
                    return blk
                if min_idep is None or idep < min_idep:
                    min_idep = idep
                    min_blk = blk
            return min_blk

        eval_limit = _MAX_EVALS_PER_BLOCK * len(self._blocks)
        eval_set = set(self.getblocks(block.CBlock))
        eval_cnt = 0
        queue = self.sblock_queue
        while True:
            if not eval_set and queue.empty():
                _logger.debug("%d block(s) evaluated, pausing", eval_cnt)
                blk = await queue.get()
                _logger.debug("output change in %s, resuming", blk)
                eval_cnt = 0
                eval_set |= blk.oconnections
            while not queue.empty():
                blk = queue.get_nowait()
                eval_set |= blk.oconnections
            if not eval_set:
                continue
            eval_cnt += 1
            if eval_cnt > eval_limit:
                raise EdzedError(
                    "Circuit instability detected (too many block evaluations)")
            if len(eval_set) == 1:
                blk = eval_set.pop()
            else:
                blk = select_blk(eval_set)
                eval_set.discard(blk)
            try:
                changed = blk.eval_block()
            except Exception as err:
                # add the block name
                fmt = f"{blk}: Error while evaluating block: {{}}"
                err.args = (fmt.format(err.args[0]) if err.args else "<NO ARGS>", *err.args[1:])
                raise
            if changed:
                eval_set |= blk.oconnections

    async def run_forever(self):    # no return value
        """
        Run the circuit simulation until the coroutine is cancelled.

        run_forever() never exits normally without an exception. It must
        be cancelled to stop the simulation.

        Please note that the cleanup could take some time - up to the
        max of SBlocks' stop_timeout values.

        When run_forever terminates, it cannot be invoked again.

        See also the ready attribute and wait_init().
        """
        if self._simtask is not None:
            if self._simtask.done():
                msg = "Cannot restart a finished simulation."
            else:
                msg = "The simulator is already running."
            raise EdzedInvalidState(msg)
        self._simtask = asyncio.current_task()
        blocks_started = False
        try:
            try:
                if self._error is not None:
                    raise self._error       # stop before start
                if not self._blocks:
                    raise EdzedError("The circuit is empty")

                _logger.debug("Initializing the circuit")
                self.sblock_queue = asyncio.Queue()
                self._init_done = asyncio.Event()
                self._check_persistent_data()
                self._resolve_events()
                self.finalize()

                _logger.debug("Setting up circuit blocks")
                blocks_started = True
                for blk in self.getblocks():
                    blk.start()
                # return control to the loop in order to run any tasks created by start()
                await asyncio.sleep(0)
                await self._init_sblocks_async()
                _logger.debug("Initializing sequential blocks")
                self._init_sblocks_sync()

                if self._error is None:
                    _logger.debug("Starting simulation")
                    self._init_done.set()
                    await self._simulate()
                    # not reached
                    assert False
            # CancelledError is derived from BaseException, (not Exception) in Python 3.8+
            except (Exception, asyncio.CancelledError) as err:
                if self._error is None:
                    self._error = err
            # Normally when a function from the try-except clause above calls abort(), the
            # abort() sets the self._error and cancels the task. The exception clause then
            # catches the cancellation.
            # But when a function calls abort() and also raises, the exception clause
            # catches the exception and the cancellation is left pending. For this
            # special edge case we must add a second except clause below.
            await asyncio.sleep(0)  # allow delivery of pending CancelledError if any
        except asyncio.CancelledError:
            pass

        if isinstance(self._error, asyncio.CancelledError):
            _logger.info("Normal circuit simulation stop")
        else:
            _logger.critical(
                "Fatal circuit simulation error: %s", self._error, exc_info=self._error)

        if blocks_started:
            # if blocks were started (at least some of them), they must be stopped
            # save the state first, because stop may invalidate the state information
            if self.persistent_dict is not None:
                for blk in self.getblocks(addons.AddonPersistence):
                    blk.save_persistent_state()
            await self._stop_sblocks()
        raise self._error

    def abort(self, exc: Exception) -> None:
        """
        Abort the circuit simulation due to an exception.

        abort() is necessary only when an ordinary exception wouldn't
        be propagated to the simulator. This is the case in asyncio
        tasks NOT using the SBlock._task_wrapper helper.

        The first error stops the simulation, that's why abort()
        delivers the exception only if the simulation hasn't received
        another exception already.

        abort() may be called even before the simulation begins.
        The start will then fail.
        """
        if self._error is not None:
            if not isinstance(exc, asyncio.CancelledError):
                _logger.warning("subsequent error: abort(%s)", exc)
            return
        if not isinstance(exc, BaseException):
            # one more reason to abort
            exc = TypeError(f'abort(): expected an exception, got {exc!r}')
        self._error = exc
        if self._simtask is not None and not self._simtask.done():
            self._simtask.cancel()

    async def shutdown(self) -> None:
        """
        Stop the simulation and wait until it finishes.
        """
        await self._check_started()
        if self.is_current_task():
            raise EdzedInvalidState("Cannot await the simulator task from the simulator task.")
        self.abort(asyncio.CancelledError('shutdown'))
        try:
            await self._simtask
        except asyncio.CancelledError:
            pass

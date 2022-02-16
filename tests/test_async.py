"""
Test asyncio related helpers.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio

import pytest

import edzed
from edzed.utils import shield_cancel

from .utils import *


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def test_shield():
    """Test without and with cancel_shield."""
    result = None

    async def shielded():
        nonlocal result
        for i in range(5):
            await asyncio.sleep(0.015)
            result += 1

    async def coro(shield):
        nonlocal result
        result = 0
        await (shield_cancel(shielded()) if shield else shielded())
        await asyncio.sleep(0.05)
        result = 99

    # without shield
    for t in range(10):
        task = asyncio.create_task(coro(False))
        await asyncio.sleep(t/100)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        if 0 < result < 5:
            break
    else:
        assert False, "test without shield failed"

    # with shield
    for t in range(10):
        task = asyncio.create_task(coro(True))
        await asyncio.sleep(t/100)
        # cancel_shield's main feature is that it can withstand repeated cancel
        task.cancel()
        await asyncio.sleep(0.005)
        task.cancel()
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert result == 5


async def test_init_timeout_acceptance(circuit):
    """Timeouts are valid only with the corresponding method defined."""
    class Incomplete(edzed.AddonAsync, edzed.SBlock):
        pass

    class Complete(Incomplete):
        async def init_async(self):
            pass
        async def stop_async(self):
            pass

    with pytest.raises(TypeError, match="init_async"):
        Incomplete('test1', init_timeout=3)
    with pytest.raises(TypeError, match="stop_async"):
        Incomplete('test2', stop_timeout=3)

    Complete('test3', init_timeout=3)
    Complete('test4', stop_timeout=3)


async def test_maintask(circuit):
    """Test the task monitoring in AddonMainTask (is_service=True)."""
    class Short(edzed.AddonMainTask, edzed.SBlock):
        async def _maintask(self):
            await asyncio.sleep(0.17)
        def init_regular(self):
            self.set_output(False)

    Short('short')
    logger = TimeLogger('logger', mstop=True)

    with pytest.raises(edzed.EdzedCircuitError, match="task termination"):
        await edzed.run(asyncio.sleep(1))

    logger.compare([(170, '--stop--')])


async def test_task_monitoring(circuit):
    """Test the task monitoring with is_service=False (default)."""
    async def coro(waitstates, fail=False):
        logger.put(f"start {waitstates}")
        await asyncio.sleep(waitstates * 0.05)
        if fail:
            raise RuntimeError("test error #999")
        logger.put(f"stop {waitstates}")

    class Worker(edzed.AddonMainTask, edzed.SBlock):
        async def _maintask(self):
            for i in range(1, 7):
                self._create_monitored_task(coro(i, i == 4))
            await asyncio.sleep(0.25) # will be cancelled at T=200 ms
            logger.put("notreached")
        def init_regular(self):
            self.set_output(False)

    Worker('block')
    logger = TimeLogger('logger', mstop=True)

    with pytest.raises(RuntimeError, match="#999"):
        await edzed.run()
    LOG = [
        (0, 'start 1'),
        (0, 'start 2'),
        (0, 'start 3'),
        (0, 'start 4'),
        (0, 'start 5'),
        (0, 'start 6'),
        (50, 'stop 1'),
        (100, 'stop 2'),
        (150, 'stop 3'),
        (200, '--stop--')]
    logger.compare(LOG)
    # prevent "Task was destroyed but it is pending!" error for tasks 5 and 6
    await asyncio.sleep(0.11)

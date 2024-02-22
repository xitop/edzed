"""
Test the Repeat block
"""

import asyncio

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import timelimit, TimeLogger


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def test_poll(circuit):
    """Test the basic value polling."""
    n = 0
    def acq():
        nonlocal n
        n += 1
        return n

    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=acq,
        interval='0m0.05s',
        on_output=edzed.Event(logger, 'log'))
    await edzed.run(asyncio.sleep(0.34))

    LOG = [
        (0, 1),
        (50, 2),
        (100, 3),
        (150, 4),
        (200, 5),
        (250, 6),
        (300, 7)]
    logger.compare(LOG)


async def test_async(circuit):
    """Test the basic value polling."""
    q = asyncio.Queue()
    for v in "AEI":
        q.put_nowait(v)

    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=q.get,
        interval='0m0.05s',
        on_output=edzed.Event(logger, 'log'))
    await edzed.run(asyncio.sleep(0.2))

    LOG = [
        (0, 'A'),
        (50, 'E'),
        (100, 'I')] # no more data in queue
    logger.compare(LOG)


async def test_undef(circuit):
    """UNDEF menas data not available."""
    n = 0
    def acq():
        nonlocal n
        n += 1
        return n if n not in (1, 3, 6) else edzed.UNDEF

    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=acq,
        interval=0.03,
        on_output=edzed.Event(logger, 'log'))
    timelimit(0.23, error=False)
    # --- time 0.000:
    # Timelogger starts
    # ValuePoll polls for the first time, receives UNDEF, remains uninitialized
    # --- time 0.030:
    # ValuePoll polls for the second time, receives 2, is now initialized (init_async)
    # timelimit timer starts counting its 0.230
    # --- time 0.260:
    # timelimit stops the circuit

    await edzed.run()

    LOG = [
        # (0, 1) missing, initialization not finished
        (30, 2),
        # (60, 3), missing
        (90, 4),
        (120, 5),
        # (150, 6), also missing
        (180, 7),
        (210, 8),
        (240, 9)]
    logger.compare(LOG)


async def test_init_timeout(circuit):
    """Test the initialization time_out."""
    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=lambda: edzed.UNDEF,   # it never delivers
        interval=10,                # don't care
        init_timeout=0.12,
        on_output=edzed.Event(logger, 'log'),
        initdef='DEFAULT')
    await edzed.run(circuit.wait_init())
    logger.compare([(120, 'DEFAULT')])


async def test_init_failure(circuit):
    """Test failed init."""
    logger = TimeLogger('logger', mstop=True)
    edzed.ValuePoll(
        'out',
        func=lambda: edzed.UNDEF,   # func never delivers
        interval=10,                # don't care
        init_timeout=0.04)          # no initdef
    with pytest.raises(Exception, match="not initialized"):
        await edzed.run()
    logger.compare([(40, '--stop--')])


async def test_async_init_timeout(circuit):
    """Test the async initialization time_out."""
    async def w3():
        await asyncio.sleep(0.1)
        return 3
    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=w3,
        interval=10,                # don't care
        init_timeout=0.2,
        on_output=edzed.Event(logger, 'log'),
        initdef='DEFAULT')
    await edzed.run(circuit.wait_init())
    logger.compare([(100, 3)])


async def test_async_init_timeout_failure(circuit):
    """Test the async initialization time_out."""
    async def w3():
        await asyncio.sleep(0.1)
        return 3
    logger = TimeLogger('logger')
    edzed.ValuePoll(
        'out',
        func=w3,
        interval=10,                # don't care
        init_timeout=0.05,
        on_output=edzed.Event(logger, 'log'),
        initdef='DEFAULT')
    await edzed.run(circuit.wait_init())
    logger.compare([(50, 'DEFAULT')])

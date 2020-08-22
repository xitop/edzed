"""
Test the Repeat block
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio

import pytest

import edzed

from .utils import *


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
    out = edzed.ValuePoll(
        'out',
        func=acq,
        interval='0m0.05s',
        on_output=edzed.Event(logger))
    timelimit(0.34, error=False)
    try:
        await circuit.run_forever()
    except asyncio.CancelledError:
        pass

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
    out = edzed.ValuePoll(
        'out',
        func=q.get,
        interval='0m0.05s',
        on_output=edzed.Event(logger))
    timelimit(0.2, error=False)
    try:
        await circuit.run_forever()
    except asyncio.CancelledError:
        pass

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
    out = edzed.ValuePoll(
        'out',
        func=acq,
        interval=0.03,
        on_output=edzed.Event(logger))
    timelimit(0.23, error=False)
    # --- time 0.000:
    # Timelogger starts
    # ValuePoll polls for the first time, receives UNDEF, remains uninitialized
    # --- time 0.030:
    # ValuePoll polls for the second time, receives 2, is now initialized (init_async)
    # timelimit timer starts counting its 0.230
    # --- time 0.260:
    # timelimit stops the circuit

    try:
        await circuit.run_forever()
    except asyncio.CancelledError:
        pass

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
    out = edzed.ValuePoll(
        'out',
        func=lambda: edzed.UNDEF,   # it never delivers
        interval=10,                # don't care
        init_timeout=0.12,
        on_output=edzed.Event(logger),
        initdef='DEFAULT')
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    await circuit.shutdown()

    logger.compare([(120, 'DEFAULT')])


async def test_init_failure(circuit):
    """Test failed init."""
    logger = TimeLogger('logger', mstop=True)
    out = edzed.ValuePoll(
        'out',
        func=lambda: edzed.UNDEF,   # func never delivers
        interval=10,                # don't care
        init_timeout=0.04)          # no initdef
    with pytest.raises(Exception, match="not initialized"):
        await circuit.run_forever()
    logger.compare([(40, '--stop--')])

"""
Test the InputExp block.
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


async def test_expiration(circuit):
    """Test the value expiration."""
    logger = TimeLogger('logger', mstop=True)
    inpexp = edzed.InputExp(
        'ie', duration=0.2, expired=-1, initdef=99,
        on_output=edzed.Event(logger))

    async def tester():
        await asyncio.sleep(0.25)
        assert inpexp.state == 'expired'
        inpexp.put(77)
        assert inpexp.state == 'valid'
        await asyncio.sleep(0.1)
        inpexp.put(55)
        await asyncio.sleep(0.25)
        inpexp.put(33, duration="0.08s")    # override
        await asyncio.sleep(0.2)

    await edzed.run(tester())
    LOG = [
        (0, 99),
        (200, -1),
        (250, 77),
        (350, 55),
        (550, -1),
        (600, 33),
        (680, -1),
        (800, "--stop--"),
    ]
    logger.compare(LOG)


async def ptest(circuit, delay, slog):

    async def test_sleep(sleeptime):
        await edzed.get_circuit().wait_init()
        await asyncio.sleep(sleeptime)

    state = {}
    # circuit 1
    circuit.set_persistent_data(state)
    ie1 = edzed.InputExp(
        'ie', duration=0.25, expired="exp", initdef="ok1", persistent=True)
    await edzed.run(test_sleep(0.1))
    assert ie1.key in state

    # circuit 2
    await asyncio.sleep(delay)
    edzed.reset_circuit()
    circuit = edzed.get_circuit()
    circuit.set_persistent_data(state)
    logger = TimeLogger('logger')
    ie2 = edzed.InputExp(
        'ie', duration=0.25, expired="exp", initdef="ok2", persistent=True,
        on_output=edzed.Event(logger))
    await edzed.run(test_sleep(0.3))
    logger.compare(slog)


async def test_persistent_state(circuit):
    """Test the state persistence."""
    LOG = [
        (0, "ok1"),
        (150, "exp"),   # 250 total - 100 in circuit1 = 150 in circuit2 [ms]
    ]
    await ptest(circuit, 0.0, LOG)


async def test_expired_persistent_state(circuit):
    """Test the persistent state with expired state"""

    LOG = [
        (0, "ok2"),     # ok1 expired
        (250, "exp")
    ]
    await ptest(circuit, 0.2, LOG)

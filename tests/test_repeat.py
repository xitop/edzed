"""
Test the Repeat block.
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


async def test_etype(circuit):
    """Test etype selectivity."""
    mem = EventMemory('mem')
    rpt = edzed.Repeat('repeat', dest=mem, etype='put', interval=0.05)

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    for etype in ('get', 'set', 'stop', 'start', 'PUT', 'putx', 'xput'):
        rpt.event(etype)
    await circuit.shutdown()
    assert mem.output is None


async def test_repeat(circuit):
    """Test the event repeating."""
    logger = TimeLogger('logger', select=lambda data: (data['repeat'], data['value']))
    rpt = edzed.Repeat('repeat', dest=logger, interval=0.05)

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    await asyncio.sleep(0.1)
    rpt.put('A')
    await asyncio.sleep(0.17)
    rpt.put('B')
    await asyncio.sleep(0.12)
    await circuit.shutdown()

    LOG = [
        (100, (False, 'A')),
        (150, (True, 'A')),
        (200, (True, 'A')),
        (250, (True, 'A')),
        (270, (False, 'B')),
        (320, (True, 'B')),
        (370, (True, 'B')),
        ]
    logger.compare(LOG)

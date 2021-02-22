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
    assert rpt.output == 0
    rpt.put('A')
    await asyncio.sleep(0.18)
    assert rpt.output == 3
    rpt.put('B')
    # assert rpt.output == 0    # would fail, the event is in the Repeat block's queue
                                # and it will take some time to process it
    await asyncio.sleep(0.12)
    assert rpt.output == 2
    await circuit.shutdown()

    LOG = [
        (100, (0, 'A')),
        (150, (1, 'A')),
        (200, (2, 'A')),
        (250, (3, 'A')),
        (280, (0, 'B')),
        (330, (1, 'B')),
        (380, (2, 'B')),
        ]
    logger.compare(LOG)


async def test_output(circuit):
    """Test if the output value matches the repeat count."""
    class Check(edzed.SBlock):
        def init_regular(self):
            self.set_output(None)
        def _event_EV(self, repeat, source, orig_source, twelve, **_data):
            assert orig_source == 'fake'
            assert source == 'repeat0'
            assert twelve == 12
            assert repeat == rpt.output
            assert 0 <= repeat <= 3

    rpt = edzed.Repeat('repeat0', etype='EV', dest=Check('check'), interval=0.05)

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert rpt.output == 0
    rpt.event('EV', twelve=12, source='fake')
    await asyncio.sleep(0.16)
    rpt.event('EV', twelve=12, source='fake')
    await asyncio.sleep(0.11)
    await circuit.shutdown()

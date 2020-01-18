"""
Test the TimeDate block as much as possible in short time.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio
import time

import pytest

import edzed
from edzed.utils.timeinterval import HMS, MD

from .utils import *


pytest_plugins = ('pytest_asyncio',)


async def _test5(circuit, *p5):
    yes1, yes2, no1, no2, ying, yang = \
        [edzed.TimeDate(f"tmp_{i}", **kw) for i, kw in enumerate(p5)]

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert yes1.output      # always on
    assert yes2.output      # always on
    assert not no1.output   # always off
    assert not no2.output   # always off
    assert ying.output != yang.output   # either a or b
    await circuit.shutdown()


@pytest.mark.asyncio
async def test_times(circuit):
    now = HMS()
    other_month = MD.NAMES[13 - MD().month]
    await _test5(
        circuit,
        {'times': '0:0-0:0'},
        {'times': f"{now}-{(now.hour+1) % 24}:{now.minute}"},
        {'times': '0:0-0:0', 'dates': f'1.{other_month}-25.{other_month}'},
        {'times': f"{(now.hour+1) % 24}:{now.minute}-{(now.hour+2) % 24}:{now.minute}"},
        {'times': '0:0:0-12:0:0'},
        {'times': '12:0:0-0:0:0'},
        )


@pytest.mark.asyncio
async def test_dates(circuit):
    now = MD()
    def mname0(mnum):
        return MD.NAMES[1 + mnum]
    await _test5(
        circuit,
        {'dates': 'jan 1 - dec 31'},
        {'dates': f"{now}-{mname0((now.month+1) % 12)}.15"},
        {'dates': 'jan 1 - dec 31', 'weekdays': ''},
        {'dates': f"{mname0((now.month+1) % 12)} 1-{mname0((now.month+2) % 12)} 20"},
        {'dates': '21.dec-20.jun'},
        {'dates': '21.jun-20.dec'},
        )

@pytest.mark.asyncio
async def test_weekdays(circuit):
    other_hour = (HMS().hour + 3) % 24
    await _test5(
        circuit,
        {'weekdays': '6712345'},
        {},
        {'weekdays': '6712345', 'times': f'{other_hour}:0 - {other_hour}:59:59'},
        {'weekdays': ''},
        {'weekdays': '1357'},
        {'weekdays': '246'},
        )

@pytest.mark.asyncio
async def test_1sec(circuit):
    """Activate for the next one second."""
    logger = TimeLogger('logger', mstop=True)
    timelimit(3.0, error=True)
    now = time.time()
    now_sec = HMS(time.localtime(now)).seconds()
    ms = now % 1
    delay = 1 if ms < 0.950 else 2   # leave at least 50ms for circuit setup
    s1 = edzed.TimeDate(
        "1sec",
        times=f"{HMS(now_sec+delay)}-{HMS(now_sec+delay+1)}",
        on_output=(
            edzed.Event(logger),
            edzed.Event('_ctrl', 'shutdown', efilter=edzed.Edge(fall=True))
            )
        )

    with pytest.raises(asyncio.CancelledError):
        await circuit.run_forever()
    LOG = [
        (0, False),
        (1000*(delay - ms), True),
        (1000*(delay + 1 - ms), False),
        (1000*(delay + 1 - ms), '--stop--'),
        ]
    logger.compare(LOG)

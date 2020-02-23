"""
Test the TimeSpan block as much as possible in short time.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import
# pylint: disable=bad-whitespace

import asyncio
import time

import pytest

import edzed
from edzed.utils.timeinterval import HMS, MD

from .utils import *


pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_null(circuit):
    null = edzed.TimeSpan('null')
    empty = edzed.TimeSpan('empty', span=' ')
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert not null.output
    assert null.get_state() == []
    assert not empty.output
    assert empty.get_state() == []
    await circuit.shutdown()


@pytest.mark.asyncio
async def test_args(circuit):
    arg = [
        [[2020, 3, 1, 12, 0], [2020, 3, 7, 18, 30, 0]],
        [[2020, 10, 10, 10, 30, 0], [2020, 10, 10, 22, 0, 0]],
    ]
    td_str = edzed.TimeSpan(
        'str_args',
        span="2020 March 1 12:00 - 2020 March 7 18:30, 10:30 Oct. 10 2020 - 22:00 Oct.10 2020")
    td_num = edzed.TimeSpan('num_args', span=arg)
    arg[0][0].append(0)     # extend to 6 items
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert td_str.get_state() == td_num.get_state() == arg
    await circuit.shutdown()


@pytest.mark.asyncio
async def test_yesno(circuit):
    yes1 = edzed.TimeSpan("yes1", span="Jan 1. 2001 0:0 - Dec.31 9999 0:0")
    no1 = edzed.TimeSpan("no1", span="Jan 1. 1970 0:0 - Dec.31 1987 0:0")   # in the past
    no2 = edzed.TimeSpan("no2", span="Feb 1. 2500 0:0 - Feb.1 1990 0:0")    # backwards!

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert yes1.output      # always on
    assert not no1.output   # always off
    assert not no2.output   # always off
    await circuit.shutdown()


async def t1sec(circuit, dynamic):
    """Activate for the next one second."""
    logger = TimeLogger('logger', mstop=True)
    timelimit(3.0, error=True)
    now = time.time()
    now_sec = HMS(time.localtime(now)).seconds()
    ms = now % 1
    delay = 1 if ms < 0.950 else 2   # leave at least 50ms for circuit setup
    t1 = time.localtime(now + delay)
    t2 = time.localtime(now + delay + 1)
    sarg = f"{t1.tm_year} {MD(t1)} {HMS(t1)} - {HMS(t2)} {MD(t2)} {t2.tm_year}"
    s1 = edzed.TimeSpan(
        "1sec",
        span=() if dynamic else sarg,
        on_output=(
            edzed.Event(logger),
            edzed.Event('_ctrl', 'shutdown', efilter=edzed.Edge(fall=True))
            )
        )
    simtask = asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    if dynamic:
        s1.event('reconfig', span=sarg)
    with pytest.raises(asyncio.CancelledError):
        await simtask

    LOG = [
        (0, False),
        (1000*(delay - ms), True),
        (1000*(delay + 1 - ms), False),
        (1000*(delay + 1 - ms), '--stop--'),
        ]
    logger.compare(LOG)

@pytest.mark.asyncio
async def test_1sec_static(circuit):
    await t1sec(circuit, False)

@pytest.mark.asyncio
async def test_1sec_dynamic(circuit):
    await t1sec(circuit, True)


def test_no_initdef(circuit):
    with pytest.raises(TypeError):
        edzed.TimeSpan(None, initdef=[])


@pytest.mark.asyncio
async def test_state(circuit):
    """Test the cron service, internal state."""
    sarg = [[[2001,6,30,1,2,3], [2048,5,31,1,59,59]]]
    td = edzed.TimeSpan("local", span=sarg)
    tdu = edzed.TimeSpan("utc", utc=True, span="2001 June 30. 1:2:3 - 31.may 2048 1:59:59")

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()

    assert td.get_state() == td.initdef == sarg
    assert tdu.get_state() == tdu.initdef == sarg

    td.event('reconfig')
    assert td.get_state() == []
    assert td.initdef == sarg

    conf = [[[2020,1,2,3,4,5], [2030,8,9,10,11,12]], [[2015,5,4,3,2,1], [2035,9,8,7,6,5]]]
    tdu.event('reconfig', span=conf)
    assert tdu.get_state() == conf
    assert tdu.initdef == sarg

    await circuit.shutdown()


def test_parse():
    parse = edzed.TimeSpan.parse
    assert parse('') == []
    assert parse("2001 August 31. 1:2:3 - 31.may 2008 1:59") == \
        [[[2001,8,31,1,2,3], [2008,5,31,1,59,0]]]


@pytest.mark.asyncio
async def test_persistent(circuit):
    td = edzed.TimeSpan("pers", persistent=True)
    storage = {}
    circuit.set_persistent_data(storage)
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert td.get_state() == []
    conf = edzed.TimeSpan.parse(
        "2001August31.23:2:3-31.may2008 0:0,2011August31.1:2:3-31.may2018 1:59")
    td.event('reconfig', span=conf)
    assert td.get_state() == conf
    await circuit.shutdown()
    assert storage == {td.key: conf}

    edzed.reset_circuit()
    td = edzed.TimeSpan("pers", persistent=True)
    circuit = edzed.get_circuit()
    circuit.set_persistent_data(storage)
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert td.get_state() == conf
    await circuit.shutdown()
    assert storage == {td.key: conf}

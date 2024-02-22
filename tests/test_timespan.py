"""
Test the TimeSpan block as much as possible in short time.
"""

import asyncio
import datetime as dt
import sys
import time

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import timelimit, TimeLogger

pytest_plugins = ('pytest_asyncio',)

P3_11 = sys.version_info >= (3, 11)


@pytest.mark.asyncio
async def test_null(circuit):
    null = edzed.TimeSpan('null')
    empty = edzed.TimeSpan('empty', span=' ')

    async def tester():
        await circuit.wait_init()
        assert not null.output
        assert null.get_state() == []
        assert not empty.output
        assert empty.get_state() == []

    await edzed.run(tester())


@pytest.mark.asyncio
async def test_args(circuit):
    arg = [
        [[2020, 3, 1, 12, 0], [2020, 3, 7, 18, 30, 1, 150_000]],
        [[2020, 10, 10, 10, 30, 0], [2020, 10, 10, 22, 0, 0]],
    ]
    td_num = edzed.TimeSpan('num_args', span=arg)
    td_str = edzed.TimeSpan(
        'str_args',
        span="2020 March 1 12:00 - 2020 March 7 18:30:1.15,"
             + "10:30 Oct. 10 2020 / 22:00 Oct.10 2020")
    if P3_11:
        td_iso = edzed.TimeSpan(
            'iso_args',
            span="20200301T1200 / 20200307T183001.15; 2020-10-10T10:30 / 2020-10-10T22;")
    else:
        td_iso = td_str

    for interval in arg:
        for endpoint in interval:
            endpoint.extend([0] * (7-len(endpoint)))    # right-pad to 7 ints

    async def tester():
        await circuit.wait_init()
        assert td_str.get_state() == td_num.get_state() == td_iso.get_state() == arg

    await edzed.run(tester())


@pytest.mark.asyncio
async def test_yesno(circuit):
    yes1 = edzed.TimeSpan("yes1", span="Jan 1. 2001 0:0 / Dec.31 9999 0:0;")
    no1 = edzed.TimeSpan("no1", span="Jan 1. 1970 0:0 - Dec.31 1987 0:0")       # in the past
    no2 = edzed.TimeSpan("no2", span="Feb 1. 2500 0:0 - 1990-Feb-01 0:0")       # backwards!

    async def tester():
        await circuit.wait_init()
        assert yes1.output      # always on
        assert not no1.output   # always off
        assert not no2.output   # always off

    await edzed.run(tester())


async def tfsec(circuit, dynamic):
    """Activate for a fraction of a second."""
    logger = TimeLogger('logger', mstop=True)
    timelimit(3.0, error=True)
    now = time.time()
    sarg = f"{dt.datetime.fromtimestamp(now + 0.3)} - {dt.datetime.fromtimestamp(now + 0.65)}"
    s1 = edzed.TimeSpan(
        "fsec",
        span=() if dynamic else sarg,
        on_output=(
            edzed.Event(logger, 'log'),
            edzed.Event('_ctrl', 'shutdown', efilter=edzed.Edge(fall=True))
            )
        )

    async def tester():
        if dynamic:
            await circuit.wait_init()
            s1.event('reconfig', span=sarg)
        await asyncio.sleep(9)

    await edzed.run(tester())

    LOG = [
        (0, False),
        (300, True),
        (650, False),
        (650, '--stop--'),
        ]
    logger.compare(LOG)

@pytest.mark.asyncio
async def test_fsec_static(circuit):
    await tfsec(circuit, False)

@pytest.mark.asyncio
async def test_fsec_dynamic(circuit):
    await tfsec(circuit, True)


def test_no_initdef(circuit):
    with pytest.raises(TypeError):
        edzed.TimeSpan(None, initdef=[])


@pytest.mark.asyncio
async def test_state(circuit):
    """Test the cron service, internal state."""
    sarg = [[[2001,6,30,1,2,3,499_000], [2048,5,31,1,59,59]]]
    td = edzed.TimeSpan("local", span=sarg)
    tdu = edzed.TimeSpan(
        "utc", utc=True, span="2001 June 30. 1:2:3.499 - 31.may 2048 1:59:59")
    if P3_11:
        tdu_iso = edzed.TimeSpan(
            "utc_iso", utc=True, span="20010630T010203.4990/20480531T01:59:59")

    async def tester():
        await circuit.wait_init()

        for endpoint in sarg[0]:
            endpoint.extend([0] * (7 - len(endpoint)))
        assert td.get_state() == td.initdef == sarg
        assert tdu.get_state() == tdu.initdef == sarg
        if P3_11:
            assert tdu_iso.get_state() == tdu.initdef == sarg

        td.event('reconfig')
        assert td.get_state() == []
        assert td.initdef == sarg

        conf = [
            [[2015,5,4,3,2,1,0], [2035,9,8,7,6,5,0]],
            [[2020,1,2,3,40,50,600], [2030,8,9,10,11,12,0]],
            ]   # sorted
        tdu.event('reconfig', span=conf)
        assert tdu.get_state() == conf
        assert tdu.initdef == sarg

    await edzed.run(tester())


def test_parse():
    parse = edzed.TimeSpan.parse
    assert parse('') == []
    assert (
        parse("2001 August 31. 1:2:3.400-31.may 2008 1:59")
        == parse("2001-08-31 1:2:3.400 - 2008-05-31 01:59:0")
        == parse("2001-08-31 1:2:3,400 - 2008-05-31 01:59:0,0;")
        == parse("1:2:3.400 2001 August 31./31.may 2008 1:59")
        == [[[2001,8,31,1,2,3,400_000], [2008,5,31,1,59,0,0]]])


@pytest.mark.asyncio
async def test_persistent(circuit):
    td = edzed.TimeSpan("pers", persistent=True)
    storage = {}
    circuit.set_persistent_data(storage)
    conf = None

    async def tester1():
        nonlocal conf
        await circuit.wait_init()
        assert td.get_state() == []
        conf = edzed.TimeSpan.parse(
            "2001August31.23:2:3-31.may2008 0:0,2011August31.1:2:3-31.may2018 1:59")
        td.event('reconfig', span=conf)
        assert td.get_state() == conf

    await edzed.run(tester1())
    assert storage[td.key] == conf

    edzed.reset_circuit()
    td = edzed.TimeSpan("pers", persistent=True)
    circuit = edzed.get_circuit()
    circuit.set_persistent_data(storage)

    async def tester2():
        await circuit.wait_init()
        assert td.get_state() == conf

    await edzed.run(tester2())
    assert storage[td.key] == conf

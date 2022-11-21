"""
Test the TimeDate block as much as possible in short time.
"""

# pylint: disable=missing-docstring, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio
import time

import pytest

import edzed
from edzed.utils import MONTH_NAMES
from edzed.blocklib.timeinterval import HMS, MD

from .utils import *


pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_null(circuit):
    """Test a disabled block and an empty schedule."""
    null = edzed.TimeDate('null')
    empty = edzed.TimeDate('empty', dates=' ', times='', weekdays=[])

    async def tester():
        await circuit.wait_init()
        assert not null.output
        assert null.get_state() == {'dates': None, 'times': None, 'weekdays': None}
        assert not empty.output
        assert empty.get_state() == {'dates': [], 'times': [], 'weekdays': []}

    await edzed.run(tester())


@pytest.mark.asyncio
async def test_args(circuit):
    """Test the equivalence of string and numeric formats."""
    kwargs = {
        'dates': [[[6,21], [12,20]]],
        'times': [[[1,30,0], [2,45,0]], [[17,1,10], [17,59,10]]],
        'weekdays': [1,5],
    }
    td_str = edzed.TimeDate(
        'str_args', dates='21.jun-20.dec', times='1:30-2:45, 17:01:10-17:59:10', weekdays='15')
    td_num = edzed.TimeDate(
        'num_args', **kwargs)

    async def tester():
        await circuit.wait_init()
        assert td_str.get_state() == td_num.get_state() == kwargs

    await edzed.run(tester())


async def _test6(circuit, *p6):
    yes1, yes2, no1, no2, ying, yang = \
        [edzed.TimeDate(f"tmp_{i}", **kw) for i, kw in enumerate(p6)]

    async def tester():
        await circuit.wait_init()
        assert yes1.output      # always on
        assert yes2.output      # always on
        assert not no1.output   # always off
        assert not no2.output   # always off
        assert ying.output != yang.output   # either a or b

    await edzed.run(tester())


@pytest.mark.asyncio
async def test_times(circuit):
    now = HMS()
    other_month = MONTH_NAMES[13 - MD().month]
    await _test6(
        circuit,
        {'times': '0:0-0:0'},
        {'times': f"{now}-{(now.hour+1) % 24}:{now.minute}"},
        {'times': '0:0-0:0', 'dates': f'1.{other_month}-25.{other_month}'},
        {'times': f"{(now.hour+1) % 24}:{now.minute}-{(now.hour+2) % 24}:{now.minute}"},
        {'times': '0:0:0-12:0:0'},
        {'times': '12:0-0:0'},
        )


@pytest.mark.asyncio
async def test_dates(circuit):
    now = MD()
    def mname0(mnum):
        return MONTH_NAMES[1 + mnum]
    await _test6(
        circuit,
        {'dates': ' jan 1 - dec 31 '},
        {'dates': f"{now}-{mname0((now.month+1) % 12)}.15"},
        {'dates': 'jan 1 - dec 31', 'weekdays': ''},
        {'dates': f"{mname0((now.month+1) % 12)} 1-{mname0((now.month+2) % 12)} 20"},
        {'dates': '21.dec.-20.jun.'},
        {'dates': '21.jun-20.dec'},
        )

@pytest.mark.asyncio
async def test_weekdays(circuit):
    other_hour = (HMS().hour + 3) % 24
    await _test6(
        circuit,
        {'weekdays': '6712345'},
        {'weekdays': list(range(7))},
        {'weekdays': '6712345', 'times': f'{other_hour}:0 - {other_hour}:59:59'},
        {'weekdays': ''},
        {'weekdays': '1357'},
        {'weekdays': '246'},
        )


async def t1sec(circuit, dynamic):
    """Activate for the next one second."""
    logger = TimeLogger('logger', mstop=True)
    timelimit(3.0, error=True)
    now = time.time()
    now_sec = HMS(time.localtime(now)).seconds()
    ms = now % 1
    delay = 1 if ms < 0.950 else 2   # leave at least 50ms for circuit setup
    targ = f"{HMS(now_sec+delay)}-{HMS(now_sec+delay+1)}"
    s1 = edzed.TimeDate(
        "1sec",
        times=None if dynamic else targ,
        on_output=(
            edzed.Event(logger),
            edzed.Event('_ctrl', 'shutdown', efilter=edzed.Edge(fall=True))
            )
        )

    async def tester():
        if dynamic:
            await circuit.wait_init()
            s1.event('reconfig', times=targ)
        await asyncio.sleep(9)  # cancellation expected

    await edzed.run(tester())

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
        edzed.TimeDate(None, initdef={})


@pytest.mark.asyncio
async def test_cron(circuit):
    """Test the cron service, internal state."""
    targ = [[[1,2,3], [2,3,4]]]
    td = edzed.TimeDate("local", times=targ, dates="apr.1")
    std = str(td)
    td2 = edzed.TimeDate("local2", weekdays="67")
    std2 = str(td2)
    cron = circuit.findblock('_cron_local')

    tdu = edzed.TimeDate("utc", utc=True, times="10:11:12-13:14:15, 14:15-16:17")
    stdu = str(tdu)
    cronu = circuit.findblock('_cron_utc')

    async def tester():
        await circuit.wait_init()
        tinit = {'times': targ, 'dates': [[[4,1], [4,1]]], 'weekdays': None}
        assert td.get_state() == td.initdef == tinit

        assert cron.event('get_schedule') == {
            '00:00:00': ['local', 'local2'], '01:02:03': ['local'], '02:03:04': ['local']}
        assert cronu.event('get_schedule') == {
            '00:00:00': ['utc'], '10:11:12': ['utc'], '13:14:15': ['utc'],
            '14:15:00': ['utc'], '16:17:00': ['utc']}

        td.event('reconfig')
        assert cron.event('get_schedule') == {'00:00:00': ['local', 'local2']}
        assert td.get_state() == {'times': None, 'dates': None, 'weekdays': None}
        assert td.initdef == tinit

        conf = {'times': [[[20,20,0], [8,30,0]]], 'dates': None, 'weekdays': [4]}
        tdu.event('reconfig', **conf)
        assert cronu.event('get_schedule') == {
            '00:00:00': ['utc'], '08:30:00': ['utc'], '20:20:00': ['utc']}
        assert tdu.get_state() == conf

    await edzed.run(tester())


def test_parse():
    parse = edzed.TimeDate.parse
    assert parse(None, None, None) == {'times': None, 'dates': None, 'weekdays': None}
    assert parse("17:0:30-18:14", "Nov30", "134") == {
        'times': [[[17,0,30], [18,14,0]]],
        'dates': [[[11,30], [11,30]]],
        'weekdays': [1,3,4]
        }


@pytest.mark.asyncio
async def test_persistent(circuit):
    td = edzed.TimeDate("pers", persistent=True)
    storage = {}
    circuit.set_persistent_data(storage)
    conf = None

    async def tester1():
        nonlocal conf
        await circuit.wait_init()
        assert td.get_state() == {'times': None, 'dates': None, 'weekdays': None}
        conf = edzed.TimeDate.parse("1:0-2:0", None, "7")
        td.event('reconfig', **conf)
        assert td.get_state() == conf

    await edzed.run(tester1())
    assert storage[td.key] == conf

    edzed.reset_circuit()
    td = edzed.TimeDate("pers", persistent=True)
    circuit = edzed.get_circuit()
    circuit.set_persistent_data(storage)

    async def tester2():
        await circuit.wait_init()
        assert td.get_state() == conf

    await edzed.run(tester2())
    assert storage[td.key] == conf

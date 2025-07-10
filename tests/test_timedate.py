"""
Test the TimeDate block as much as possible in short time.
"""

import asyncio
import sys
import datetime as dt
import time

import pytest

import edzed
from edzed.utils import MONTH_NAMES

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit, fixture_task_factories
from .utils import timelimit, TimeLogger

pytest_plugins = ('pytest_asyncio',)

P3_11 = sys.version_info >= (3, 11)


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
        'times': [[[1,30], [2,45,0]], [[17,1,10,50_000], [17,59,10,0]]],
        'weekdays': [1,7],
    }
    td_str = edzed.TimeDate(
        'str_args',
        dates='21.jun-20.dec', times='1:30-2:45, 17:01:10.05/17:59:10', weekdays='17')
    td_num = edzed.TimeDate(
        'num_args', **kwargs)
    if P3_11:
        td_iso = edzed.TimeDate(
            'iso_args',
            dates='--0621 - --1220',
            times='T0130-T0245, T17:01:10.05/17:59:10.00',
            weekdays='01')  # both 0 and 7 mean a Sunday
    else:
        td_iso = td_str

    for interval in kwargs['times']:
        for endpoint in interval:
            endpoint.extend([0] * (4-len(endpoint)))    # right-pad to 4 ints

    async def tester():
        await circuit.wait_init()
        assert td_str.get_state() == td_num.get_state() == td_iso.get_state() == kwargs

    await edzed.run(tester())


async def _test6(circuit, *p6):
    yes1, yes2, no1, no2, ying, yang = [
        edzed.TimeDate(f"tmp_{i}", **kw)for i, kw in enumerate(p6)]

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
    now = dt.datetime.today()
    other_month = MONTH_NAMES[13 - now.month]
    await _test6(
        circuit,
        {'times': '0:0 / 0:0'},
        {'times': f"{now.time()}-{(now.hour+1) % 24}:{now.minute}"},
        {'times': '0:0-0:0', 'dates': f'1.{other_month}-25.{other_month}'},
        {'times': f"{(now.hour+1) % 24}:{now.minute}-{(now.hour+2) % 24}:{now.minute}"},
        {'times': '0:0:0 - 12:0:0'},
        {'times': '12:0-0:0'},
        )


@pytest.mark.asyncio
async def test_dates(circuit):
    now = dt.date.today()
    nowm = now.month
    await _test6(
        circuit,
        {'dates': ' jan 1 - dec 31 '},
        {'dates': f"{now.day}.{MONTH_NAMES[nowm]}-{MONTH_NAMES[nowm % 12 + 1]}.15"},
        {'dates': 'jan 1-dec 31', 'weekdays': ''},
        {'dates': f"{MONTH_NAMES[nowm % 12 + 1]} 1-{MONTH_NAMES[(nowm+1) % 12 + 1]} 20"},
        {'dates': '21.dec.-20.jun.'},
        {'dates': '21.jun / 20.dec'},
        )

@pytest.mark.asyncio
async def test_weekdays(circuit):
    other_hour = (dt.datetime.now().hour + 3) % 24
    await _test6(
        circuit,
        {'weekdays': '6712345'},
        {'weekdays': list(range(7))},
        {'weekdays': '6712345', 'times': f'{other_hour}:0 - {other_hour}:59:59'},
        {'weekdays': ''},
        {'weekdays': '1357'},
        {'weekdays': '246'},
        )


async def tfsec(circuit, dynamic):
    """Activate for a fraction of a second."""
    def time_from_timestamp(ts: float) -> dt.time:
        return dt.datetime.fromtimestamp(ts).time()

    logger = TimeLogger('logger', mstop=True)
    timelimit(3.0, error=True)
    now = time.time()
    targ = f"{time_from_timestamp(now+0.35)}/{time_from_timestamp(now+0.75)}"

    s1 = edzed.TimeDate(
        "short",
        times=None if dynamic else targ,
        on_output=(
            edzed.Event(logger, 'log'),
            edzed.Event('_ctrl', 'shutdown', efilter=edzed.Edge(fall=True))
            )
        )

    async def tester():
        if dynamic:
            await circuit.wait_init()
            s1.event('reconfig', times=targ)
        await asyncio.sleep(5)  # cancellation expected

    await edzed.run(tester())

    LOG = [
        (0, False),
        (350, True),
        (750, False),
        (750, '--stop--'),
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
        edzed.TimeDate(None, initdef={})


@pytest.mark.asyncio
async def test_cron(circuit):
    """Test the cron service, internal state."""
    targ = [[[1,2,3,5000], [2,3,4,0]]]
    td = edzed.TimeDate("local", times=targ, dates="apr.1")
    edzed.TimeDate("local2", weekdays="67")
    cron = circuit.findblock('_cron_local')

    tdu = edzed.TimeDate(
        "utc",
        utc=True,
        times="10:11:12-131415.0, T141500-T1617" if P3_11
            else "10:11:12-13:14:15, 14:15-16:17",
        )
    cronu = circuit.findblock('_cron_utc')

    async def tester():
        await circuit.wait_init()
        tinit = {'times': targ, 'dates': [[[4,1], [4,1]]], 'weekdays': None}
        assert td.get_state() == td.initdef == tinit

        assert cron.event('get_schedule') == {
            '00:00:00': ['local', 'local2'],
            '01:02:03.005000': ['local'],
            '02:03:04': ['local']}
        assert cronu.event('get_schedule') == {
            '00:00:00': ['utc'], '10:11:12': ['utc'], '13:14:15': ['utc'],
            '14:15:00': ['utc'], '16:17:00': ['utc']}

        td.event('reconfig')
        assert cron.event('get_schedule') == {'00:00:00': ['local', 'local2']}
        assert td.get_state() == {'times': None, 'dates': None, 'weekdays': None}
        assert td.initdef == tinit

        conf = {'times': [[[20,20,0,0], [8,30,0,0]]], 'dates': None, 'weekdays': [4]}
        tdu.event('reconfig', **conf)
        assert cronu.event('get_schedule') == {
            '00:00:00': ['utc'], '08:30:00': ['utc'], '20:20:00': ['utc']}
        assert tdu.get_state() == conf

    await edzed.run(tester())


def test_parse():
    parse = edzed.TimeDate.parse
    assert parse(None, None, None) == {'times': None, 'dates': None, 'weekdays': None}
    assert parse("17:0:30-18:14", "Nov30", "134") == {
        'times': [[[17,0,30,0], [18,14,0,0]]],
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

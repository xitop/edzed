"""
Test modules from edzed.utils
"""
# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import time

import pytest

from edzed import utils
from edzed.utils import timeinterval

from .utils import *


def test_compare_logs(circuit):
    """Check if we can rely on compare_logs()."""
    log = [(x, f'value_{x}') for x in range(0, 1000, 17)]
    compare_logs(log, log)
    with pytest.raises(AssertionError):
        compare_logs(log, log[:-1])                         # diff length
    with pytest.raises(AssertionError):
        compare_logs(log, log[:-1])                         # diff length
    with pytest.raises(AssertionError):
        compare_logs(
            [(0, 'start'), (22, 'string')],
            [(0, 'start'), (22, 'String')]) # s vs S in string
    # delta_abs tests
    compare_logs(
        [(0, 'start'), (15, 'x')],          # tlog (test)
        [(0, 'start'), (10, 'x')],          # slog (standard)
        delta_abs=5, delta_rel=0)
    with pytest.raises(AssertionError, match="15 is way above expected 10"):
        compare_logs(
            [(0, 'start'), (15, 'x')],
            [(0, 'start'), (10, 'x')],
            delta_abs=4, delta_rel=0)       # NOT 5 < 4 ms
    with pytest.raises(AssertionError, match="8.5 is way below expected 10"):
        compare_logs(
            [(0, 'start'), (8.5, 'x')],     # negative difference -> 1/5 of delta
            [(0, 'start'), (10, 'x')],
            delta_abs=4, delta_rel=0)       # NOT 1.5 < 0.8 (1/5 of 4) ms
    # delta_rel tests
    compare_logs(
        [(490, 'y')],
        [(460, 'y')],
        delta_abs=0, delta_rel=0.10)        # 6.5% < 10%
    with pytest.raises(AssertionError):
        compare_logs(
            [(490, 'y')],
            [(460, 'y')],
            delta_abs=0, delta_rel=0.05)    # 6.5% < 5%
    with pytest.raises(AssertionError):
        compare_logs(
            [(460, 'y')],                  # negative difference -> 1/5 of delta
            [(490, 'y')],
            delta_abs=0, delta_rel=0.1)    # NOT 6.1% < 2% (1/5 of 10%)

def test_timelogger_tool(circuit):
    """Check if we can rely on the TimeLogger."""
    logger = TimeLogger('logger')
    init(circuit)
    logger.put('A')
    time.sleep(0.1)
    logger.put('B')
    time.sleep(0.05)
    logger.put('C')
    logger.compare([(0, 'A'), (100, 'B'), (150, 'C')])


def test_timelogger_marks(circuit):
    """TimeLogger add start and stop marks if enabled."""
    logger = TimeLogger('logger', mstart=True, mstop=True)
    logger.compare([])
    init(circuit)
    logger.compare([(0, '--start--')])
    time.sleep(0.05)
    logger.stop()
    logger.compare([(0, '--start--'), (50, '--stop--')])


def test_tconst():
    assert utils.SEC_PER_MIN == 60
    assert utils.SEC_PER_HOUR == 60*60
    assert utils.SEC_PER_DAY == 24*60*60


def test_timeunits():
    convert = utils.convert
    assert isinstance(convert('1m'), float)
    assert convert('') == 0.0
    assert convert('10.5') == convert('10.5s') == convert('0m10.5') == 10.5
    for arg in ('20h15m10', ' 20 h 15 m 10 ', '19H75M10.000', '20h910'):
        assert convert(arg) == 72910.0
    assert convert('1d') == convert('24h') == utils.SEC_PER_DAY
    for arg in ('1 0 0s', 'hello', '15m1h', '1.5d', '.', '0..1s', '5e-2'):
        with pytest.raises(ValueError):
            convert(arg)


def test_timestr():
    convert = utils.convert
    timestr = utils.timestr
    assert timestr(72910) == '20h15m10s'        # from int
    assert timestr(72910.0) == '20h15m10.000s'  # from float
    assert timestr(5) == '0m5s'                 # minutes always present
    assert timestr(5.0) == '0m5.000s'
    for d in (1, 5, 10):
        for h in (0, 3, 12):
            for m in (10, 20, 59):
                for s in ('30.000', '45.999'):
                    tstr = f"{d}d{h}h{m}m{s}s"
                    assert timestr(convert(tstr)) == tstr
    for t in (0, 100, 10_000, 1_000_000, 100_000_000):
        assert convert(timestr(t)) == t


def test_time_period():
    time_period = utils.time_period
    assert time_period(None) is None
    for v in (-128, -2.8, 0, 5, 33.33):
        c = time_period(v)
        assert isinstance(c, float)
        assert c == (v if v > 0 else 0.0)
    assert time_period("1h1") == 3601.0
    with pytest.raises(ValueError, match='Invalid'):
        time_period('short')
    with pytest.raises(TypeError):
        time_period([1,2,3])


def test_hms():
    HMS = timeinterval.HMS
    assert HMS("15:40") == HMS("15:40:0") == HMS("15:40:00") == HMS((15, 40)) \
        == HMS((15, 40, 0)) == HMS(15*3600 + 40*60)
    assert str(HMS("9:59")) == "09:59:00"       # always HH:MM:SS
    assert str(HMS((7, 20, 5))) == "07:20:05"
    assert HMS([13, 17, 19]).seconds() == 13*3600 + 17*60 + 19
    assert HMS(-1) == HMS("23:59:59")
    for s in (-9_000_000, -52_999, -970, -5, 0, 50, 2345, 71_300, 444_222):
        assert (HMS(s).seconds() - s) % utils.SEC_PER_DAY == 0
    assert HMS([0, 0, 1]) == HMS(1)
    assert HMS([0, 1, 0]) == HMS(utils.SEC_PER_MIN)
    assert HMS([1, 0, 0]) == HMS(utils.SEC_PER_HOUR)
    assert HMS([0, 0, 0]) == HMS(utils.SEC_PER_DAY) == HMS(0)

    t1 = HMS("23:30")
    t2 = HMS("2:0:10")
    assert isinstance(t1.seconds(), int)
    assert isinstance(t1.seconds_from(t2), int)
    assert t1.hour == 23 and t1.minute == 30 and t1.second == 0 # attribute access
    diff2to1 = HMS("21:29:50").seconds()
    diff1to2 = HMS("2:30:10").seconds()
    assert t1.seconds_from(t2) == diff2to1
    assert t2.seconds_from(t1) == diff1to2
    assert diff1to2 + diff2to1 == utils.SEC_PER_DAY

    # HMS is a tuple subclass
    assert HMS("11:59") == (11, 59, 0)
    assert (4, 15, 0) < HMS("4:30") < HMS("4:45:51") < (5, 0, 0) < HMS("7:0:0")
    assert not (4, 15, 0) < HMS("4:10") < (5, 0, 0)

    for tmstruct in (time.localtime(), time.gmtime()):
        assert HMS(tmstruct) == HMS((tmstruct.tm_hour, tmstruct.tm_min, tmstruct.tm_sec))

    now = HMS()
    assert now.seconds_from(now) == 0
    assert now is HMS(now) is HMS(HMS(now))
    assert now == HMS(str(now))

    for arg in ((25, 0), "12:61:0", [1, 2, 3, 4]):
        with pytest.raises(ValueError):
            HMS(arg)
    for arg in (3.14, ...):     # the ellipsis (...) is also an object
        with pytest.raises(TypeError):
            HMS(arg)


def test_md():
    MD = timeinterval.MD
    md69 = MD([6, 9])
    assert md69 == (6, 9)
    assert md69.day == 9 and md69.month == 6
    assert str(md69) == 'Jun.09'
    for dstr in ('09.JunE', ' 9.jun.', '9JUNe', '09 Jun', 'Jun9', ' JUN  09 ', 'jun 9.'):
        assert MD(dstr) == md69

    assert MD('Apr 10') < MD('1.may') < (5, 5) < md69 < MD('Oct 31.') < MD((11, 1))
    today = MD()
    assert today == MD(today) == MD(MD(today))
    assert today == MD(str(today))

    for arg in ([7], "okt. 10", "30.Feb", "what", (0, 2), (2, 30), (13, 13), (1, 1, 1)):
            # 'okt' is not 'oct'
        with pytest.raises(ValueError):
            MD(arg)
    for arg in (1, 3.14, ...):
        with pytest.raises(TypeError):
            MD(arg)


def test_dateinterval():
    DI = timeinterval.DateInterval
    di1 = DI('Jan10 - April10')
    def test1(m, d):
        return (1, 10) <= (m, d) <= (4, 10)
    di2 = DI('15.dec - 15.jan')
    def test2(m, d):
        return (12, 15) <= (m, d) or (m, d) <= (1, 15)
    di12 = DI('15DECEM. - 15JAN, Jan.10-Apr.10')
    di3 = DI('3.aug')
    assert timeinterval.MD("3.aug") in di3
    di4 = DI(' 1 jan - 31 dec ')

    for d in (5, 10, 15, 25):
        for m in range(1, 13):
            md = timeinterval.MD((m, d))
            assert (md in di1) == test1(m, d)
            assert (md in di2) == test2(m, d)
            assert (md in di12) == test1(m, d) or test2(m, d)
            assert md not in di3    # Aug, 3rd not in test data
            assert md in di4


def test_timeinterval():
    TI = timeinterval.TimeInterval
    ti1 = TI('10:30 - 21:10')
    def test1(h, m, s):
        return (10, 30, 0) <= (h, m, s) < (21, 10, 0)
    ti2 = TI('23:40:30 - 01:20:30')
    def test2(h, m, s):
        return (23, 40, 30) <= (h, m, s) or (h, m, s) < (1, 20, 30)
    ti12 = TI('23:40:30-01:20:30, 10:30-21:10')
    assert repr(ti12).endswith(".TimeInterval('23:40:30-01:20:30, 10:30:00-21:10:00')")
    ti3 = TI('6:44:27-6:44:28')
    assert timeinterval.HMS("6:44:27") in ti3
    assert timeinterval.HMS("6:44:28") not in ti3
    ti4 = TI('0:0-0:0')

    for h in range(24):
        for m in range(0, 60, 3):
            for s in (0, 20, 30):
                md = timeinterval.HMS((h, m, s))
                assert (md in ti1) == test1(h, m, s)
                assert (md in ti2) == test2(h, m, s)
                assert (md in ti12) == test1(h, m, s) or test2(h, m, s)
                assert md not in ti3    # 6:44:27 not in test data
                assert md in ti4


def test_dateinterval_ranges():
    MD = timeinterval.MD
    di = timeinterval.DateInterval('15DEC - 15JAN, Jan.10-Apr.10, 6.dec.')
    assert sorted(di.range_endpoints()) == [
        MD((1, 10)), MD((1, 15)), MD((4, 10)),
        MD((12, 6)), MD((12, 6)), MD((12, 15))]


def test_timeinterval_ranges():
    HMS = timeinterval.HMS
    ti = timeinterval.TimeInterval('23:40:30-01:20:30, 10:30-21:10, 15:59:50-16:0')
    assert sorted(ti.range_endpoints()) == [
        HMS((1, 20, 30)), HMS((10, 30, 0)),
        HMS((15, 59, 50)), HMS((16, 0, 0)),
        HMS((21, 10, 0)), HMS((23, 40, 30))]

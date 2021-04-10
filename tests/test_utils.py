"""
Test internal utilities and also modules from edzed.utils
"""
# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import time

import pytest

from edzed import utils
from edzed.blocklib.sblocks2 import _args_as_string

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


def test_args_as_string():
    """Test the _args_as_string helper."""
    def test(*args, **kwargs):
        return _args_as_string(args, kwargs)

    assert test() == "()"
    assert test(-1, 'arg') == "(-1, 'arg')"
    assert test(f=False, t=True, n=[1, 2]) == "(f=False, t=True, n=[1, 2])"
    assert test(1, 2, None, a=1, b='xy') == "(1, 2, None, a=1, b='xy')"

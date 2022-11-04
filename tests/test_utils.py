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
    assert timestr(60+59.9999) == '2m0.000s'    # test rounding
    assert timestr(5) == '0m5s'                 # minutes always present
    assert timestr(5.0) == '0m5.000s'
    assert timestr(5.0001) == '0m5.000s'
    assert timestr(5.0009) == '0m5.001s'
    for d in (1, 5, 10):
        for h in (0, 3, 12):
            for m in (10, 20, 59):
                for s in ('30.000', '45.999'):
                    tstr = f"{d}d{h}h{m}m{s}s"
                    assert timestr(convert(tstr)) == tstr
    for t in (0, 100, 10_000, 1_000_000, 100_000_000):
        assert convert(timestr(t)) == t


def test_timestr_prec():
    timestr = utils.timestr
    t = 7.12345678
    assert timestr(t, prec=7) == '0m7.1234568s'
    assert timestr(t, prec=6) == '0m7.123457s'
    assert timestr(t, prec=5) == '0m7.12346s'
    assert timestr(t, prec=4) == '0m7.1235s'
    assert timestr(t, prec=3) == '0m7.123s'
    assert timestr(t) == '0m7.123s'
    assert timestr(t, prec=2) == '0m7.12s'
    assert timestr(t, prec=1) == '0m7.1s'
    assert timestr(t, prec=0) == '0m7s'
    t = 64.0
    assert timestr(t, prec=4, sep='+') == '1m+4.0000s'
    assert timestr(t, prec=3, sep='_') == '1m_4.000s'
    assert timestr(t) == '1m4.000s'
    assert timestr(t, prec=2) == '1m4.00s'
    assert timestr(t, prec=1) == '1m4.0s'
    assert timestr(t, prec=0) == '1m4s'


def test_timestr_sep():
    convert = utils.convert
    timestr = utils.timestr
    for d in (2, 6, 15):
        for h in (3, 7, 16):
            for m in (0, 11, 45):
                for s in ('30.000', '45.999'):
                    for sep in ('', '_', 'ä', '@@', 'a b c '):
                        tstr = f"{d}d{h}h{m}m{s}s"
                        sepstr = f"{d}d{sep}{h}h{sep}{m}m{sep}{s}s"
                        assert timestr(convert(tstr), sep=sep) == sepstr

def test_timestr_approx():
    convert = utils.convert
    timestr = utils.timestr_approx
    # type int
    assert timestr(0) == '0s'
    assert timestr(1) == '1s'
    assert timestr(3598) == '59m58s'
    # S.sss
    assert timestr(0.1234) == '0.123s'
    assert timestr(0.1236) == '0.124s'
    assert timestr(0.5) == '0.500s'
    assert timestr(0.9994) == '0.999s'
    # S.ss
    assert timestr(0.9996) == '1.00s'
    assert timestr(1.0) == '1.00s'
    assert timestr(2.009) == '2.01s'
    assert timestr(3.999) == '4.00s'
    assert timestr(9.9949) == '9.99s'
    # S.s
    assert timestr(9.9951) == '10.0s'
    assert timestr(10.01) == '10.0s'
    assert timestr(20.05) == '20.1s'
    assert timestr(30.951) == '31.0s'
    assert timestr(59.94) == '59.9s'
    # M S
    assert timestr(59.99) == '1m0s'
    assert timestr(60.01) == '1m0s'
    assert timestr(150.0) == '2m30s'
    assert timestr(3599.4) == '59m59s'
    # H M S
    assert timestr(3600.2) == '1h0m0s'
    assert timestr(35999.3) == '9h59m59s'
    # (D) H M
    assert timestr(35999.7) == '10h0m'
    assert timestr(36029.99) == '10h0m'
    assert timestr(36030.0) == '10h1m'
    assert timestr(86400+7200+660) == '1d2h11m'
    assert timestr(864000-40) == '9d23h59m'
    # D H
    assert timestr(864000-20) == '10d0h'
    assert timestr(864000) == '10d0h'
    assert timestr(864000.0) == '10d0h'
    assert timestr(864000+1799) == '10d0h'
    assert timestr(864000+1800) == '10d1h'
    assert timestr(864000+1801) == '10d1h'
    assert timestr(8640000) == '100d0h'

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

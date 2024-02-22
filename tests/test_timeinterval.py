"""
Test the timeinterval (a supporting module for TimeDate and TimeSpan)
"""
import datetime as dt
import random
import sys

import pytest

from edzed.blocklib import timeinterval as ti

# ISO 8601 support was pathetic before Python 3.11, we ignore it
P3_11 = sys.version_info >= (3, 11)

def test_time_conversions():
    from_seq = ti.convert_time_seq
    from_str = ti.convert_time_str

    for seq in [
            [13, 51, 20, 500_400], (7, 8, 9, 123), (0, 0), [23, 59, 59],
        ]:
        time = from_seq(seq)
        assert time == dt.time(*seq)
        extend4 = list(seq) + [0]*(4 - len(seq))
        assert ti.export_dt(time) == extend4

    time945 = from_seq([9, 45, 0, 210_000])
    strings = ['9:45:0.21', '09:45:00.210', '09:45:00,210']
    if P3_11:
        strings.extend(['T09:45:00.21', 'T094500.2100', '094500,2100'])
    for tstr in strings:
        assert from_str(tstr) == time945
        for whitespace in ["   {}", " {} ", "\t{}\t ", "{}  "]:
            assert from_str(whitespace.format(tstr)) == time945

    time10 = from_seq([10])
    strings = ['10:0 ', '10:00:0.0', '10:0:00']
    if P3_11:
        strings.extend(['10', 'T10', 'T1000 ', 'T10:00', 'T100000'])
    for tstr in strings:
        assert from_str(tstr) == time10

    assert (from_str('1:30') < from_str('1:30:0.000001') < from_seq((5, 5))
            < time945 < time10 < from_seq((13, 14, 15, 789)))

    for tstr in [
            "", "123", "T123", "12:60:00", "8 : 30", "8:30:", ":8:30"
        ]:
        with pytest.raises(ValueError):
            from_str(tstr)
    for tseq in [
            [], (25, 0), (-1, 0), (13, 60), (1, 1, 1, 1, 1),
        ]:
        with pytest.raises(ValueError):
            from_seq(tseq)


def test_timeinterval_ranges():
    ti1 = ti.TimeInterval('23:40:30-01:20:30, 10:30:0.0-21:10, 15:59:50.123-16:0')
    assert sorted(ti1.range_endpoints()) == [
        dt.time(1, 20, 30), dt.time(10, 30, 0),
        dt.time(15, 59, 50, 123_000), dt.time(16, 0, 0),
        dt.time(21, 10, 0), dt.time(23, 40, 30)]


def test_timeinterval_parsing():
    ti_args = '10:30:00 / 21:10:00; 15:59:50.123000 / 16:00:00; 23:40:30 / 01:20:30;' # ordered
    ti_seq = ti.TimeInterval(ti_args).as_list()
    ti_str = f"TimeInterval('{ti_args}')"

    for tstr in [
            '23:40:30-01:20:30   ,   10:30:0.0-21:10   , 15:59:50.123   /   16:0:0.0',
            '23:40:30 / 01:20:30, 10:30:0.0 / 21:10, 15:59:50.123-16:0:0.000000 ',
            '23:40:30.0 - 01:20:30; 10:30 / 21:10;     15:59:50,123-16;', # terminating ;
            '15:59:50,123-16:0:0.0; 23:40:30 - 01:20:30; 10:30:0.0 / 21:10',
            ]:
        ti_obj = ti.TimeInterval(tstr)
        assert ti_obj.as_list() == ti_seq
        assert ti_obj.as_string() == ti_args
        assert str(ti_obj) == ti_str
        assert repr(ti_obj).endswith(ti_str)

    for tstr in [
            # either semicolons or commas, not both
            '23:40:30 / 01:20:30, 10:30:0.0 / 21:10; 15:59:50.123-16:0:0.0',
            # decimal comma in time -> may not use comma separated ranges
            '23:40:30 - 01:20:30, 10:30:0.0 / 21:10, 15:59:50,123-16:0:0.0',
            '15:59:50,123-16:0:0.0',    # not even in one-range interval
            '15:59:50,123 - 16:0:0.0',
            '15:59:50,123/16:0:0.0',
        ]:
        with pytest.raises(ValueError):
            ti.TimeInterval(tstr)

    # decimal comma in an one-range interval
    for tstr in [
            '15:59:50,123/16:0:0.0;', '15:59:50,123-16:0:0.0;'
        ]:
        assert ti.TimeInterval(tstr).as_list() == [[[15, 59, 50, 123_000], [16, 0, 0, 0]]]


def test_timeinterval_mixed_types():

    def convert_random(tseq):
        return tuple(tseq) if random.randrange(2) else str(ti.convert_time_seq(tseq))

    conf = ti.TimeInterval(
        [(f"{h}:{m}", [h,m+7,30]) for h in range(24) for m in (30, 15, 0)]
        ).as_list()
    assert len(conf) == 24*3
    for _ in range(8):
        conf_copy = conf.copy()
        random.shuffle(conf_copy)
        assert ti.TimeInterval(
            { (convert_random(start), convert_random(stop)) for start, stop in conf_copy }
            ).as_list() == conf


def test_timeinterval():
    from_seq = ti.convert_time_seq
    from_str = ti.convert_time_str
    TI = ti.TimeInterval

    ti1 = TI('10:30 - 21:10')
    def test1(h, m, s):
        return (10, 30, 0) <= (h, m, s) < (21, 10, 0)

    ti2 = TI('23:40:30.20 - 01:20:30')
    def test2(h, m, s):
        return (23, 40, 30) <= (h, m, s) or (h, m, s) < (1, 20, 30)
    ti12 = TI(['23:40:30-01:20:30', ['10:30', [21, 10]]])

    ti3 = TI('6:44:27-6:44:28')
    assert from_str("6:44:27") in ti3
    assert from_str("6:44:28") not in ti3

    ti4 = TI('0:0-0:0')

    for h in range(24):
        for m in range(0, 60, 3):
            for s in [0, 20, 30]:
                time_of_day = from_seq((h, m, s))
                assert (time_of_day in ti1) == test1(h, m, s)
                assert (time_of_day in ti2) == test2(h, m, s)
                assert (time_of_day in ti12) == test1(h, m, s) or test2(h, m, s)
                assert time_of_day not in ti3    # 6:44:27 not in test data
                assert time_of_day in ti4


def test_date_conversions():
    from_seq = ti.convert_date_seq
    from_str = ti.convert_date_str

    md69 = from_seq([6, 9])
    assert md69 == dt.date(404, 6, 9)
    assert ti.export_dt(md69) == [6, 9]
    for dstr in [
            '09.JunE', '9.jun.', '9JUNe', '09 Jun',
            'Jun9', 'JUN  09', 'jun 9.',
            '--0609', '--06-09',
            ]:
        assert from_str(dstr) == md69
        for whitespace in ["   {}", " {} ", "\t {}\t ", "{}  "]:
            assert from_str(whitespace.format(dstr)) == md69

    assert (from_str('Apr 10') < from_str('1.may') < from_seq((5, 5))
            < md69 < from_str('Oct 31.') < from_seq((11, 1)) < from_str('--1201'))

    for dstr in [
            "", "okt. 10", "30.Feb", "what", "--1301", "0101",      # 'okt' is not 'oct'
            '09 Junius', "09_jun", "--0609-", "--6-9", "-06-09",
            ]:
        with pytest.raises(ValueError):
            from_str(dstr)
    for dseq in [
            [], [7], (0, 2), (2, 30), (13, 13), (1, 1, 1)
        ]:
        with pytest.raises(ValueError):
            from_seq(dseq)


def test_range_separators():
    for datestr in [
            "May 1-31. May", "1.May/--0531",
            "--0501 - --0531", "--05-01 - --05-31", "--05-01/31may",
        ]:
        assert ti.DateInterval(datestr).as_list() == [[[5,1], [5,31]]]

    # hyphens in the date
    for datestr in [
            "--0501-May 31", "May 1- --0601", "1 May---0601",
        ]:
        with pytest.raises(ValueError):
            ti.DateInterval(datestr)

    if not P3_11:
        return

    for datestr in [
            "2023-01-10 20:00:00.0 - 2024-01-10T20:00",
            "2023-01-10 20:00:00.0 - 2024-01-10T20:00,",
            "2023-01-10 20:00:00,0 - 2024-01-10T20:00;",
            "2023-01-10 20:00/2024-01-10T20",
            "2023-01-10 20:00/2024-01-10T20,",
            "2023-01-10 20:00/2024-01-10T20;",
        ]:
        assert ti.DateTimeInterval(datestr).as_list() == [
            [[2023,1,10,20,0,0,0], [2024,1,10,20,0,0,0]]]

    for datestr in [
            "2023-01-10 20:00-2024-01-10T20:00",
        ]:
        with pytest.raises(ValueError):
            ti.DateTimeInterval(datestr)


def test_dateinterval():
    from_seq = ti.convert_date_seq
    from_str = ti.convert_date_str
    DI = ti.DateInterval

    di1 = DI('Jan10 - April10')
    def test1(m, d):
        return (1, 10) <= (m, d) <= (4, 10)

    di2 = DI('15.dec - 15.jan')
    def test2(m, d):
        return (12, 15) <= (m, d) or (m, d) <= (1, 15)

    di12 = DI('15DECEM. - 15JAN, Jan.10-Apr.10')
    di12_args = 'Jan 10 / Apr 10; Dec 15 / Jan 15;'
    di12_str = f"DateInterval('{di12_args}')"
    assert di12.as_list() == [[[1,10],[4,10]], [[12,15],[1,15]]]
    assert di12.as_string() == di12_args
    assert str(di12) == di12_str
    assert repr(di12).endswith(di12_str)

    di3 = DI('3.aug')
    assert from_str("3.aug") in di3
    di4 = DI('1 jan / 31 dec')

    for d in [5, 10, 15, 25]:
        for m in range(1, 13):
            md = from_seq((m, d))
            assert (md in di1) == test1(m, d)
            assert (md in di2) == test2(m, d)
            assert (md in di12) == test1(m, d) or test2(m, d)
            assert md not in di3    # Aug, 3rd not in test data
            assert md in di4


def test_dateinterval_ranges():
    from_seq = ti.convert_date_seq
    di1 = ti.DateInterval('15DEC - 15JAN, Jan.10-Apr.10, 6.dec.')
    assert sorted(di1.range_endpoints()) == [
        from_seq((1, 10)), from_seq((1, 15)), from_seq((4, 10)),
        from_seq((12, 6)), from_seq((12, 15))]


def test_datetime_conversions():
    from_seq = ti.convert_datetime_seq
    from_str = ti.convert_datetime_str

    seq = (2028, 7, 20, 8, 9, 10, 110_000)
    b6 = from_seq(seq)
    assert b6 == dt.datetime(*seq)
    assert ti.export_dt(b6) == list(seq)

    strings = [
        '20 July 2028 8:9:10.11', '2028-JUL-20 08:9:10.110', '8:9:10.11 2028-07-20',
        '20. Jul. 8:9:10.11 2028', '2028jul20 8:9:10.11', '8:9:10.11jul2028 20.',
        ]
    if P3_11:
        strings.extend(['2028-07-20T080910.11'])
    for dstr in strings:
        assert from_str(dstr) == b6
        for whitespace in ["   {}", " {} ", "\t{}\t ", "{}  "]:
            assert from_str(whitespace.format(dstr)) == b6


    assert (from_str('Apr 10. 2024 0:0') < from_str('Apr. 10 2025 0:0')
            < from_seq((2026, 12, 1, 9, 0)) < from_seq([2026, 12, 1, 9, 0, 0, 1])
            < b6 < from_str('2028-07-20 8:9:10.21') < from_str('21. jul 2028 20:28')
            < from_seq((2029, 4, 5, 6, 7)) < from_seq([2029, 4, 6, 5, 4]))
    if P3_11:
        assert (from_str('2024-04-10T00') == from_str('20240410T00:00')
            < b6 < from_seq((2028, 12, 1, 9, 0)) < from_str('2028-12-01T090000.1'))

    for arg in [
            # incomplete:
            "", "Apr. 10 2024", "12.Feb", "today", "--1301", "15:10:00",
            "2024-04-10", "20240410",
            # extra chars:
            "028-07-20 8:9:10.21 -", "028-07-20_8:9:10.21",
            # non-ISO date with ISO time is not supported:
            "21. jul 2028 2028", "21. jul 2028 T2028", "21. jul 2028 T20:28:00",
            # malformed:
            "2015-AUG-3 6:00",
            ]:
        with pytest.raises(ValueError):
            from_str(arg)
    for arg in [
            [], [7], (2001, 2), (2001, 3, 4), (2001, 3, 4, 5),      # too short
            (2001, 3, 4, 5, 16, 17, 18, 18),                        # too long
            [2001, 13, 4, 20, 0], [2001, 3, 32, 20, 0], [2001, 3, 4, 60, 0],  # wrong date/time
            ]:
        with pytest.raises(ValueError):
            from_seq(arg)

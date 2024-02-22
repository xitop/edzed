"""
This module defines time/date intervals.

It is built on top of the datetime (dt) module:
    - time of day -> dt.time
    - date without a year -> dt.date with year set to a dummy value
    - date -> dt.date
    - full date+time -> dt.datetime

Intervals use those objects as endpoints:
    - TimeInterval defines time intervals within a day,
    - DateInterval defines periods in a year.
    - DateTimeInterval defines non-recurring intervals.

All intervals support the operation "value in interval".
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import datetime as dt
import re
from typing import Generic, Literal, overload, TypeVar, Union

from ..utils.tconst import MONTH_NAMES

# types accepted as inputs for: date/time, range (sub-interval), interval
# using Union, because T1|T2 is not supported in Python 3.9
IDT_Type = Union[Sequence[int], str]            # length: time = 1..4; date = 2; datetime = 5..7
IDT_RangeType = Union[str, Sequence[IDT_Type]]  # length = 1 (right-closed intervals only) or 2
IDT_IntervalType = Union[str, Sequence[IDT_RangeType], set[IDT_RangeType]]

# normalized types
NDT_Type = list[int]                    # sequence length: time = 4; date = 2, datetime = 7
NDT_RangeType = list[NDT_Type]
NDT_IntervalType = list[NDT_RangeType]

# real data type (result of conversions, source for exports)
DateTimeType = TypeVar("DateTimeType", dt.time, dt.date, dt.datetime)


@overload
def _match_pattern(
        string: str, pattern: re.Pattern[str]
        ) -> tuple[str, None|tuple[str, ...]]:
    ...
@overload
def _match_pattern(
        string: str, pattern: re.Pattern[str], errmsg: None
        ) -> tuple[str, None|tuple[str, ...]]:
    ...
@overload
def _match_pattern(
        string: str, pattern: re.Pattern[str], errmsg: str
        ) -> tuple[str, tuple[str, ...]]:
    ...
def _match_pattern(
        string: str, pattern: re.Pattern[str], errmsg: None|str = None
        ) -> tuple[str, None|tuple[str, ...]]:
    """
    Try to match the string with the pattern.

    Return value has two items:
        - match found - string with the matched part removed, all match groups in a tuple
        - no match - unmodified string, None
    """
    if not (match := pattern.search(string)):
        if errmsg:
            raise ValueError(errmsg)
        return string, None

    start, end = match.start(), match.end()
    if start == 0:
        string = string[end:]
    elif end == len(string):
        string = string[:start]
    else:
        # join the remaining pieces with a space
        string = ' '.join((string[:start], string[end:]))
    return string, match.groups()


def _name_to_month(name: str) -> int:
    capitalized_name = name.capitalize()
    for i, month_name in enumerate(MONTH_NAMES):
        # real start at index 1 = January;
        if i > 0 and month_name.startswith(capitalized_name):
            return i
    raise ValueError(f"invalid month name: {name!r}")


# _RE_YMD and _RE_MONTH now accept Unicode characters in the month name,
# but non-english names are not supported yet. They are using:
#  - [^\W\d_] as a workaround for unsupported [[:alpha:]]
#  - [0-9] instead of \d, because re.ASCII flag cannot be set.

# HH:MM  HH:M:SS HH:MM:SS.sss  HH:MM:SS,sss  (one or two digits for H, M, S)
_RE_TIME = re.compile(r'(\d{1,2}:\d{1,2}(:\d{1,2})?([.,]\d+)?)', flags=re.ASCII)

# YYYY-MM-DD  YYYY-month-DD
_RE_YMD = re.compile(r'([0-9]{4})-([^\W\d_]{3,}|[0-9]{2})-([0-9]{2})')

_RE_YEAR = re.compile(r'(\d{4})', flags=re.ASCII)
_RE_ISO_DM = re.compile(
    r'--(\d{2})-?(\d{2})', flags=re.ASCII)  # --MMDD --MM-DD (not valid ISO 8601, see the docs)
_RE_MONTH = re.compile(r'([^\W\d_]{3,})\.?')
_RE_DAY = re.compile(r'(\d{1,2})\.?', flags=re.ASCII)

@overload
def _convert_str(string: str, with_time: Literal[False]) -> dt.date:
    """Convert a date without year (month and day only)"""
@overload
def _convert_str(string: str, with_time: Literal[True]) -> dt.datetime:
    """Convert a complete date+time"""
def _convert_str(string: str, with_time: bool) -> dt.date|dt.datetime:
    original_string = string

    got_dm = False
    mgroups: None | tuple[str, ...]
    if with_time:
        string, mgroups = _match_pattern(string, _RE_TIME, "missing time")
        dt_time = convert_time_str(mgroups[0])

        string, mgroups = _match_pattern(string, _RE_YMD)
        if mgroups:
            got_dm = True
            year = int(mgroups[0])
            try:
                month = int(mgroups[1])
            except ValueError:
                month = _name_to_month(mgroups[1])
            day = int(mgroups[2])
        else:
            string, mgroups = _match_pattern(string, _RE_YEAR, "missing year")
            year = int(mgroups[0])

    if not got_dm:
        string, mgroups = _match_pattern(string, _RE_ISO_DM)
        if mgroups:
            month = int(mgroups[0])
            day = int(mgroups[1])
        else:
            string, mgroups = _match_pattern(string, _RE_MONTH, "missing month")
            month = _name_to_month(mgroups[0])
            string, mgroups = _match_pattern(string, _RE_DAY, "missing day of month")
            day = int(mgroups[0])

    string = string.strip()
    if string:
        raise ValueError(
            f"Could not convert {original_string!r}, offending part: {string!r}")

    if with_time:
        return convert_datetime_seq([year, month, day, *export_dt(dt_time)])
    return convert_date_seq([month, day])


_DT_ATTRS = "year month day hour minute second microsecond".split()
_ATTRS = {
    dt.time: _DT_ATTRS[3:],
    dt.date: _DT_ATTRS[1:3],
    dt.datetime: _DT_ATTRS
}

def export_dt(dt_object: DateTimeType, ) -> NDT_Type:
    """Export a date/time object."""
    return [getattr(dt_object, attr) for attr in _ATTRS[type(dt_object)]]


### time
def convert_time_seq(time_seq: Sequence[int]) -> dt.time:
    """[hour, minute=0, second=0, microsecond=0] -> time of day"""
    if not 1 <= len(time_seq) <= 4:
        raise ValueError(
            f"{time_seq} not in expected format: "
            "[hour, minute=0, second=0, µs=0]")
    # mypy is overlooking that the time_seq cannot have more than 4 items
    return dt.time(*time_seq, tzinfo=None)      # type: ignore[misc, arg-type]


def convert_time_str(time_str: str) -> dt.time:
    """string -> time of day"""
    time_str = time_str.strip()
    try:
        dt_time = dt.time.fromisoformat(time_str)
    except ValueError:
        pass
    else:
        if dt_time.tzinfo is not None:
            raise ValueError(f"{time_str!r}: time zones are not supported")
        return dt_time
    for fmt in ("%H:%M", "%H:%M:%S", "%H:%M:%S.%f", "%H:%M:%S,%f"):
        try:
            return dt.datetime.strptime(time_str, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Invalid time of date string: {time_str!r}")


### date
_DUMMY_YEAR = 404
# 404 is a leap year (allows Feb 29) and is not similar
# to anything related to modern date values

def convert_date_seq(date_seq: Sequence[int]) -> dt.date:
    """[month, day] -> date (without year)"""
    if len(date_seq) != 2:
        raise ValueError(f"{date_seq} not in expected format: [month, day]")
    return dt.date(_DUMMY_YEAR, *date_seq)


def convert_date_str(date_str: str) -> dt.date:
    """string -> date (without year)"""
    return _convert_str(date_str.strip(), with_time=False)


def date_to_string(date: dt.date) -> str:
    """date -> 'MMM DD' string"""
    assert date.year == _DUMMY_YEAR
    return f"{MONTH_NAMES[date.month][:3]} {date.day}"


### datetime
def convert_datetime_seq(datetime_seq: Sequence[int]) -> dt.datetime:
    """[year, month, day, hour, minute, second=0, microsecond=0] -> datetime"""
    if not 5 <= len(datetime_seq) <= 7:
        raise ValueError(
            f"{datetime_seq} not in expected format: "
            "[year, month, day, hour, minute, second=0, µs=0]")
    # mypy is overlooking that the time_seq cannot have more than 7 items
    return dt.datetime(*datetime_seq, tzinfo=None)      # type: ignore[misc, arg-type]


def convert_datetime_str(datetime_str: str) -> dt.datetime:
    """string -> datetime"""
    datetime_str = datetime_str.strip()
    if 'T' in datetime_str: # not accepting date without time of day
        try:
            dt_datetime = dt.datetime.fromisoformat(datetime_str)
        except ValueError:
            pass
        else:
            if dt_datetime.tzinfo is not None:
                raise ValueError(f"{datetime_str!r}: time zones are not supported")
            return dt_datetime
    return _convert_str(datetime_str, with_time=True)


_RANGE_SEPARATORS = ['/', ' - ', '-']    # high to low priority
_DELIMITER = ';'
_DELIMITER_LEGACY = ','
class _Interval(Generic[DateTimeType]):
    """
    The common part of Date/Time Intervals.

    Warning: time/date intervals do not follow the strict mathematical
    interval definition.
    """

    # https://en.wikipedia.org/wiki/Interval_(mathematics)#Terminology
    # the subintervals are always left-closed
    _RCLOSED_INTERVAL: bool     # are the subintervals right-closed?
    _convert_str: Callable[[str], DateTimeType]
    _convert_seq: Callable[[Sequence[int]], DateTimeType]
    _export: Callable[[DateTimeType], NDT_Type] = export_dt
    _str: Callable[[DateTimeType], str] = str

    def __init__(self, ivalue: IDT_IntervalType):
        """
        Usage: with comma or colon separated string type ranges or
        with a sequence of ranges:
            _Interval('subinterval1, subinterval2, ...')
            _Interval([subinterval1, subinterval2, ...])

        where each range (subinterval) is a pair of endpoints
        "from-to" or "from/to"(string) or [from, to] (sequence).
        If the interval is right-closed, a single value is accepted
        as both 'from' and 'to' endpoints.

        After splitting into endpoints, each value (str or sequence)
        is converted to time/date according to the actual interval type.

        The string value may contain whitespace around any endpoint.
        """
        self._interval: list[tuple[DateTimeType, DateTimeType]]
        if isinstance(ivalue, str):
            delimiter = _DELIMITER if _DELIMITER in ivalue else _DELIMITER_LEGACY
            ivalue = ivalue.split(delimiter)
            if ivalue and not ivalue[-1].strip():
                del ivalue[-1]
        elif not isinstance(ivalue, (Sequence, set)):
            raise TypeError(f"Unsupported argument type: {type(ivalue).__name__}")
        self._interval = sorted(self._parse_range(subint) for subint in ivalue)

    @staticmethod
    def _convert(
            value: IDT_Type,
            convert_str: Callable[[str], DateTimeType],
            convert_seq: Callable[[Sequence[int]], DateTimeType]
            ) -> DateTimeType:
        """Convert with the right function."""
        if isinstance(value, str):
            return convert_str(value)
        if isinstance(value, Sequence):
            assert not isinstance(value, str)   # for mypy
            return convert_seq(value)
        raise TypeError(
            f"Unsupported type: {type(value).__name__}; "
            f"cannot convert {value!r} to date/time")

    def _parse_range(self, rng: IDT_RangeType) -> tuple[DateTimeType, DateTimeType]:
        convert_str = type(self)._convert_str
        if isinstance(rng, str):
            for sep in _RANGE_SEPARATORS:
                if len(parts := rng.split(sep)) == 2:
                    return (convert_str(parts[0]), convert_str(parts[1]))
            if self._RCLOSED_INTERVAL:
                endpoint = convert_str(rng)
                return (endpoint, endpoint)
            raise ValueError(f"Invalid range {rng!r}")
        if isinstance(rng, Sequence):
            convert_seq = type(self)._convert_seq
            if (length := len(rng)) == 2:
                # sequence items could be also strings
                return (
                    self._convert(rng[0], convert_str, convert_seq),
                    self._convert(rng[1], convert_str, convert_seq))
            if length == 1 and self._RCLOSED_INTERVAL:
                # undocumented for sequences, only for strings
                endpoint = self._convert(rng[0], convert_str, convert_seq)
                return (endpoint, endpoint)
            raise ValueError("A range cannot have {length} endpoints: {rng}")
        raise TypeError(f"Invalid range {rng!r}")

    def range_endpoints(self) -> set[DateTimeType]:
        """return all unique range start and stop values."""
        enpoints = set()
        for start, stop in self._interval:
            enpoints.add(start)
            enpoints.add(stop)
        return enpoints

    @staticmethod
    def _cmp_open(low: DateTimeType, item: DateTimeType, high: DateTimeType) -> bool:
        """
        The ranges are left-closed and right-open intervals, i.e.
        value is in interval if and only if start <= value < stop
        """
        if low < high:
            return low <= item < high
        # low <= item < MAX or MIN <= item < high
        return low <= item or item < high

    @staticmethod
    def _cmp_closed(low: DateTimeType, item: DateTimeType, high: DateTimeType) -> bool:
        """
        The ranges are closed intervals, i.e.
        value is in interval if and only if start <= value <= stop
        """
        if low <= high:
            return low <= item <= high
        return low <= item or item <= high

    def _cmp(self, *args: DateTimeType) -> bool:
        return (self._cmp_closed if self._RCLOSED_INTERVAL else self._cmp_open)(*args)

    def __contains__(self, item: DateTimeType) -> bool:
        return any(self._cmp(low, item, high) for low, high in self._interval)

    def as_list(self) -> NDT_IntervalType:
        """
        Return the intervals as a nested list of integers.

        The output is a list of endpoint pairs. Each endpoint is a list
        of integers. The output is suitable as an input argument.
        """
        export = type(self)._export
        return [[export(start), export(stop)] for start, stop in self._interval]

    def _range_string(self, start: DateTimeType, stop: DateTimeType) -> str:
        to_string = type(self)._str
        if self._RCLOSED_INTERVAL and start == stop:
            return to_string(start) + _DELIMITER
        return f"{to_string(start)} {_RANGE_SEPARATORS[0]} {to_string(stop)}{_DELIMITER}"

    def as_string(self) -> str:
        return ' '.join(self._range_string(start, stop) for start, stop in self._interval)

    def __str__(self) -> str:
        cls = type(self)
        return f"{cls.__qualname__}('{self.as_string()}')"

    def __repr__(self) -> str:
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self.as_string()}')"


class TimeInterval(_Interval[dt.time]):
    """
    List of time ranges.

    The whole day is 00:00 - 00:00.
    """

    _RCLOSED_INTERVAL = False
    _convert_seq = convert_time_seq
    _convert_str = convert_time_str


class DateInterval(_Interval[dt.date]):
    """
    List of date ranges and single dates.
    """

    _RCLOSED_INTERVAL = True
    _convert_seq = convert_date_seq
    _convert_str = convert_date_str
    _str = date_to_string


class DateTimeInterval(_Interval[dt.datetime]):
    """
    List of datetime ranges.
    """

    _RCLOSED_INTERVAL = False
    _convert_seq = convert_datetime_seq
    _convert_str = convert_datetime_str

    @staticmethod
    def _cmp_open(low: dt.datetime, item: dt.datetime, high: dt.datetime) -> bool:
        """Compare function for non-recurring intervals."""
        return low <= item < high

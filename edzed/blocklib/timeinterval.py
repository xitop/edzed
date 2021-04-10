"""
This module defines:
    - HMS class representing an idealized local clock time
    - MD class representing a date within a year
    - intervals using the HMS or MD objects as endpoints:
        - TimeInterval defines fixed time intervals within a day,
        - DateInterval defines fixed periods in a year.
      Intervals support the operation "value in interval".
"""

import collections.abc as cabc
import re
import time
from typing import Generator, Sequence, Union

from ..utils.tconst import *   # pylint: disable=wildcard-import


DAYS = (None, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
# match group 1 = stripped match
RE_YEAR = re.compile(r'\s*(\d{4,})\s*', flags=re.ASCII)
RE_MONTH = re.compile(r'\s*([A-Z]{3,})\.?\s*', flags=re.ASCII|re.IGNORECASE)
RE_TIME = re.compile(r'\s*(\d{1,2}\s*:\s*\d{1,2}(\s*:\s*\d{1,2})?)\s*', flags=re.ASCII)
RE_DAY = re.compile(r'\s*(\d{1,2})\.?\s*', flags=re.ASCII)


def _cut(match):
    """
    Cut matched characters from the searched string.
    Join the remaining pieces with a space.
    """
    string, start, end = match.string, match.start(), match.end()
    if start == 0:
        return string[end:]
    if end == len(string):
        return string[:start]
    return ' '.join((string[:start], string[end:]))


# pylint: disable=invalid-name
def _ydt_convert(string, y=False, d=False, t=False):
    """
    Convert string to year (if y), month, day (if d), hour, minute, second (if t).

    The result is not fully validated.
    """

    year = month = day = None
    hms = (None, None, None)
    if t:
        match = RE_TIME.search(string)
        if not match:
            raise ValueError("missing time (H:M or H:M:S)")
        hms = [int(x) for x in match.group(1).split(':')]
        if len(hms) == 2:
            hms.append(0)
        string = _cut(match)
    if y:
        match = RE_YEAR.search(string)
        if not match:
            raise ValueError("missing year")
        year = int(match.group(1))
        string = _cut(match)
    if d:
        match = RE_MONTH.search(string)
        if not match:
            raise ValueError("missing month")
        name = match.group(1).capitalize()
        for i in range(1, 13):
            if MONTH_NAMES[i].startswith(name):
                month = i
                break
        else:
            raise ValueError(f"invalid month name: {match.group(1)!r}")
        string = _cut(match)
    if d:
        match = RE_DAY.search(string)
        if not match:
            raise ValueError("missing day of month")
        day = int(match.group(1))
        string = _cut(match)
    if string:
        raise ValueError(f"offending part: {string!r}")

    return (year, month, day, *hms)


def ydt_convert(string, *args, **kwargs):
    try:
        return _ydt_convert(string, *args, **kwargs)
    except Exception as err:
        raise ValueError(f"Could not convert {string!r}: {err}") from None


def _validate(y=None, md=None, hms=None):
    if y is not None:
        if y < 1970:
            # just a precaution, not a strict requirement
            raise ValueError(f"year {y} before start of the Unix Epoch (January 1, 1970)")
    if md is not None:
        month, day = md
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid month number: {month}")
        if not 1 <= day <= DAYS[month]:
            raise ValueError(f"Invalid day in month number: {day}")
    if hms is not None:
        # leap second H:M:60 is accepted
        if not 0 <= hms[0] < 24 or not 0 <= hms[1] < 60 or not 0 <= hms[2] <= 60:
            raise ValueError(f"Time {hms} not between 0:0:0 and 23:59:59")


def _to_intlist(seq):
    try:
        return [int(x) for x in seq]
    except TypeError:
        raise TypeError(f"Cannot convert this type: {seq!r}")
    except ValueError:
        raise ValueError(f"Cannot convert this value: {seq!r}")


class HMS(tuple):
    """
    HMS stands for hour, minute, second. It is a 3-tuple representing
    a clock time within a day, always between (0,0,0) and (23,59,59).

    It can be directly compared with other tuples of the same format.

    Individual fields are accessible as hour, minute and second
    attributes.
    """

    def __new__(
            cls,
            hms: Union[None, 'HMS', time.struct_time, int, str, Sequence[int]] = None):
        """
        HMS() or HMS(None) = use the current local time of day
        HMS(hms) = return the existing instance
        HMS(time.struct_time) = use the provided time
        HMS(integer) = convert the seconds counted from midnight 00:00:00
        HMS(string) = convert from "HH:MM" or "HH:MM:SS" format
        HMS(iterable with 2 elements) = use as hour and minute value
        HMS(iterable with 3 elements) = use as hour, minute, and second
                                        (avoid unordered iterables)
        """
        if isinstance(hms, cls):
            # OK, it is immutable
            return hms
        if hms is None:
            hms = time.localtime()
        if isinstance(hms, time.struct_time):
            hms3 = (hms.tm_hour, hms.tm_min, hms.tm_sec)
        elif isinstance(hms, int):
            seconds = hms % SEC_PER_DAY
            hours, seconds = divmod(seconds, SEC_PER_HOUR)
            minutes, seconds = divmod(seconds, SEC_PER_MIN)
            hms3 = (hours, minutes, seconds)
        else:
            if isinstance(hms, str):
                hms3 = ydt_convert(hms, t=True)[3:6]
            else:
                hms3 = _to_intlist(hms)
                if len(hms3) == 2:
                    hms3.append(0)
                elif len(hms3) != 3:
                    raise ValueError(f"Invalid time specification: {hms!r}")
            _validate(hms=hms3)
        return super().__new__(cls, hms3)

    @property
    def hour(self) -> int:
        return self[0]

    @property
    def minute(self) -> int:
        return self[1]

    @property
    def second(self) -> int:
        return self[2]

    def seconds(self) -> int:
        """Return seconds counted from 00:00:00."""
        return self[0]*SEC_PER_HOUR + self[1]*SEC_PER_MIN + self[2]

    def seconds_from(self: 'HMS', other: 'HMS') -> int:
        """
        Return seconds from other HMS to this HMS.

        The result is always >= 0:
            HMS('10:30').seconds_from(HMS('9:30')) ==  1 * SEC_PER_HOUR
        because 10:30 is one hour after 9:30, but:
            HMS('9:30').seconds_from(HMS('10:30')) == 23 * SEC_PER_HOUR
        because 9:30 is 23 hours after 10:30.
        """
        sec = self.seconds() - other.seconds()
        return sec + SEC_PER_DAY if sec < 0 else sec

    def __str__(self):
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}"

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


class MD(tuple):
    """
    MD stands for month and day. It is a 2-tuple representing a calendar
    date, i.e. always between (1,1) and (12,31).

    It can be directly compared with other tuples of the same format.

    Individual fields are accessible as day and month attributes.
    """

    def __new__(cls, md: Union[None, 'MD', time.struct_time, str, Sequence[int]] = None):
        """
        MD() or MD(None) = use the current local date
        MD(md) = return the existing instance
        MD(time.struct_time) = use the provided date
        MD(string) = convert from a string
        MD(iterable with 2 elements) = use as day and month numeric values
                                       (avoid unordered iterables)

        When building from a string, the month must be written as a three
        letter English acronym in order to avoid ambiguities. The rules:
            - day = 1 or 2 digits
            - month = 3 letters in lower, upper or mixed case
            - there may be one period (full stop) appended
              directly to the day or the month
            - the date consists of day and month in this or in
              reversed order
            - leading, trailing whitespace and any whitespace between
              the day and the month is ignored
        Examples:
            09.Jun   9.jun.   9JUN   09 Jun   Jun9   JUN 09   Jun.9.
        """
        if isinstance(md, cls):
            # OK, it is immutable
            return md
        if md is None:
            md = time.localtime()
        if isinstance(md, time.struct_time):
            md2 = (md.tm_mon, md.tm_mday)
        else:
            if isinstance(md, str):
                md2 = ydt_convert(md, d=True)[1:3]
            else:
                md2 = _to_intlist(md)
                if len(md) != 2:
                    raise ValueError(f"Invalid month, day specification: {md!r}")
            _validate(md=md2)
        return super().__new__(cls, md2)

    @property
    def month(self) -> int:
        return self[0]

    @property
    def day(self) -> int:
        return self[1]

    def __str__(self):
        """Output format is 'Jun.09'"""
        return f'{MONTH_NAMES[self.month][:3]}.{self.day:02d}'

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


class YDT(tuple):
    """
    YDT stands for year, date (as in MD) and time (as in HMS).
    It is a 6-tuple of integers: (year, month, date, hour, minute, second).

    It can be directly compared with other tuples of the same format.

    Individual fields are accessible as attributes.
    """

    def __new__(cls, ydt: Union[None, 'YDT', time.struct_time, str, Sequence[int]] = None):
        """
        YDT() or YDT(None) = use the current local date and time
        YDT(ydt) = return the existing instance
        YDT(time.struct_time) = use the provided time
        YDT(string) = convert from a string
        YDT(iterable with 5 elements) = use as year, month, day, hour and minute value
        YDT(iterable with 6 elements) = use as year, ... second
                                        (avoid unordered iterables)
        """
        if isinstance(ydt, cls):
            # OK, it is immutable
            return ydt
        if ydt is None:
            ydt = time.localtime()
        if isinstance(ydt, time.struct_time):
            ydt6 = tuple(ydt[0:6])
        else:
            if isinstance(ydt, str):
                ydt6 = ydt_convert(ydt, y=True, d=True, t=True)
            else:
                ydt6 = _to_intlist(ydt)
                if len(ydt6) == 5:
                    ydt6.append(0)
                elif len(ydt6) != 6:
                    raise ValueError(f"Invalid date and time specification: {ydt!r}")
                _validate(y=ydt6[0], md=ydt6[1:3], hms=ydt6[3:6])
        return super().__new__(cls, ydt6)

    @property
    def year(self) -> int:
        return self[0]

    @property
    def month(self) -> int:
        return self[1]

    @property
    def day(self) -> int:
        return self[2]

    @property
    def hour(self) -> int:
        return self[3]

    @property
    def minute(self) -> int:
        return self[4]

    @property
    def second(self) -> int:
        return self[5]

    def __str__(self):
        return f"{self.year} {MONTH_NAMES[self.month][:3]}.{self.day:02d} " \
               f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}"

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


SEPCHAR = ','
RANGECHAR = '-'
class _Interval:
    """
    The common part of TimeInterval and DateInterval.

    Warning: time/date intervals do not follow strict mathematic
    interval definition.
    """

    # https://en.wikipedia.org/wiki/Interval_(mathematics)#Terminology
    # the subintervals are always left-closed
    _RCLOSED_INTERVAL = False # are the subintervals also right-closed?

    @staticmethod
    def _convert(val: Union[str, Sequence]):
        """Convert interval endpoint."""

    def __init__(self, ivalue: Union[None, '_Interval', str, Sequence] = None):
        """
        _Interval() = empty interval
        _Interval(interval) = copy of interval
        _Interval('string') = converted from a string containing comma
            separated ranges:
                "FROM1-TO1,FROM2-TO2".
            If _RCLOSED_INTERVAL is True a single value is accepted
            as well, e.g.:
                "FROM1-TO1,VALUE2"
            is equivalent to "FROM1-TO1, VALUE2-VALUE2".
            The input string may contain whitespace around any value.
        _Interval([[from1, to1], [from2, to2], ...]) = create from
            a sequence of pairs
        """
        if ivalue is None:
            self._interval = []
            return
        if isinstance(ivalue, type(self)):
            # pylint: disable=protected-access
            self._interval = ivalue._interval.copy()
            return
        if isinstance(ivalue, str):
            self._interval = []
            ivalue = ivalue.strip()
            if not ivalue:
                return
            for rstr in ivalue.split(SEPCHAR):
                try:
                    split_here = rstr.index(RANGECHAR, 1, -1)
                except ValueError:
                    if not self._RCLOSED_INTERVAL:
                        raise ValueError(f"Invalid range {rstr!r}") from None
                    low = high = self._convert(rstr)
                else:
                    low = self._convert(rstr[:split_here])
                    high = self._convert(rstr[split_here+1:])
                self._interval.append((low, high))
            return
        if isinstance(ivalue, (cabc.Sequence, cabc.Iterator)):
            self._interval = [(self._convert(low), self._convert(high)) for low, high in ivalue]
            return
        raise TypeError("Invalid interval value")

    def range_endpoints(self) -> Generator:
        """Yield all range start and stop values."""
        for low, high in self._interval:
            yield low
            yield high

    @staticmethod
    def _cmp_open(low, item, high):
        """
        The ranges are left-closed and right-open intervals, i.e.
        value is in interval if and only if start <= value < stop
        """
        if low < high:
            return low <= item < high
        return low <= item or item < high   # low <= item < MAX or MIN <= item < high

    @staticmethod
    def _cmp_closed(low, item, high):
        """
        The ranges are closed intervals, i.e.
        value is in interval if and only if start <= value <= stop
        """
        if low <= high:
            return low <= item <= high
        return low <= item or item <= high

    def _cmp(self, *args):
        return (self._cmp_closed if self._RCLOSED_INTERVAL else self._cmp_open)(*args)

    def __contains__(self, item):
        return any(self._cmp(low, item, high) for low, high in self._interval)

    def as_list(self):
        """
        Return the intervals as a nested list of integers.

        The output is suitable as an input argument.
        """
        return [[list(low), list(high)] for low, high in self._interval]

    def __str__(self):
        def fmt(low, high):
            if self._RCLOSED_INTERVAL and low == high:
                return str(low)
            return f"{low}{RANGECHAR}{high}"
        return f'{SEPCHAR} '.join(fmt(low, high) for low, high in self._interval)

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


class TimeInterval(_Interval):
    """
    List of time ranges.

    See the HMS class for time formats.

    The whole day is 00:00 - 00:00.
    """

    _RCLOSED_INTERVAL = False
    def _convert(self, val):
        if isinstance(val, int):
            # HMS can convert int, but in this context it is almost
            # certainly a result of a malformed input. Compare:
            #   incorrect: [[h1,m1],[h2,m2]]
            #   correct:  [[[h1,m1],[h2,m2]]]
            raise TypeError(
                f"Expected was [H, M] or [H, M, S], but got an int ({val}); "
                "check the structure of the input argument")
        return HMS(val)


class DateInterval(_Interval):
    """
    List of date ranges and single dates.

    See the MD class for date formats.
    """

    _RCLOSED_INTERVAL = True
    _convert = MD


class DateTimeInterval(_Interval):
    """
    List of date+time ranges.

    See the YDT class.
    """

    _RCLOSED_INTERVAL = False
    _convert = YDT

    @staticmethod
    def _cmp_open(low, item, high):
        """Compare function for non-repeating intervals."""
        return low <= item < high

"""
This module defines:
    - HMS class representing an idealized local clock time
    - MD class representing a date within a year
    - intervals using the HMS or MD objects as endpoints:
        - TimeInterval defines fixed time intervals within a day,
        - DateInterval defines fixed periods in a year.
      Intervals support the operation "value in interval".
"""

import abc
import re
import time
from typing import Iterator, Sequence, Union

from .tconst import *   # pylint: disable=wildcard-import


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
        HMS() or HMS(None) = use the current time of day
        HMS(hms) = return the existing instance
        HMS(time.struct_time) = use the provided time
        HMS(integer) = convert the seconds counted from midnight 00:00:00
        HMS(string) = convert from "HH:MM" or "HH:MM:SS" format
        HMS(iterable with 2 elements) = use as hours and minutes value
        HMS(iterable with 3 elements) = use as hours, minutes, and seconds
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
                hms3 = hms.split(':')
            else:
                try:
                    hms3 = list(hms)
                except TypeError:
                    raise TypeError(
                        f"Cannot convert argument of this type: {hms!r}") from None
            if len(hms3) == 2:
                hms3.append(0)
            elif len(hms3) != 3:
                raise ValueError(f"Invalid time specification: '{hms}'")
            hms3 = [int(x) for x in hms3]
            if not 0 <= hms3[0] < 24 or not 0 <= hms3[1] < 60 or not 0 <= hms3[2] < 60:
                raise ValueError(f"Invalid time of day: '{hms}'")
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
        return '{0[0]:02d}:{0[1]:02d}:{0[2]:02d}'.format(self)

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

    NAMES = (
        None,
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    DAYS = (None, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    _RE_D = r'(?P<day>[0-9]{1,2})\.?'
    _RE_M = r'(?P<month>[a-zA-Z]{3})\.?'
    _RE_S = r'\s*'
    _RE1 = re.compile(_RE_D + _RE_S + _RE_M)
    _RE2 = re.compile(_RE_M + _RE_S + _RE_D)

    def __new__(cls, md: Union[None, 'MD', time.struct_time, str, Sequence[int]] = None):
        """
        MD() or MD(None) = use the current date
        MD(md) = return the existing instance
        MD(time.struct_time) = use the provided date
        MD(string) = convert from a string
        MD(iterable with 2 elements) = use as day and month numeric values
                                       (avoid unordered iterables)

        When building from a string, the month must be written as a three
        letter English acronym in order to avoid ambiguities. The rules:
            - day = 1 or 2 digits
            - month = 3 letters in lower, upper or mixed case
            - there may be one dot appended directly to the day
              or the month
            - the date consists of day and month in this or in
              reversed order
            - leading, trailing whitespace and any whitespace between
              the day and the month is ignored
        Examples:
            09.Jun   9.jun.   9JUN   09 Jun   Jun9   JUN 09   Jun.9.
        """
        if isinstance(md, cls):
            return md
        if md is None:
            md = time.localtime()
        if isinstance(md, time.struct_time):
            md = (md.tm_mon, md.tm_mday)
        else:
            if isinstance(md, str):
                md = md.strip()
                mres = cls._RE1.fullmatch(md) or cls._RE2.fullmatch(md)
                if mres is None:
                    raise ValueError(f"Invalid date specification: '{md}'")
                day = int(mres.group('day'))
                try:
                    month = cls.NAMES.index(mres.group('month').capitalize())
                except ValueError:
                    raise ValueError(f"Invalid month name: '{mres.group('month')}'") from None
                md = (month, day)
            else:
                try:
                    month, day = md
                except TypeError:
                    raise TypeError(
                        f"Cannot convert argument of this type: {md!r}") from None
                except ValueError:
                    raise ValueError(f"Invalid date specification: {md}") from None
            if not 1 <= month <= 12:
                raise ValueError(f"Invalid month number: {month}")
            if not 1 <= day <= cls.DAYS[month]:
                raise ValueError(f"Invalid day in month number: {day}")
        return super().__new__(cls, md)

    @property
    def month(self) -> int:
        return self[0]

    @property
    def day(self) -> int:
        return self[1]

    def __str__(self):
        """Output format is 'Jun.09'"""
        return f'{self.NAMES[self.month]}.{self.day:02d}'

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


SEPCHAR = ','
RANGECHAR = '-'
class Interval(metaclass=abc.ABCMeta):
    """
    A list of ranges (subintervals).
    """

    # https://en.wikipedia.org/wiki/Interval_(mathematics)#Terminology
    # the subintervals are always left-closed
    _RCLOSED_INTERVAL = False # are the subintervals also right-closed?

    @staticmethod
    @abc.abstractmethod
    def _convert(val: str):
        """Convert interval endpoint."""

    def __init__(self, ivalue: Union[None, 'Interval', str] = None):
        """
        Interval() = empty interval
        Interval(interval) = copy of interval
        Interval('string') = converted from a string containing comma
            separated ranges:
                "FROM1-TO1,FROM2-TO2".
            If _RCLOSED_INTERVAL is True a single value is accepted
            as well, e.g.:
                "FROM1-TO1,VALUE2"
            is equivalent to "FROM1-TO1, VALUE2-VALUE2".
            The input string may contain whitespace around any value.
        """
        if ivalue is None:
            self._interval = []
            return
        if isinstance(ivalue, type(self)):
            # pylint: disable=protected-access
            self._interval = ivalue._interval.copy()
            return
        if isinstance(ivalue, str):
            interval = []
            for rstr in ivalue.split(SEPCHAR):
                rstr = rstr.strip()
                try:
                    split_here = rstr.index(RANGECHAR, 1, -1)
                except ValueError:
                    if not self._RCLOSED_INTERVAL:
                        raise ValueError(f"Invalid range '{rstr}'") from None
                    low = high = self._convert(rstr)
                else:
                    low = self._convert(rstr[:split_here].rstrip())
                    high = self._convert(rstr[split_here+1:].lstrip())
                interval.append((low, high))
            self._interval = interval
            return
        raise TypeError("Invalid interval value")

    def range_starts(self) -> Iterator:
        """Return an iterator of all range start values."""
        return (low for low, high in self._interval)

    def range_ends(self) -> Iterator:
        """Return an iterator of all range end values."""
        return (high for low, high in self._interval)

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

    def __str__(self):
        def fmt(low, high):
            if self._RCLOSED_INTERVAL and low == high:
                return str(low)
            return f"{low}{RANGECHAR}{high}"
        return f'{SEPCHAR} '.join(fmt(low, high) for low, high in self._interval)

    def __repr__(self):
        cls = type(self)
        return f"{cls.__module__}.{cls.__qualname__}('{self}')"


class TimeInterval(Interval):
    """
    List of time ranges.

    Times are in 24-hour clock and HH:MM or HH:MM:SS format (leading
    zero is optional, i.e. 01:05 and 1:5 are equivalent). Example:
        23:50-01:30, 3:20-5:10

    The whole day is 00:00 - 00:00.
    """

    _RCLOSED_INTERVAL = False
    _convert = HMS


class DateInterval(Interval):
    """
    List of date ranges and single dates.

    See the MD class for date formats, e.g.
        May1-May15, 31.Dec

    The whole year is 1.jan - 31.dec.
    """

    _RCLOSED_INTERVAL = True
    _convert = MD

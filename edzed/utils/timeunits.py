"""
Conversion routines for time spans using multiple units.

Example: "20h15m10" = 20 hours + 15 minutes + 10 seconds = 72910 seconds
"""

from __future__ import annotations

from typing import overload
import re

from .tconst import *   # pylint: disable=wildcard-import, unused-wildcard-import

__all__ = ['timestr', 'timestr_approx', 'convert', 'time_period']

# note: type hint float includes also integers

def timestr(seconds: float, sep: str = '', prec: int = 3) -> str:
    """
    Return seconds as a string using d, h, m and s units.

    The individual parts are separated with the 'sep' string.

    Fractional seconds are formatted to 'prec' decimal places.
    """
    if seconds < 0:
        raise ValueError("Number of seconds cannot be negative")
    is_float = isinstance(seconds, float)
    if is_float:
        seconds = round(seconds, prec)
    d, s = divmod(seconds, SEC_PER_DAY)
    h, s = divmod(s, SEC_PER_HOUR)
    m, s = divmod(s, SEC_PER_MIN)
    parts = []
    if d:
        parts.append(f"{int(d)}d")
    if d or h:
        parts.append(f"{int(h)}h")
    parts.append(f"{int(m)}m")
    parts.append(f"{s:.{prec}f}s" if is_float else f"{s}s")
    return sep.join(parts)


def timestr_approx(seconds: float, sep: str = '') -> str:
    """
    Return possibly rounded seconds as a string using d, h, m, s units.

    The individual parts are separated with the 'sep' string.
    """
    #      ge  lt*   format  arg-type
    #     ---  ---   ------  --------
    #       0   1s   0.sss   float
    #      1s  10s   S.ss    float
    #     10s   1m   S.s     float
    #       0   1m   S       int
    #      1m   1h   M S
    #      1h  10h   H M S
    #     10h   1d   D M
    #     10h  10d   D H M
    #     10d        D H
    #
    # (*) lt (less than) after rounding. We want to prevent this:
    #   0.9998 -> 1 with three decimal places = 1.000
    #   1.0002 -> 1 with two decimal places   = 1.00
    # We prefer consistency and always have 0.xxx and 1.yy.

    if seconds < 0:
        raise ValueError("Number of seconds cannot be negative")
    omit_minutes = omit_seconds = False
    if isinstance(seconds, float):
        # the rounding issues are trickier than it might seem ...
        if seconds < 1.0:
            sprec = 3   # seconds' precision (decimal places)
            seconds = round(seconds, sprec) # may be now equal to 1.0, no elif in the next line
        if 1.0 <= seconds < 10.0:
            sprec = 2
            seconds = round(seconds, sprec) # may be now equal to 10.0
        if 10.0 <= seconds < 60.0:
            sprec = 1
            seconds = round(seconds, sprec) # may be now equal ... etc.
        if 60.0 <= seconds < 10*SEC_PER_HOUR:
            seconds = round(seconds)        # now an int => 'sprec' unused
    # int or float
    if 10*SEC_PER_HOUR <= seconds < 10*SEC_PER_DAY:
        omit_seconds = True
        seconds = SEC_PER_MIN * int(seconds / SEC_PER_MIN + 0.5)    # round to nearest minute
    if 10*SEC_PER_DAY <= seconds:
        omit_seconds = omit_minutes = True
        seconds = SEC_PER_HOUR * int(seconds / SEC_PER_HOUR + 0.5)  # round to nearest hour

    d, s = divmod(seconds, SEC_PER_DAY)
    h, s = divmod(s, SEC_PER_HOUR)
    if not omit_minutes:
        m, s = divmod(s, SEC_PER_MIN)
    parts = []
    if d:
        parts.append(f"{int(d)}d")
    if d or h:
        parts.append(f"{int(h)}h")
    # pylint - "m" is defined when (not omit_minutes) is true
    # pylint: disable-next=possibly-used-before-assignment)
    if not omit_minutes and (m or h or d):
        parts.append(f"{int(m)}m")
    if not omit_seconds:
        # seconds = original value; s = 0 to 60 seconds
        parts.append(f"{s:.{sprec}f}s" if isinstance(seconds, float) else f"{s}s")
    return sep.join(parts)


_NUM = r'(\d+(?:[.,]\d+)?)'   # a match group for a number with optional fractional part
_RE_DURATION = re.compile(rf"""
    \s*
    (?:{_NUM}\s*d)?  \s*  (?:{_NUM}\s*h)?  \s*
    (?:{_NUM}\s*m)?  \s*  (?:{_NUM}\s*s?)?  \s*
    """, flags = re.ASCII | re.IGNORECASE | re.VERBOSE)
_RE_ISO_DURATION = re.compile(rf"""
    \s*
    P (?:{_NUM}Y)?  (?:{_NUM}M)?  (?:{_NUM}D)?
    (?:
        T  (?:{_NUM}H)?  (?:{_NUM}M)?  (?:{_NUM}S)?
     )?
     \s*
     """, flags = re.ASCII | re.VERBOSE)

def _convert(tstr: str) -> float:
    """
    Convert string to number of seconds. Return float.

    Supports the traditional format and the ISO 8601 format
    but with years and months not accepted.
    """
    if not any((match := re.fullmatch(tstr)) for re in (_RE_DURATION, _RE_ISO_DURATION)):
        raise ValueError("Invalid time representation")
    assert match is not None        # mypy

    result = 0.0
    smallest_unit = True
    for value, scale_factor in zip(
            reversed(match.groups()),
            (1, SEC_PER_MIN, SEC_PER_HOUR, SEC_PER_DAY, None, None)
            ):
        if value is None:
            continue
        if (decimal_comma := ',' in value) or ('.' in value):
            if not smallest_unit:
                raise ValueError("only the smallest unit may have a fractional part")
            if decimal_comma:
                value = value.replace(',', '.', 1)
        num = float(value)
        smallest_unit = False
        if num == 0.0:
            continue
        if scale_factor is None:
            raise ValueError("calendar years/months are not supported as duration units")
        result += num * scale_factor
    if smallest_unit:
        raise ValueError("at least one element must be present")
    return result


def convert(tstr: str) -> float:
    try:
        return _convert(tstr)
    except ValueError as err:
        raise ValueError(f"{tstr!r}: {err}") from None


@overload
def time_period(period: None) -> None:
    ...
@overload
def time_period(period: float|str) -> float:
    ...
def time_period(period: None|float|str) -> None|float:
    """Convenience wrapper for convert()."""
    if period is None:
        return None
    if isinstance(period, int):
        period = float(period)
    if isinstance(period, float):
        return max(0.0, period)
    if isinstance(period, str):
        return convert(period)
    raise TypeError(f"Invalid type for time period specification: {period!r}")

"""
Conversion routines for time spans using multiple units.

Example: "20h15m10" = 20 hours + 15 minutes + 10 seconds = 72910 seconds
"""

from __future__ import annotations

from typing import overload
import re

from .tconst import *   # pylint: disable=wildcard-import, unused-wildcard-import

__all__ = ['timestr', 'timestr_approx', 'convert', 'time_period']

# pylint: disable=invalid-name
def timestr(seconds: int|float, sep: str = '', prec: int = 3) -> str:
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

def timestr_approx(seconds: int|float, sep: str = '') -> str:
    """
    Return possibly rounded seconds as a string using d, h, m, s units.

    The individual parts are separated with the 'sep' string.
    """
    #      ge  lt*   format
    #     ---  ---   ------
    #           1s   0.sss (float)
    #      1s  10s   S.ss  (float)
    #     10s   1m   S.s   (float)
    #           1m   S     (int)
    #      1m  10h   (H) M S
    #     10h  10d   (D) H M
    #     10d        D H
    #
    # (*) lt (less than) after rounding. We want to prevent e.g. 0.9998
    # to be rounded to 1 with three decimal places 1.000, but 1.002 to
    # 1 with two decimal places 1.00. We prefer consistency and always
    # have 0.xxx and 1.yy.

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
    if not omit_minutes and (d or h or m):
        parts.append(f"{int(m)}m")
    if not omit_seconds:
        # seconds = original value; s = 0 to 60 seconds
        parts.append(f"{s:.{sprec}f}s" if isinstance(seconds, float) else f"{s}s")
    return sep.join(parts)

_RE_TIME = r'(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:([\d.]+)\s*s?)?'
_REGEXP_TIME = re.compile(_RE_TIME, re.ASCII | re.IGNORECASE)

def convert(tstr: str) -> float:
    """
    Convert string to number of seconds. Return float.

    Format:
        TIMESTR = [DAYS] [HOURS] [MINUTES] [SECONDS]
    where:
        DAYS = <int> "D"
        HOURS = <int> "H"
        MINUTES = <int> "M"
        SECONDS =  <int or float> ["S"]
    Notes:
        - whitespace around numbers and units is allowed
        - numbers do not have to be normalized, e.g. "72h" is OK
        - unit symbols D, H, M, S may be entered in upper or lower case
        - negative values are not allowed
        - float values with exponents are not supported
    """
    match = _REGEXP_TIME.fullmatch(tstr.strip())
    if match is None:
        raise ValueError("Invalid time representation")
    d, h, m, s = match.groups()
    result = 0.0
    if d:
        result += int(d) * SEC_PER_DAY
    if h:
        result += int(h) * SEC_PER_HOUR
    if m:
        result += int(m) * SEC_PER_MIN
    if s:
        result += float(s)  # may raise ValueError, the regexp is not strict enough
    return result

@overload
def time_period(period: None) -> None:
    ...
@overload
def time_period(period: int|float|str) -> float:
    ...
def time_period(period):
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

"""
Conversion routines for time spans using multiple units.

Example: "20h15m10" = 20 hours + 15 minutes + 10 seconds = 72910 seconds
"""

import re
from typing import Optional, Union

from .tconst import *   # pylint: disable=wildcard-import, unused-wildcard-import

__all__ = ['timestr', 'convert', 'time_period']

# pylint: disable=invalid-name
def timestr(seconds: Union[int, float]) -> str:
    """
    Return seconds as a string using d, h, m and s units.

    Minutes and seconds are always present in the result.
    Days and hours are prepended only when needed.

    This is an inverse function to convert() below.
    Partial seconds are formatted to 3 decimal places.
    """
    if seconds < 0:
        raise ValueError("Number of seconds cannot be negative")
    d, s = divmod(seconds, SEC_PER_DAY)
    h, s = divmod(s, SEC_PER_HOUR)
    m, s = divmod(s, SEC_PER_MIN)
    parts = []
    if d:
        parts.append(f"{int(d)}d")
    if d or h:
        parts.append(f"{int(h)}h")
    parts.append(f"{int(m)}m")
    # seconds = original value; s = 0 to 60 seconds
    parts.append(f"{s:.3f}s" if isinstance(seconds, float) else f"{s}s")
    return ''.join(parts)


_RE_TIME = r'(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:([\d.]+)\s*s?)?'
_REGEXP_TIME = re.compile(_RE_TIME, re.ASCII | re.IGNORECASE)

def convert(tstr: str) -> float:
    """
    Convert string to number of seconds. Return float.

    Format:
        TIMESTR = [DAYS] [HOURS] [MINUTES] [SECONDS]
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


def time_period(period: Union[None, int, float, str]) -> Optional[float]:
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

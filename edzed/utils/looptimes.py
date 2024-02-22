"""
Convert timestamps between event loop and system.
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional


def _get_timediff() -> float:
    """Return the difference between loop and Unix time bases."""
    unixtime_func = time.time
    looptime_func = asyncio.get_running_loop().time
    unixbefore = unixtime_func()
    loopnow = looptime_func()
    unixafter = unixtime_func()
    return (unixbefore + unixafter) / 2 - loopnow

def loop_to_unixtime(looptime: float, timediff: Optional[float] = None) -> float:
    """Convert event loop time to standard Unix time."""
    if timediff is None:
        timediff = _get_timediff()
    return looptime + timediff

def unix_to_looptime(unixtime: float, timediff: Optional[float] = None) -> float:
    """Convert standard Unix time to event loop time."""
    if timediff is None:
        timediff = _get_timediff()
    return unixtime - timediff

"""
Convert timestamps between event loop and system.
"""

import asyncio
import time


def _get_timediff():
    """Return the difference between loop and Unix time bases."""
    loopnow = asyncio.get_running_loop().time()
    unixnow = time.time()
    return unixnow - loopnow

def loop_to_unixtime(looptime, timediff=None):
    """Convert event loop time to standard Unix time."""
    if timediff is None:
        timediff = _get_timediff()
    return looptime + timediff

def unix_to_looptime(unixtime, timediff=None):
    """Convert standard Unix time to event loop time."""
    if timediff is None:
        timediff = _get_timediff()
    return unixtime - timediff

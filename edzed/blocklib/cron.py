"""
Call the 'recalc' method of all registered blocks at given times of day.

Intervals given by time, date, and weekdays are implemented on top
of this low-level service.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import asyncio
import bisect
from dataclasses import dataclass
import time
from typing import NoReturn

from .. import addons
from .. import block
from .. import utils
from . import timeinterval as ti

# HMS is an abbreviation for clock time hour, minute, second
# MD is an abbreviation for month, day
# see edzed.utils.timeinterval for details

_MAX_TRACKING_ERROR = 2.0   # max. acceptable scheduler's error in seconds, must be >= 1.0


@dataclass(frozen=True)
class TimeData:
    """Time in various represenations."""
    __slots__ = ['hms', 'tstruct', 'subsec']
    hms: ti.HMS
    tstruct: time.struct_time
    subsec: float


# hourly wake-ups for precise time tracking and early detection of DST changes
SET24 = frozenset(ti.HMS([hour, 0, 0]) for hour in range(24))


class Cron(addons.AddonMainTask, block.SBlock):
    """
    Simple cron service.

    Do not use directly in circuits. It has a form of an SBlock only
    to allow debug messages and monitoring through the event interface.
    """

    def __init__(self, *args, utc: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self._timefunc = time.gmtime if utc else time.localtime
        self._alarms: dict[ti.HMS, set[block.SBlock]] = {}
        self._queue: asyncio.Queue
        self._needs_reload = False

    def reload(self) -> None:
        """Reload the configuration after add_block/remove_block calls."""
        if self._needs_reload:
            if self._mtask is not None:
                self._queue.put_nowait(None)    # wake up the task, value does not matter
            self._needs_reload = False

    def add_block(self, hms: ti.HMS, blk: block.SBlock) -> None:
        """
        Add a block to be activated at given HMS.

        The block's 'recalc' method will be called at given time H:M:S
        and also when this service is started or reloaded.

        A TimeData object will be passed to the blk as its
        only argument.

        Don't forget to reload() after the last change.
        """
        if not hasattr(blk, 'recalc'):
            raise TypeError("{blk} is not compatible with the cron internal service")
        if not isinstance(hms, ti.HMS):
            raise TypeError(f"argument 'hms': expected an HMS object, got {hms!r}")
        if hms in self._alarms:
            self._alarms[hms].add(blk)
        else:
            self._alarms[hms] = {blk}
            if hms not in SET24:
                self._needs_reload = True

    def remove_block(self, hms: ti.HMS, blk: block.SBlock) -> None:
        """
        Remove a blk for given HMS if it was registered.

        Do nothing if a registration was not found.

        A reload after the last change is recommended, but not
        strictly necessary.
        """
        if hms not in self._alarms:
            return
        self._alarms[hms].discard(blk)
        if not self._alarms[hms]:
            del self._alarms[hms]
            if hms not in SET24:
                self._needs_reload = True

    def get_current_time(self) -> TimeData:
        """Return the current time/date."""
        now = time.time()
        tstruct = self._timefunc(now)
        return TimeData(
            hms=ti.HMS(tstruct),
            tstruct=tstruct,
            subsec=now % 1,     # don't want to import math just for the modf()
            )

    async def _maintask(self) -> NoReturn:
        """Recalculate registered blocks according to the schedule."""
        reset = False
        reload = True
        while True:
            # in outer loop:
            # - reset: DST begin/end or other computer clock related reason
            # - reload: self._alarms has changed
            now = self.get_current_time()
            if now.tstruct.tm_year < 2020:
                # this software did not exist back then
                raise RuntimeError("System clock is not set correctly.")
            if reset:
                for blk in set.union(*self._alarms.values()):    # all blocks
                    blk.recalc(now)     # type: ignore
            if reload:
                timetable = sorted(set.union(set(self._alarms), SET24))
                tlen = len(timetable)
            next_idx = bisect.bisect_left(timetable, now.hms)
            reset = reload = False
            while True:
                # in inner loop: cycle through the timetable; break out to the outer loop
                # for a reset if time tracking is not accurate or for reload
                if next_idx == tlen:
                    next_idx = 0
                next_hms = timetable[next_idx]
                self.log_debug("next wakeup at %s", next_hms)
                now = self.get_current_time()
                sleeptime = next_hms.seconds_from(now.hms) - now.subsec
                try:
                    await asyncio.wait_for(self._queue.get(), sleeptime)
                except asyncio.TimeoutError:
                    pass
                else:
                    reload = True
                    break
                now = self.get_current_time()
                if now.hms != next_hms:
                    # wrong time!
                    diff = now.hms.seconds_from(next_hms) + now.subsec
                    if diff > utils.SEC_PER_DAY / 2:
                        diff -= utils.SEC_PER_DAY
                    # diff > 0 = too late, diff < 0 = too early
                    reset = abs(diff) > _MAX_TRACKING_ERROR
                    self.log_warning(
                        "expected time: %s.000, current time: %s.%s, difference: %.3fs ",
                        next_hms, now.hms, format(now.subsec, '.3f')[2:], diff)
                    if reset:
                        self.log_warning("Resetting due to a time tracking error.")
                        break
                    if diff < 0.0:
                        # too early, everything should be fine after another sleep
                        continue
                if next_hms in self._alarms:
                    # recalc may alter the set we are iterating
                    for blk in list(self._alarms[next_hms]):
                        blk.recalc(now)     # type: ignore
                next_idx += 1

    def init_regular(self) -> None:
        self.set_output(None)

    def start(self) -> None:
        super().start()
        self._queue = asyncio.Queue()

    def _event_get_schedule(self, **_data) -> dict[str, list[str]]:
        """Return the internal scheduling data for debugging or monitoring."""
        return {
            str(hms): sorted(blk.name for blk in blkset)
            for hms, blkset in self._alarms.items()}

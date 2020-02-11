"""
Periodic events at fixed time/date.

Refer to the edzed documentation.
"""

import asyncio
import bisect
import collections
from dataclasses import dataclass
import logging
import time

from .. import addons
from .. import block
from .. import simulator
from ..utils import tconst
from ..utils import timeinterval

__all__ = ['TimeDate', 'TimeDateUTC']

_logger = logging.getLogger(__package__)


# HMS is an abbreviation for clock time hour:minute:second
# MD stands for month and day, i.e. a date within a year
# see edzed.utils.timeinterval for details

_MAX_TRACKING_ERROR = 2.0   # max. acceptable scheduler's error in seconds, must be >= 1.0


@dataclass(frozen=True)
class _TimeData:
    """Time in various represenations."""
    __slots__ = ['time', 'date', 'weekday', 'subsec']
    time: timeinterval.HMS
    date: timeinterval.MD
    weekday: int
    subsec: float


class _TimeDateBase(addons.AddonAsync, block.SBlock):
    """
    Base class for TimeDate and TimeDateUTC.
    """

    _scheduler_task = None

    # subclasses must define working timefunc
    @classmethod
    def timefunc(cls, ts):
        """Convert a UNIX timestamp to struct_time."""
        raise TypeError(f"{cls.__name__}.timefunc() not defined")

    def __init__(self, *args, times=None, dates=None, weekdays=None, **kwargs):
        self._times = None if times is None else timeinterval.TimeInterval(times)
        self._dates = None if dates is None else timeinterval.DateInterval(dates)
        self._weekdays = None if weekdays is None \
            else frozenset((int(x, base=8) + 6) % 7 for x in weekdays)
        super().__init__(*args, **kwargs)

    @classmethod
    def _get_current_time(cls) -> _TimeData:
        """Return the current time/date."""
        now = time.time()
        tstruct = cls.timefunc(now)
        return _TimeData(
            time=timeinterval.HMS(tstruct),
            date=timeinterval.MD(tstruct),
            subsec=now % 1,     # don't want to import math just for the modf()
            weekday=tstruct.tm_wday,
            )

    # pylint: disable=protected-access
    @classmethod
    async def _scheduler(cls):
        """Perform block updates according to the schedule."""
        alarms = collections.defaultdict(set)
        # populate with hourly wake-ups for precise time tracking
        # and early detection of DST changes
        for hour in range(24):
            alarms[timeinterval.HMS([hour, 0, 0])]  # pylint: disable=expression-not-assigned
        newday = timeinterval.HMS([0, 0, 0])
        for blk in simulator.get_circuit().getblocks(cls):
            if blk._times is not None:
                for hms in blk._times.range_starts():
                    alarms[hms].add(blk)
                for hms in blk._times.range_ends():
                    alarms[hms].add(blk)
            if blk._times is None or blk._dates is not None or blk._weekdays is not None:
                alarms[newday].add(blk)
        timetable = sorted(alarms)
        tlen = len(timetable)

        clsname = cls.__name__
        while True:
            # in outer loop = initialization or reset due to a DST begin/end
            # or other computer clock related reason
            now = cls._get_current_time()
            for blk in set.union(*alarms.values()):    # all instances
                blk._recalc(now)
            next_idx = bisect.bisect_right(timetable, now.time)
            while True:
                # in inner loop: cycle through the timetable; break out to the outer loop
                # for a reset if time tracking is not accurate
                if next_idx == tlen:
                    next_idx = 0
                next_hms = timetable[next_idx]
                _logger.debug("%s: next wakeup at %s", clsname, next_hms)
                await asyncio.sleep(next_hms.seconds_from(now.time) - now.subsec)
                now = cls._get_current_time()
                if now.time != next_hms:
                    # wrong time!
                    diff = now.time.seconds_from(next_hms) + now.subsec
                    if diff > tconst.SEC_PER_DAY / 2:
                        diff -= tconst.SEC_PER_DAY
                    # diff > 0 = too late, diff < 0 = too early
                    _logger.info(
                        "%s: expected time: %s.000, current time: %s.%s, difference: %.3fs ",
                        clsname, next_hms, now.time, format(now.subsec, '.3f')[2:], diff)
                    if abs(diff) > _MAX_TRACKING_ERROR:
                        _logger.warning("%s: Resetting due to a time tracking error.", clsname)
                        break
                    if diff < 0.0:
                        # too early, everything should be fine after another sleep
                        continue
                for blk in alarms[next_hms]:
                    blk._recalc(now)
                next_idx += 1

    def _recalc(self, now: _TimeData):
        """Update the output."""
        self.set_output(
            (self._times is None or now.time in self._times)
            and (self._dates is None or now.date in self._dates)
            and (self._weekdays is None or now.weekday in self._weekdays))

    def start(self):
        super().start()
        cls = type(self)
        if cls._scheduler_task is None:
            # The first block provides its wrapper to the scheduler
            # task which is common to all blocks of this type. Fatal
            # scheduler errors will be reported as belonging to this
            # first block. That might be little bit misleading, but
            # hopefully there will be no problems to report.
            cls._scheduler_task = asyncio.create_task(
                self._task_wrapper(cls._scheduler(), is_service=True))

    def stop(self):
        cls = type(self)
        if cls._scheduler_task is not None:
            # the first stopped block cancels the class-wide scheduler task
            cls._scheduler_task.cancel()
            cls._scheduler_task = None
        super().stop()


# Implementation note: do not further subclass the subclasses below,
# because each class manages all its instances (as recognized by
# isinstance()) and that includes also instances of subclasses.

class TimeDate(_TimeDateBase):
    """
    Block for periodic events at fixed local time/date.
    """

    timefunc = time.localtime


class TimeDateUTC(_TimeDateBase):
    """
    Block for periodic events at fixed UTC time/date.
    """

    timefunc = time.gmtime

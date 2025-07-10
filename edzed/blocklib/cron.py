"""
Call the .recalc() method of all registered blocks at given times of day.

Blocks acting on given time, date and weekdays are implemented
on top of this low-level service.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import asyncio
import bisect
import datetime as dt
import time
from typing import NoReturn

from .. import addons
from .. import block
from ..utils.tconst import SEC_PER_HOUR, SEC_PER_MIN, SEC_PER_DAY
from ..utils.flag import Flag

# time tracking accuracy (in seconds)
_TT_OK = 0.001          # desired accuracy
_TT_WARNING = 0.1       # log a warning when exceeded
_TT_ERROR = 2.5         # do a reset when exceeded

# hourly wake-ups for precise time tracking and early detection of DST changes
_SET24 = frozenset(dt.time(hour, 0, 0) for hour in range(24))


class Cron(addons.AddonMainTask, block.SBlock):
    """
    Simple cron service.

    Do not use directly in circuits. It has a form of an SBlock only
    to allow debug messages and monitoring through the event interface.
    """

    def __init__(self, *args, utc: bool, **kwargs):
        super().__init__(*args, **kwargs)
        self._utc = bool(utc)
        self._alarms: dict[dt.time, set[block.SBlock]] = {}
        self._queue: asyncio.Queue
        self._needs_reload_flag = Flag(False)

    def dtnow(self) -> dt.datetime:
        """Return the current date/time."""
        if self._utc:
            # dt.datetime.utcnow() is deprecated (Python 3.12),
            # but we need to keep all date/time object timezone naive
            # in order to make them mutually comparable
            #
            # dt.UTC (an alias for dt.timezone.utc) was introduced
            # in Python 3.11
            return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        return dt.datetime.now()

    def reload(self) -> None:
        """Reload the configuration after add_block/remove_block calls."""
        if self._needs_reload_flag.test_clear() and self._mtask is not None:
            self._queue.put_nowait(None)    # wake up the task, value does not matter

    def _check_tz(self, time_of_day: dt.time) -> dt.time:
        """
        Check if the time zone is left unspecified.

        Exception: in UTC mode accept the UTC zone, but remove it. (undocumented)
        """
        if not isinstance(time_of_day, dt.time):
            raise TypeError(
                f"time_of_day should be a datetime.time object, but got {time_of_day!r}")
        if time_of_day.tzinfo is None:
            return time_of_day
        if time_of_day.tzinfo == dt.timezone.utc and self._utc:
            # silently ignore
            return time_of_day.replace(tzinfo=None)
        raise ValueError("time_of_day must not contain timezone data")

    def add_block(self, time_of_day: dt.time, blk: block.SBlock) -> None:
        """
        Add a block to be activated at given time.

        The block's 'recalc' method will be called at given time
        and also when this service is started, reset or reloaded.

        A datetime.datetime object will be passed to the blk as its
        only argument.

        Don't forget to reload() cron after the last change.
        """
        if not hasattr(blk, 'recalc'):
            raise TypeError("{blk} is not compatible with the cron service")
        time_of_day = self._check_tz(time_of_day)
        if time_of_day in self._alarms:
            self._alarms[time_of_day].add(blk)
        else:
            self._alarms[time_of_day] = {blk}
            self._needs_reload_flag |= time_of_day not in _SET24

    def remove_block(self, time_of_day: dt.time, blk: block.SBlock) -> None:
        """
        Remove a blk for given time if it was registered.

        Do nothing if a registration was not found.

        A reload after the last change is recommended, but not
        strictly necessary.
        """
        time_of_day = self._check_tz(time_of_day)
        if time_of_day not in self._alarms:
            return
        self._alarms[time_of_day].discard(blk)
        if not self._alarms[time_of_day]:
            del self._alarms[time_of_day]
            self._needs_reload_flag |= time_of_day not in _SET24

    async def _maintask(self) -> NoReturn:
        """Recalculate registered blocks according to the schedule."""
        overhead = _TT_OK   # initial value, will be adjusted
                            # the sleeptime is reduced by this value
        reset_flag = Flag(False)
        reload_flag = Flag(True)  # reload will also initialize the index
        short_sleep = False       # alternative sleep function used => do not compute overhead
        while True:
            if reload_flag.test_clear():
                timetable = sorted(_SET24.union(self._alarms))
                tlen = len(timetable)
                self.log_debug("time schedule reloaded")
                index = None

            nowdt = self.dtnow()
            nowt = nowdt.time()
            if index is None:
                # reload is set before entering the loop -> "tlen" gets initialized
                # pylint: disable-next=possibly-used-before-assignment
                index = bisect.bisect_left(timetable, nowt) % tlen
            wakeup = timetable[index]
            self.log_debug("wakeup time: %s", wakeup)

            # sleep until the wakeup time:
            # step 0 - compute the delay until wakeup time
            #        - sleep
            # step 1 - check the current time, adjust overhead estimate,
            #            A: finish if the time is correct, or
            #            B: add a tiny sleep if woken up too early, because
            #               continuing before wakeup time is not acceptable
            #            C: do a reset if the time is way off
            # step 2 - check time after 1B,
            #            A: finish if the time is correct
            #            B: do a reset otherwise
            for step in range(3):
                # datetime.time does not support time arithmetic
                sleeptime = (SEC_PER_HOUR*(wakeup.hour - nowt.hour)
                    + SEC_PER_MIN*(wakeup.minute - nowt.minute)
                    + (wakeup.second - nowt.second)
                    + (wakeup.microsecond - nowt.microsecond)/ 1_000_000.0)
                if nowt.hour == 23 and wakeup.hour == 0:
                    # wrap around midnight (relying on hourly wakeups in SET24)
                    sleeptime += SEC_PER_DAY
                # sleeptime: negative = after the alarm time; positive = before the alarm time
                if step == 0:
                    self.log_debug("sleep until wakeup: %.3f sec", sleeptime)
                if step > 1 or sleeptime < 0:
                    diff = abs(sleeptime)
                    if self.debug:
                        self.log_debug(
                            "step %d, diff %.2f ms %s, estimated overhead: %.2f ms",
                            step, 1000*diff,
                            'EARLY' if sleeptime > 0 else 'late', 1000*overhead)
                    if diff > _TT_WARNING:
                        self.log_warning(
                            "expected time: %s, current time: %s, diff: %.2f ms.",
                            wakeup, nowt, 1000*diff)
                    if reset_flag.ior((step == 2 and sleeptime > 0) or diff > _TT_ERROR):
                        break
                    if step == 1 and not short_sleep and not -_TT_OK <= sleeptime <= 0:
                        overhead -= (sleeptime + _TT_OK/2) * 0.5    # average of new and old
                    if sleeptime <= 0:
                        break
                    if self.debug:
                        self.log_debug("additional sleep %.2f ms", 1000*sleeptime)

                if sleeptime == 0.0:
                    pass    # how likely is this?
                elif sleeptime <= _TT_OK/2:
                    short_sleep = True
                    # breaking the asyncio rules for max time tracking accuracy:
                    # doing a blocking sleep, but only for a fraction of a millisecond
                    time.sleep(sleeptime)
                elif sleeptime <= overhead:
                    short_sleep = True
                    await asyncio.sleep(sleeptime)
                else:
                    short_sleep = False
                    try:
                        await asyncio.wait_for(self._queue.get(), sleeptime - overhead)
                    except asyncio.TimeoutError:
                        pass
                    else:
                        reload_flag.set()
                        break
                nowdt = self.dtnow()
                nowt = nowdt.time()

            if reset_flag.test_clear():
                # DST begin/end or other computer clock related reason
                if (not self._utc
                        and nowdt.isoweekday() >= 6
                        and abs(diff - SEC_PER_HOUR) <= _TT_ERROR
                        ):
                    self.log_warning("Apparently a DST (summer time) clock change has occured.")
                self.log_warning("Reset_flagting due to a time tracking problem.")
                for blk in set.union(*self._alarms.values()):    # all blocks
                    assert hasattr(blk, 'recalc')
                    blk.recalc(nowdt)
                index = None
                continue
            if reload_flag:
                continue

            if wakeup in self._alarms:
                # .recalc() may alter the set we are iterating over
                for blk in list(self._alarms[wakeup]):
                    assert hasattr(blk, 'recalc')
                    blk.recalc(nowdt)
            index = (index + 1) % tlen

    def init_regular(self) -> None:
        self.set_output(None)

    def start(self) -> None:
        self._queue = asyncio.Queue()
        super().start()

    def _event_get_schedule(self, **_data) -> dict[str, list[str]]:
        """Return the internal scheduling data for debugging or monitoring."""
        return {
            str(time_of_day): sorted(blk.name for blk in blkset)
            for time_of_day, blkset in self._alarms.items()}

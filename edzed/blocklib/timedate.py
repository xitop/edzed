"""
Periodic events at fixed time/date.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from .. import addons
from .. import block
from .. import simulator
from . import cron
from . import timeinterval


__all__ = ['TimeDate', 'TimeSpan']


def _get_cron(utc):
    circuit = simulator.get_circuit()
    name = '_cron_utc' if utc else '_cron_local'
    try:
        return circuit.findblock(name)
    except KeyError:
        return cron.Cron(name, utc=utc, _reserved=True)


class TimeDate(addons.AddonPersistence, block.SBlock):
    """
    Block for periodic events at given time/date.
    """

    def __init__(self, *args, times=None, dates=None, weekdays=None, utc=False, **kwargs):
        self._cron = _get_cron(bool(utc))
        self._times = self._dates = self._weekdays = None
        # we build the initdef from times, dates, weekdays in order to simplify the usage
        if 'initdef' in kwargs:
            raise TypeError(
                f"'initdef' is an invalid keyword argument for {type(self).__name__}")
        initdef = self.parse(times, dates, weekdays)
        super().__init__(*args, initdef=initdef, **kwargs)

    @classmethod
    def parse(cls, times, dates, weekdays) -> dict:
        """Return the values in a normalized form."""
        return cls._export3(*cls._parse3(times, dates, weekdays))

    @staticmethod
    def _parse3(times, dates, weekdays):
        if times is not None:
            times = timeinterval.TimeInterval(times)
        if dates is not None:
            dates = timeinterval.DateInterval(dates)
        if weekdays is not None:
            if isinstance(weekdays, str):
                weekdays = [int(x) for x in weekdays if x != ' ']
            if not all(0 <= x <= 7 for x in weekdays):
                raise ValueError(
                    "Only numbers 0 or 7 (Sun), 1 (Mon), ... 6(Sat) are accepted as weekdays")
            weekdays = frozenset(0 if x == 7 else x for x in weekdays)
        return times, dates, weekdays

    @staticmethod
    def _export3(times, dates, weekdays):
        return {
            'times': None if times is None else times.as_list(),
            'dates': None if dates is None else dates.as_list(),
            'weekdays': None if weekdays is None else sorted(weekdays),
        }

    def get_state(self):
        return self._export3(self._times, self._dates, self._weekdays)

    def recalc(self, now: cron.TimeData):
        """Update the output."""
        tnone, dnone, wnone = self._times is None, self._dates is None, self._weekdays is None
        self.set_output(
            not (tnone and dnone and wnone)
            and (tnone or now.hms in self._times)
            and (dnone or timeinterval.MD(now.tstruct) in self._dates)
            # convert 0-6 (Mon-Sun) to 0-6 (Sun-Sat)
            and (wnone or (now.tstruct.tm_wday + 1) % 7 in self._weekdays))

    def _event_reconfig(self, *, times=None, dates=None, weekdays=None, **_data):
        """Reconfigure the block."""
        if self._times is not None:
            for hms in self._times.range_endpoints():
                self._cron.remove_block(hms, self)
        self._times, self._dates, self._weekdays = self._parse3(times, dates, weekdays)
        if self._times is not None:
            for hms in self._times.range_endpoints():
                self._cron.add_block(hms, self)
        # sometimes it is necessary, sometimes not, but it is easier
        # to always add 0:0:0 than to analyze the arguments
        self._cron.add_block(timeinterval.HMS([0, 0, 0]), self)
        self._cron.reload()
        self.recalc(self._cron.get_current_time())

    def init_from_value(self, value):
        self._event_reconfig(**value)

    _restore_state = init_from_value


class TimeSpan(addons.AddonPersistence, block.SBlock):
    """
    Block active between start and stop time/date.
    """

    def __init__(self, *args, span=(), utc=False, **kwargs):
        self._cron = _get_cron(bool(utc))
        self._span = timeinterval.DateTimeInterval(())
        # we build the initdef
        if 'initdef' in kwargs:
            raise TypeError(
                f"'initdef' is an invalid keyword argument for {type(self).__name__}")
        initdef = self.parse(span)
        super().__init__(*args, initdef=initdef, **kwargs)

    @classmethod
    def parse(cls, span) -> list:
        """Return the value in a normalized form."""
        return timeinterval.DateTimeInterval(span).as_list()

    def get_state(self):
        return self._span.as_list()

    def recalc(self, now: cron.TimeData):
        """Update the output."""
        self.set_output(timeinterval.YDT(now.tstruct) in self._span)

    def _event_reconfig(self, *, span=(), **_data):
        """Reconfigure the block."""
        for ydt in self._span.range_endpoints():
            self._cron.remove_block(timeinterval.HMS(ydt[3:6]), self)
        self._span = timeinterval.DateTimeInterval(span)
        now = self._cron.get_current_time()
        now_ymd = tuple(now.tstruct[0:3])
        for ydt in self._span.range_endpoints():
            if ydt[0:3] >= now_ymd:
                # future events only
                self._cron.add_block(timeinterval.HMS(ydt[3:6]), self)
        self._cron.reload()
        self.recalc(now)

    def init_from_value(self, value):
        self._event_reconfig(span=value)

    _restore_state = init_from_value

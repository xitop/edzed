"""
Periodic events at fixed time/date.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence, Set
from typing import cast, Optional

from .. import addons
from .. import block
from .. import simulator
from . import cron
from . import timeinterval as ti


__all__ = ['TimeDate', 'TimeSpan']


def _get_cron(utc: bool) -> cron.Cron:
    circuit = simulator.get_circuit()
    name = '_cron_utc' if utc else '_cron_local'
    try:
        return cast(cron.Cron, circuit.findblock(name))
    except KeyError:
        return cron.Cron(name, utc=utc, _reserved=True)


class TimeDate(addons.AddonPersistence, block.SBlock):
    """
    Block for periodic events at given time/date.
    """

    def __init__(
            self, *args,
            times: Optional[str|Sequence[Sequence[Sequence[int]]]] = None,
            dates: Optional[str|Sequence[Sequence[Sequence[int]]]] = None,
            weekdays: Optional[str|Sequence[int]] = None,
            utc: bool = False,
            **kwargs):
        self._cron = _get_cron(bool(utc))
        self._times: Optional[ti.TimeInterval] = None
        self._dates: Optional[ti.DateInterval] = None
        self._weekdays: Optional[Set[int]] = None
        # we build the initdef from times, dates, weekdays in order to simplify the usage
        if 'initdef' in kwargs:
            raise TypeError(
                f"'initdef' is an invalid keyword argument for {type(self).__name__}")
        initdef = self.parse(times, dates, weekdays)
        super().__init__(*args, initdef=initdef, **kwargs)

    @classmethod
    def parse(
            cls,
            times: Optional[str|Sequence[Sequence[Sequence[int]]]],
            dates: Optional[str|Sequence[Sequence[Sequence[int]]]],
            weekdays: Optional[str|Sequence[int]]
            ) -> dict[str, list|None]:
        """Return the values in a normalized form."""
        return cls._export3(*cls._parse3(times, dates, weekdays))

    @staticmethod
    def _parse3(
            times: Optional[str|Sequence[Sequence[Sequence[int]]]],
            dates: Optional[str|Sequence[Sequence[Sequence[int]]]],
            weekdays: Optional[str|Sequence[int]]
            ) -> tuple[
                    Optional[ti.TimeInterval],
                    Optional[ti.DateInterval],
                    Optional[frozenset[int]]
                    ]:
        ptimes = None if times is None else ti.TimeInterval(times)
        pdates = None if dates is None else ti.DateInterval(dates)
        if weekdays is None:
            pweekdays = None
        else:
            if isinstance(weekdays, str):
                weekdays = [int(x) for x in weekdays if x != ' ']
            if not all(0 <= x <= 7 for x in weekdays):
                raise ValueError(
                    "Only numbers 0 or 7 (Sun), 1 (Mon), ... 6(Sat) are accepted as weekdays")
            pweekdays = frozenset(0 if x == 7 else x for x in weekdays)
        return ptimes, pdates, pweekdays

    @staticmethod
    def _export3(
            times: Optional[ti.TimeInterval],
            dates: Optional[ti.DateInterval],
            weekdays: Optional[Iterable]
            ) -> dict[str, list|None]:
        return {
            'times': None if times is None else times.as_list(),
            'dates': None if dates is None else dates.as_list(),
            'weekdays': None if weekdays is None else sorted(weekdays),
        }

    def get_state(self) -> dict[str, list|None]:
        return self._export3(self._times, self._dates, self._weekdays)

    def _is_configured(self) -> bool:
        return any(cfg is not None for cfg in (self._times, self._dates, self._weekdays))

    def recalc(self, now: cron.TimeData) -> None:
        """Update the output."""
        self.set_output(
            self._is_configured()
            and (self._times is None or now.hms in self._times)
            and (self._dates is None or ti.MD(now.tstruct) in self._dates)
            # convert 0-6 (Mon-Sun) to 0-6 (Sun-Sat)
            and (self._weekdays is None or (now.tstruct.tm_wday + 1) % 7 in self._weekdays))

    def _event_reconfig(
            self, *,
            times: Optional[str|Sequence[Sequence[Sequence[int]]]] = None,
            dates: Optional[str|Sequence[Sequence[Sequence[int]]]] = None,
            weekdays: Optional[str|Sequence[int]] = None,
            **_data
            ) -> None:
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
        self._cron.add_block(ti.HMS([0, 0, 0]), self)
        self._cron.reload()
        self.recalc(self._cron.get_current_time())

    def init_from_value(self, value: Mapping[str, Sequence|None]) -> None:
        self._event_reconfig(**value)

    _restore_state = init_from_value


class TimeSpan(addons.AddonPersistence, block.SBlock):
    """
    Block active between start and stop time/date.
    """

    def __init__(
            self, *args,
            span: str|Sequence[Sequence[Sequence[int]]] = (),
            utc: bool = False,
            **kwargs):
        self._cron = _get_cron(bool(utc))
        self._span = ti.DateTimeInterval(())
        # we build the initdef
        if 'initdef' in kwargs:
            raise TypeError(
                f"'initdef' is an invalid keyword argument for {type(self).__name__}")
        initdef = self.parse(span)
        super().__init__(*args, initdef=initdef, **kwargs)

    @classmethod
    def parse(cls, span: str|Sequence[Sequence[Sequence[int]]]) -> list[list[list[int]]]:
        """Return the value in a normalized form."""
        return ti.DateTimeInterval(span).as_list()

    def get_state(self) -> list[list[list[int]]]:
        return self._span.as_list()

    def recalc(self, now: cron.TimeData) -> None:
        """Update the output."""
        self.set_output(ti.YDT(now.tstruct) in self._span)

    def _event_reconfig(
            self, *,
            span: str|Sequence[Sequence[Sequence[int]]] = (),
            **_data) -> None:
        """Reconfigure the block."""
        for ydt in self._span.range_endpoints():
            self._cron.remove_block(ti.HMS(ydt[3:6]), self)
        self._span = ti.DateTimeInterval(span)
        now = self._cron.get_current_time()
        now_ymd = tuple(now.tstruct[0:3])
        for ydt in self._span.range_endpoints():
            if ydt[0:3] >= now_ymd:
                # future events only
                self._cron.add_block(ti.HMS(ydt[3:6]), self)
        self._cron.reload()
        self.recalc(now)

    def init_from_value(self, value: Sequence[Sequence[Sequence[int]]]) -> None:
        self._event_reconfig(span=value)

    _restore_state = init_from_value

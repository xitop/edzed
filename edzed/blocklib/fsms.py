"""
FSM blocks for general use.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

from .. import fsm

__all__ = ['Timer']


class Timer(fsm.FSM):
    """
    A timer.
    """

    STATES = ('off', 'on')
    TIMERS = {
        'on': (fsm.INF_TIME, 'stop'),
        'off': (fsm.INF_TIME, 'start'),
        }
    EVENTS = (
        ('start', None, 'on'),
        ('stop', None, 'off'),
        ('toggle', 'on', 'off'),
        ('toggle', 'off', 'on'),
        )

    def __init__(self, *args, restartable: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._restartable = bool(restartable)

    def cond_start(self) -> bool:
        return self._restartable or self._state != 'on'

    def cond_stop(self) -> bool:
        return self._restartable or self._state != 'off'

    def calc_output(self) -> bool:
        return self._state == 'on'

"""
FSM blocks for general use.
"""

from .. import fsm

__all__ = ['Timer']


class Timer(fsm.FSM):
    """
    A timer.

    Output is True for time duration t_on, and False for duration t_off.

    By default both durations are infinite (timer disabled), i.e. the
    block is bistable. If one duration is set, the block is monostable.
    If both durations are set, the block is astable.

    See fsm.FSM for more information about durations.

    Arguments:
        restartable -- if restartable (default), a 'start' event
            occurring while in the 'on' state restarts the timer
            to measure the 't_on' time from the beginning. If not
            restartable, the timer will continue to measure the
            time and ignore the event. The same holds for the 'stop'
            event in the 'off' state.
        t_on -- 'on' state timer duration,
        t_off -- 'off' state timer duration,
        state='on' -- Start in the 'on' state (default is 'off')

    A conditional event 'start:stop' is often used for Timer control.
    See SBlock._event for description of how conditional events work.
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

    def __init__(self, *args, restartable=True, **kwargs):
        super().__init__(*args, **kwargs)
        self._restartable = bool(restartable)

    def cond_start(self):
        return self._restartable or self._state != 'on'

    def cond_stop(self):
        return self._restartable or self._state != 'off'

    def _eval(self):
        return self._state == 'on'

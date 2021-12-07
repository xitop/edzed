"""
Test the 'duration' event data item on FSMs.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio

import pytest

import edzed

from .utils import *


pytest_plugins = ('pytest_asyncio',)


@pytest.mark.asyncio
async def test_duration(circuit):
    """Test variable timer duration."""
    PERIOD = 0.040 # 40 ms = 25 Hz
    class PWM(edzed.FSM):
        STATES = ('off_0', 'on_0', 'off', 'on')
        TIMERS = {
            'on': (edzed.INF_TIME, 'stop'),
            'off': (edzed.INF_TIME, 'start'),
            }
        EVENTS = (
            ('start', None, 'on_0'),
            ('stop', None, 'off_0'),
            )
        def __init__(self, *args, dc=0.5, **kwargs):
            self._dc = dc   # duty cycle 0.0 < dc < 1.0
            super().__init__(*args, **kwargs)

        def _event_setdc(self, dc, **data):
            self._dc = dc

        def enter_on_0(self):
            self.event(edzed.Goto('on'), duration=self._dc * PERIOD)

        def enter_off_0(self):
            self.event(edzed.Goto('off'), duration=(1.0 - self._dc) * PERIOD)

        def calc_output(self):
            return self._state == 'on'

    logger = TimeLogger('logger', mstop=True)
    freq = PWM(
        'vclock', comment="25Hz variable duty cycle (pulse width modulation",
        initdef='on_0', on_output=edzed.Event(logger))

    async def tester():
        await asyncio.sleep(0.115)      # 3 periods 20:20 ms
        freq.event('setdc', dc=0.25)
        await asyncio.sleep(0.120)      # 3 periods 10:30
        freq.event('setdc', dc=1.0)
        await asyncio.sleep(0.115)      # 40:0 = permanetly on

    await edzed.run(tester())
    LOG = [
        # 20:20
        (0, True), (20, False),
        (40, True), (60, False),
        (80, True), (100, False),
        # 10:30
        (120, True), (130, False),
        (160, True), (170, False),
        (200, True), (210, False),
        # 40:0
        (240, True), # till stop, no output change for 'off' because duration is 0.0
        (350, '--stop--'),
        ]
    logger.compare(LOG)

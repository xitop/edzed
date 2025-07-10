"""
Test the Timer block.
"""

import asyncio

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit, fixture_task_factories
from .utils import init, TimeLogger

pytest_plugins = ('pytest_asyncio',)


def test_static(circuit):
    """Test states, events, output."""
    bis = edzed.Timer('timer')
    init(circuit)

    def trans(event, state):
        bis.event(event)
        assert bis.state == 'on' if state else 'off'
        assert bis.output is bool(state)

    assert bis.output is False
    trans('start', True)
    trans('stop', False)
    trans('stop', False)
    trans('toggle', True)
    trans('start', True)
    trans('start', True)
    trans('toggle', False)
    trans('toggle', True)
    trans('start', True)
    trans('toggle', False)
    trans('start', True)


@pytest.mark.asyncio
async def test_clock(circuit):
    """Test a trivial clock signal generator."""
    logger1 = TimeLogger('logger1')
    logger2 = TimeLogger('logger2')
    edzed.Timer('timer1', t_on=0.05, t_off=0.1, on_output=edzed.Event(logger1, 'log'))
    edzed.Timer('timer2', t_period=0.25, on_output=edzed.Event(logger2, 'log'))

    await edzed.run(asyncio.sleep(0.8))
    LOG1 = [
        (0,   False), (100, True),
        (150, False), (250, True),
        (300, False), (400, True),
        (450, False), (550, True),
        (600, False), (700, True),
        (750, False)]
    LOG2 = [
        (0,   False), (125, True),
        (250, False), (375, True),
        (500, False), (625, True),
        (750, False)]
    logger1.compare(LOG1)
    logger2.compare(LOG2)


@pytest.mark.asyncio
async def test_restartable(circuit):
    """Test restartable vs. not restartable."""
    rlogger = TimeLogger('rlogger')
    rmono = edzed.Timer(
        'rtimer', t_on=0.12, on_output=edzed.Event(rlogger, etype='log'))
    nlogger = TimeLogger('nlogger')
    nmono = edzed.Timer(
        'ntimer', t_on=0.12, on_output=edzed.Event(nlogger, etype='log'), restartable=False)

    async def tester():
        await asyncio.sleep(0.05)
        assert rmono.event('start')         # start OK
        assert nmono.event('start')         # start OK
        await asyncio.sleep(0.05)
        assert rmono.event('start')         # re-start OK
        assert not nmono.event('start')     # re-start not ok!
        await asyncio.sleep(0.1)
        assert rmono.event('start')         # re-start OK
        assert nmono.event('start')         # start OK
        await asyncio.sleep(0.05)
        rmono.event('start')
        nmono.event('start')
        await asyncio.sleep(0.25)

    await edzed.run(tester())

    RLOG = [
        (0, False),
        (50, True),
        (370, False),
        ]
    rlogger.compare(RLOG)
    NLOG = [
        (0, False),
        (50, True), (170, False),   # 120 ms
        (200, True), (320, False),  # 120 ms
        ]
    nlogger.compare(NLOG)


@pytest.mark.asyncio
async def test_duration(circuit):
    """Test variable timer duration."""
    logger = TimeLogger('logger')
    mono = edzed.Timer('timer', t_on=0.2, on_output=edzed.Event(logger, 'log'))

    async def tester():
        mono.event('start')
        await asyncio.sleep(0.25)
        mono.event('start', duration=0.05)
        await asyncio.sleep(0.1)
        mono.event('start', duration=None)
        await asyncio.sleep(0.25)

    await edzed.run(tester())
    LOG = [
        (0, False),
        (0, True), (200, False),    # 200 ms
        (250, True), (300, False),  # 50 ms
        (350, True), (550, False),  # 200 ms
        ]
    logger.compare(LOG)


@pytest.mark.asyncio
async def test_output(circuit):
    """Output is properly set when on_output is called."""
    def test_timer(value):
        assert value == timer.output
        assert timer.state == ('on' if value else 'off')

    testfunc = edzed.OutputFunc('testfunc', func=test_timer, on_error=None)
    timer = edzed.Timer('timer', on_output=edzed.Event(testfunc))

    async def tester():
        timer.event('start')
        timer.event('stop')
        timer.event('start')
        timer.event('stop')

    await edzed.run(tester())


@pytest.mark.asyncio
async def test_no_busy_loop(circuit):
    """Busy loop (zero period clock) is detected as chained events."""
    edzed.Timer('timer', t_on=0, t_off=0)

    with pytest.raises(edzed.EdzedCircuitError, match="infinite loop?"):
        await edzed.run()


def test_args(circuit):
    with pytest.raises(TypeError):
        edzed.Timer(None, t_on=1, t_period=1)
    with pytest.raises(TypeError):
        edzed.Timer(None, t_off=1, t_period=1)


def test_period(circuit):
    a = edzed.Timer('timer a', t_on=1, t_off=1)
    b = edzed.Timer('timer b', t_period='2s')

    # pylint: disable=protected-access
    assert a._duration == b._duration == {'on': 1.0, 'off': 1.0}

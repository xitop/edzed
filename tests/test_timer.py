"""
Test the Timer block.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio

import pytest

import edzed

from .utils import *


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
    timelimit(0.8, error=False)
    logger = TimeLogger('logger')
    clock = edzed.Timer('timer', t_on=0.05, t_off=0.1, on_output=edzed.Event(logger))

    try:
        await circuit.run_forever()
    except asyncio.CancelledError:
        pass
    LOG = [
        (0, False), (100, True),
        (150, False), (250, True),
        (300, False), (400, True),
        (450, False), (550, True),
        (600, False), (700, True),
        (750, False)]
    logger.compare(LOG)


@pytest.mark.asyncio
async def test_restartable(circuit):
    """Test restartable vs. not restartable."""
    rlogger = TimeLogger('rlogger')
    rmono = edzed.Timer('rtimer', t_on=0.12, on_output=edzed.Event(rlogger))
    nlogger = TimeLogger('nlogger')
    nmono = edzed.Timer('ntimer', t_on=0.12, on_output=edzed.Event(nlogger), restartable=False)

    asyncio.create_task(circuit.run_forever())
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
    await circuit.shutdown()

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
    mono = edzed.Timer('timer', t_on=0.2, on_output=edzed.Event(logger))

    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0.0)
    mono.event('start')
    await asyncio.sleep(0.25)
    mono.event('start', duration=0.05)
    await asyncio.sleep(0.1)
    mono.event('start', duration=None)
    await asyncio.sleep(0.25)
    await circuit.shutdown()
    LOG = [
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

    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0.0)
    timer.event('start')
    timer.event('stop')
    timer.event('start')
    timer.event('stop')
    await circuit.shutdown()


@pytest.mark.asyncio
async def test_no_busy_loop(circuit):
    """Busy loop (zero period clock) is detected as chained events."""
    timer = edzed.Timer('timer', t_on=0, t_off=0)

    with pytest.raises(edzed.EdzedCircuitError, match="infinite loop?"):
        await circuit.run_forever()

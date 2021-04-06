"""
Test the OutputAsync block.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio

import pytest

import edzed

from .utils import *


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def output_async(
        circuit, *,
        log, t1=0.1, test_error=False, mstop=True, on_error=None, **kwargs):
    async def worker(arg):
        logger.put(f'start {arg}')
        if test_error:
            # pylint: disable=pointless-statement
            1/0     # BOOM!
        await asyncio.sleep(0.12)
        logger.put(f'stop {arg}')
        return f'ok {arg}'

    try:
        inp = edzed.Input('inp', initdef='i1', on_output=edzed.Event('echo'))
        logger = TimeLogger('logger', mstop=mstop)
        edzed.OutputAsync('echo', coro=worker, on_error=on_error, **kwargs)
        asyncio.create_task(circuit.run_forever())
        await asyncio.sleep(t1)
        if circuit.is_ready():      # skip after an error,
            inp.put('iX')           # has an effect in qmode only
            inp.put('i2')
            await asyncio.sleep(0.05)
        await circuit.shutdown()
        logger.put("END")
    finally:
        logger.compare(log)


async def test_noqmode(circuit):
    LOG = [
        (0, 'start i1'),
        (100, 'cancel i1'), # on_cancel event
        (100, 'start i2'),  # i2 cancels i1
        (150, '--stop--'),
        (220, 'stop i2'),   # wait for i2
        (220, 'END')
        ]
    await output_async(
        circuit,
        log=LOG,
        on_cancel=edzed.Event(
            'logger',
            efilter=lambda data: {'value': f"cancel {data['arg']}"}),
        )


async def test_stop_timeout(circuit):
    LOG = [
        (0, 'start i1'),
        (100, 'start i2'),
        (150, '--stop--'),
        (190, 'END')        # timeout waiting for i2
        ]
    await output_async(circuit, stop_timeout=0.04, log=LOG)


async def test_queue_mode(circuit):
    LOG = [
        (0, 'start i1'),
        # 100, iX and i2 were put into the queue
        (120, 'stop i1'),
        (120, 'start iX'),
        (150, '--stop--'),
        (240, 'stop iX'),
        (240, 'start i2'),
        (360, 'stop i2'),
        (360, 'END')
        ]
    await output_async(circuit, qmode=True, log=LOG)


async def test_guard_time_noqueue(circuit):
    LOG = [
        (0, 'start i1'),
        # 100, i2 cancels i1, guard time begins
        (150, '--stop--'),
        (170, 'start i2'),  # i2 came before stop, it will be run
        (290, 'stop i2'),
        (360, 'END')
        ]
    await output_async(circuit, guard_time=0.07, log=LOG)


async def test_guard_time_queue(circuit):
    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (150, '--stop--'),
        (190, 'start iX'),  # 70 ms after last stop
        (310, 'stop iX'),
        (380, 'start i2'),  # 70 ms after last stop,
        (500, 'stop i2'),
        (570, 'END')
        ]
    await output_async(circuit, qmode=True, guard_time=0.07, log=LOG)


async def test_guard_time_after_error(circuit):
    """Guard time sleep is performed also after an error."""
    LOG = [
        (0, 'start i1'),
        (0, 'division by zero'),
        # 100, i2 was put into queue, but guard_time ends at t=130
        (130, 'start i2'),
        (130, 'division by zero'),
        (150, '--stop--'),
        (260, 'END')
        ]
    await output_async(
        circuit, test_error=True, guard_time=0.13, log=LOG,
        on_error=edzed.Event('logger', efilter=lambda data: {'value': str(data['error'])}))


async def test_guard_time_too_long(circuit):
    with pytest.raises(ValueError, match="not exceed"):
        edzed.OutputAsync(
            'not_OK', coro=asyncio.sleep, guard_time=1.5, stop_timeout=1.0, on_error=None)


async def test_on_success(circuit):
    def check_trigger(data):
        assert data['trigger'] == 'success'
        v = data['value']
        if v.startswith('ok'):
            assert v.endswith(data['arg'])
        return True

    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (120, 'ok i1'),     # on_success - coroutine return value
        (120, 'start iX'),
        (150, '--stop--'),
        (240, 'stop iX'),
        (240, 'ok iX'),
        (240, 'start i2'),
        (360, 'stop i2'),
        (360, 'ok i2'),    # on_success
        (360, 'END')
        ]
    await output_async(
        circuit, qmode=True,
        on_success=edzed.Event('logger', efilter=check_trigger),
        log=LOG)


async def test_on_error_ignore(circuit):
    LOG = [
        (0, 'start i1'),
        # (0, ??), <== error ignored
        (100, 'start i2'),
        # (100, ??), <== error ignored
        (150, '--stop--'),
        (150, 'END')
        ]
    await output_async(circuit, test_error=True, log=LOG)


async def test_on_error_abort(circuit):
    LOG = [
        (0, 'start i1'),
        (0, '--stop--'),
        ]
    with pytest.raises(edzed.EdzedError, match="error reported by 'echo': ZeroDivisionError"):
        await output_async(
            circuit, test_error=True, on_error=edzed.Event.abort(), log=LOG)


async def test_on_error_custom(circuit):
    """on_error=... overrides the default error handling."""
    def check_trigger(data):
        assert data['trigger'] == 'error'
        assert isinstance(data['error'], ZeroDivisionError)
        assert data['arg'] in {'i1', 'i2'}
        return True

    LOG = [
        (0, 'start i1'),
        (0, 'division by zero'),
        (100, 'start i2'),
        (100, 'division by zero'),
        (150, '--stop--'),
        (150, 'END')
        ]
    await output_async(
        circuit, test_error=True, log=LOG,
        on_error=edzed.Event('logger', efilter=(
            check_trigger,
            lambda data: {'value': str(data['error'])}
            )
        ))


async def test_stop(circuit):
    """Test the stop value."""
    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (150, 'start i2'),
        (200, 'start CLEANUP'),
        (320, 'stop CLEANUP'),
        (320, 'END')
        ]
    VLOG = [
        (120, 'ok i1'),
        (200, '--stop--'),
        ]

    vlog = TimeLogger('vlog', mstop=True)
    await output_async(
        circuit, stop_value='CLEANUP', log=LOG, t1=0.15,
        on_success=edzed.Event('vlog'), mstop=False)
    vlog.compare(VLOG)

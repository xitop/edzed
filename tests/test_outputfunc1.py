"""
Test the OutputFunc block.
Part 1/2 - async
"""

import asyncio

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit, fixture_task_factories
from .utils import TimeLogger


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def output_func(circuit, *, log, v2=2, on_error=None, mstop=True, **kwargs):
    def worker(arg):
        v = 12//arg
        logger.log(v)
        return 100+v

    inp = edzed.Input('inp', initdef=6, on_output=edzed.Event('echo'))
    logger = TimeLogger('logger', mstop=mstop)
    edzed.OutputFunc('echo', func=worker, on_error=on_error, **kwargs)

    async def tester():     # will be cancelled on simulation error
        inp_put = edzed.ExtEvent(inp).send
        await asyncio.sleep(0.05)
        inp_put(v2)
        await asyncio.sleep(0.05)
        inp_put(3)

    try:
        await edzed.run(tester())
        logger.log("END")
    finally:
        logger.compare(log)


async def test_basic(circuit):
    LOG = [
        (0, 2),
        (50, 6),
        (100, 4),
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(circuit, log=LOG)


async def test_on_success(circuit):
    def check_trigger(data):
        assert data['trigger'] == 'success'
        return True

    LOG = [
        (0, 2),
        (0, 102),
        (50, 6),
        (50, 106),      # on_success - function return value
        (100, 4),
        (100, 104),
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(
        circuit,
        on_success=edzed.Event('logger', etype='log', efilter=check_trigger),
        log=LOG)


async def test_on_error_ignore(circuit):
    LOG = [
        (0, 2),
        # (50, ??), <--- ignored exception
        (100, 4),
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(circuit, v2=0, log=LOG)


async def test_on_error_abort(circuit):
    LOG = [
        (0, 2),
        (50, '--stop--'),
        ]
    with pytest.raises(
            edzed.EdzedCircuitError, match="error reported by 'echo': ZeroDivisionError"):
        await output_func(circuit, v2=0, on_error=edzed.Event.abort(), log=LOG)


async def test_on_error_custom(circuit):
    def check_trigger(data):
        assert data['trigger'] == 'error'
        return True

    LOG = [
        (0, 2),
        (50, 'ZeroDivisionError'),
        (100, 4),   # error was handled, simulation continues
        (100, '--stop--'),
        (100, 'END')
        ]
    # now using type(exc).__name__ instead of str(exc)
    # n//0: Python <= 3.13: ZeroDivisionError: integer division or modulo by zero
    # n//0: Python >= 3.14: ZeroDivisionError: division by zero
    await output_func(
        circuit, v2=0, log=LOG,
        on_error=edzed.Event(
            'logger', 'log',
            efilter=(check_trigger, lambda data: {'value': type(data['error']).__name__})
            )
        )


async def test_stop(circuit):
    """Test the stop arguments."""
    LOG = [
        (0, 2),
        (50, 1),
        (100, 4),
        (100, '--stop--'),
        (100, 1),
        (100, 'END')
        ]
    VLOG = [
        (0, 102),
        (50, 101),
        (100, 104),
        (100, '--stop--'),
        (100, 101), # output event for stop_args
        ]
    vlog = TimeLogger('vlog', mstop=True)
    await output_func(
        circuit, v2=12, stop_data={"value": 12}, log=LOG,
        on_success=edzed.Event('vlog', 'log'))
    vlog.compare(VLOG)

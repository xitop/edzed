"""
Test the OutputFunc block.
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


async def output_func(circuit, *, log, v2=2, **kwargs):
    def worker(arg):
        v = 12//arg
        logger.put(v)
        return 100+v

    try:
        inp = edzed.Input('inp', initdef=6, on_output=edzed.Event('echo'))
        logger = TimeLogger('logger', mstop=True)
        edzed.OutputFunc('echo', func=worker, **kwargs)
        asyncio.create_task(circuit.run_forever())
        await asyncio.sleep(0.05)
        inp.put(v2)
        if circuit.is_ready():  # skip after an error,
            await asyncio.sleep(0.05)
            inp.put(3)
        await circuit.shutdown()
        logger.put("END")
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
    await output_func(circuit, on_success=edzed.Event('logger'), log=LOG)


async def Xtest_on_error_default(circuit):
    """An error (exception in the function) stops the simulation by default."""
    LOG = [
        (0, 2),
        (50, '--stop--'),
        ]
    with pytest.raises(edzed.EdzedError, match="error reported by 'echo': ZeroDivisionError"):
        await output_func(circuit, v2=0, log=LOG)


async def test_on_error(circuit):
    """on_error=... overrides the default error handling."""
    LOG = [
        (0, 2),
        (50, 'integer division or modulo by zero'),
        (100, 4),   # error was handled, simulation continues
        (100, '--stop--'),
        (100, 'END')
        ]
    await output_func(
        circuit, v2=0, log=LOG,
        on_error=edzed.Event('logger', efilter=lambda data: {'value': str(data['error'])}))


async def test_stop(circuit):
    """Test the stop value."""
    LOG = [
        (0, 2),
        (50, 6),
        (100, 4),
        (100, '--stop--'),
        (100, 1),
        (100, 'END')
        ]
    await output_func(circuit, stop_value=12, log=LOG)

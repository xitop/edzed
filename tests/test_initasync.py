"""
Test the InitAsync block.
"""

import asyncio

import pytest

import edzed

# pylint: disable-next=unused-import
from .utils import fixture_circuit, fixture_task_factories
from .utils import timelimit


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def sleep(t):
    await asyncio.sleep(t)
    return t


async def run_test1(circuit, expected, **init_kwargs):
    inp = edzed.Input('inp', initdef='x-inp')
    ainit = edzed.InitAsync('init', **init_kwargs, on_output=edzed.Event('inp'))
    timelimit(1, error=True)

    async def tester():
        await circuit.wait_init()
        assert ainit.output == expected[0]
        assert inp.output == expected[1]
    await edzed.run(tester())


async def test_init(circuit):
    """Test basic initialization."""
    await run_test1(circuit, (0.0, 0.0), init_coro=[sleep, 0.0])


async def test_timeout1(circuit):
    """Test timeout and default value in InitAsync."""
    await run_test1(
        circuit, ('x-init', 'x-init'),
        init_coro=[sleep, 5.0], init_timeout=0.05, initdef='x-init')


async def test_timeout2(circuit):
    """Test timeout and no default value in InitAsync."""
    await run_test1(circuit, (None, 'x-inp'), init_coro=[sleep, 5.0], init_timeout=0.05)


async def test_error1(circuit):
    """Test exception in coro and default value in InitAsync."""
    await run_test1(
        circuit, ('x-init', 'x-init'), init_coro=[sleep, 'bad', 'args'], initdef='x-init')


async def test_error2(circuit):
    """Test exception in coro and no default value in InitAsync."""
    await run_test1(circuit, (None, 'x-inp'), init_coro=[sleep, 'bad', 'args'])


async def run_test2(circuit, expected, flt):
    inp = edzed.Input('inp', initdef='x-inp')
    edzed.InitAsync(
        'init1', init_coro=[sleep, 0.0],
         on_output=edzed.Event('inp'))
    edzed.InitAsync(
        'init2', init_coro=[sleep, 0.1],
        on_output=edzed.Event('inp', efilter=edzed.IfNotIitialized(inp) if flt else None))
    timelimit(1, error=True)

    async def tester():
        await circuit.wait_init()
        assert inp.output == expected
    await edzed.run(tester())


async def test_filter1(circuit):
    """Test multiple inits without the IfNotIitialized filter."""
    await run_test2(circuit, 0.1, flt=False) # second value overwrites


async def test_filter2(circuit):
    """Test multiple inits with the IfNotIitialized filter."""
    await run_test2(circuit, 0.0, flt=True)  # second value filtered out

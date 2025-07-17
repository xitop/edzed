"""
Pytest fixtures.
"""

import asyncio
import gc

import pytest

import edzed
from .utils_gc import gc_exceptions


# using readable names, because they are displayed in the "pytest -v" output
_factories = ["regular-tasks"]
if hasattr(asyncio, "eager_task_factory"):
    _factories.append("eager-tasks")


@pytest.fixture(scope="module", params=_factories)
async def task_factories(request):
    """If supported, run tests twice: with eager tasks off and on."""
    if request.param == "eager-tasks":
        factory = asyncio.eager_task_factory
    elif request.param == "regular-tasks":
        factory = None
    else:
        raise ValueError("Unknown task factory name in the pytest fixture")
    asyncio.get_running_loop().set_task_factory(factory)


@pytest.fixture(name='circuit')
def fixture_circuit():
    """Return a new empty circuit."""
    edzed.reset_circuit()
    return edzed.get_circuit()


@pytest.fixture(scope='module', autouse=True)
def suppress_gc_during_tests():
    """Do not interfere with timing tests."""
    gc.disable()
    yield None
    gc_exceptions()
    gc.enable()
    gc.collect()

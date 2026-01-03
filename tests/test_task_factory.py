"""
Test the task_factory fixture.
"""

import asyncio

import pytest

import edzed

pytestmark = pytest.mark.usefixtures("task_factories")

@pytest.fixture(scope="module", name="memory")
def memory_fixture():
    storage = []
    yield storage
    assert storage == [False, True]

@pytest.mark.skipif(
    not hasattr(asyncio, "eager_task_factory"),
    reason="eager asyncio tasks not supported")
async def test_task_factory(memory):
    memory.append(edzed.simulator.tasks_are_eager())

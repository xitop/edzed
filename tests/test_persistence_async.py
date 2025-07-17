"""
Test the persistent state.
"""

# pylint: disable=missing-class-docstring, unused-argument

import time

import pytest

import edzed

from .utils import init

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_save_at_exit(circuit):
    """State is saved at exit regardless of sync_state."""
    storage = {}
    inp1 = edzed.Input('inp1', initdef=11, sync_state=False, persistent=True)
    inp2 = edzed.Input('inp2', initdef=22, sync_state=True, persistent=True)
    circuit.set_persistent_data(storage)
    await edzed.run(circuit.wait_init())

    assert inp1.output == 11
    assert inp2.output == 22
    assert storage[inp1.key] == 11
    assert storage[inp2.key] == 22

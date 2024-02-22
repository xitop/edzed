"""
Test the Repeat block.
Part 2/2: non-async
"""

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit

def test_no_eventcond(circuit):
    with pytest.raises(ValueError):
        edzed.Repeat(None, etype=edzed.EventCond(None, None), interval=1, dest='dummy')

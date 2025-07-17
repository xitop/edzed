"""
Test the Repeat block.
"""

# pylint: disable=unused-argument

import pytest

import edzed

def test_no_eventcond(circuit):
    with pytest.raises(ValueError):
        edzed.Repeat(None, etype=edzed.EventCond(None, None), interval=1, dest='dummy')

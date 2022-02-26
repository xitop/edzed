"""
Test the Repeat block.
Part 2/2: non-async
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *

def test_no_eventcond(circuit):
    with pytest.raises(ValueError):
        edzed.Repeat(None, etype=edzed.EventCond(None, None), interval=1, dest='dummy')

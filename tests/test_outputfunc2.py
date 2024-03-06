"""
Test the OutputFunc block.
Part 2/2 - non-async
"""

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit


def test_argument_checks(circuit):
    """Test f_args and f_kwargs validation."""
    for val in (None, 0, "string", edzed.UNDEF, {1:2}, {'xy'}, ["A", "B", 1], (True, False)):
        with pytest.raises(TypeError, match="f_args"):
            edzed.OutputFunc('err', func=lambda x: 0, on_error=None, f_args=val)
        with pytest.raises(TypeError, match="f_kwargs"):
            edzed.OutputFunc('err', func=lambda x: 0, on_error=None, f_kwargs=val)

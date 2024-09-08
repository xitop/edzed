"""
Test the reference cycle detection (EXPERIMENTAL)
"""

# xpylint: disable=missing-docstring, unused-variable

import gc

from .utils_gc import gc_exceptions

def _create_reference_cycle():
    try:
        1/0
    except Exception as err:
        localerr = err

def test_cycle_detection():
    _create_reference_cycle()
    assert gc_exceptions(quiet=True)
    gc.collect()
    assert not gc_exceptions()

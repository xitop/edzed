"""
Test the initial value aggregation.

Another test is: test_event_async:test_one_output_event
"""

# pylint: disable=missing-class-docstring

import edzed

from .utils import init

def test_no_double_processing(circuit):
    """
    Test that the output is not processed twice.

    During initialization is each new output value only stored.
    After all initialization steps is the last value copied
    to the output. It must not be processed again in "set_output".
    """
    class DoubleValue(edzed.Input):
        def set_output(self, value):
            super().set_output(2*value)

    double = DoubleValue(None, initdef=1)
    init(circuit)

    assert double.output == 2

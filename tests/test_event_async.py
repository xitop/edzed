"""
Test SBlock events and event filters.
"""

# pylint: disable=missing-class-docstring, unused-argument

import pytest

import edzed

pytestmark = pytest.mark.usefixtures("task_factories")


async def test_recipe(circuit):
    """Test the recipe from docs."""
    class ExtEventAuth(edzed.ExtEvent):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if not getattr(self.dest, 'x_input', False):
                raise ValueError(
                    f"Block {self.dest.name} is not accepting external inputs")

    inp_a = edzed.Input('inp_a', initdef=0, x_input=True)
    inp_b = edzed.Input('inp_b', initdef=1)

    async def tester():
        ExtEventAuth(inp_a, source='tester').send(value=6, wer='Steinscheißer Karl')
        assert inp_a.output == 6
        ExtEventAuth(inp_a).send(7)
        assert inp_a.output == 7
        with pytest.raises(ValueError):
            ExtEventAuth(inp_b)
        assert inp_b.output == 1

    await edzed.run(tester())


async def test_one_output_event(circuit):
    """Several initialization steps, but only one output event will be sent."""
    class Test(edzed.AddonPersistence, edzed.AddonAsync, edzed.SBlock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.inits = 0

        def _restore_state(self, state, /):
            self.set_output('P')  # Persistent
            self.inits += 1

        async def init_async(self):
            self.set_output('A')  # Async
            self.inits += 10

        def init_regular(self):
            self.set_output('R')  # Regular
            self.inits += 100

    class PutEventHistory(edzed.SBlock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.events = []

        def _event_put(self, *, value, previous, **_data):
            self.events.append((previous, value))

        def init_regular(self):
            self.set_output(None)

    hist = PutEventHistory('hist')
    source = Test('source', persistent=True, on_output=edzed.Event(hist))
    circuit.set_persistent_data({source.key: 1})
    await edzed.run(circuit.wait_init())

    assert source.inits == 1+10+100             # UNDEF -> P -> A -> R
    assert source.output == 'R'
    assert hist.events == [(edzed.UNDEF, 'R')]  # UNDEF -----------> R

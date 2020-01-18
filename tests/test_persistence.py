"""
Test the persistent state.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_keys(circuit):
    """Test keys under which the persistent data is stored."""
    assert edzed.Input('ipers').key == "<Input 'ipers'>"
    assert edzed.Timer('tpers').key == "<Timer 'tpers'>"


def test_save_state_sync(circuit):
    """By default the state is saved after each event (sync_state=True)."""
    storage = dict()
    inp = edzed.Input('ipers', initdef=99, persistent=True)
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp.output == 99
    assert storage == {inp.key: 99}
    inp.event('put', value=3.14)
    assert storage == {inp.key: 3.14}


def test_save_state_nosync(circuit):
    """Test with sync_state disabled."""
    storage = dict()
    inp = edzed.Input('ipers', initdef=99, sync_state=False, persistent=True)
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp.output == 99
    assert storage == {}
    inp.save_persistent_state()     # state must be saved explicitly
    assert storage == {inp.key: 99}
    inp.event('put', value=3.14)
    assert storage == {inp.key: 99}
    inp.save_persistent_state()
    assert storage == {inp.key: 3.14}


def test_load_state(circuit):
    """The saved state is loaded in preference to the default."""
    inp = edzed.Input('ipers', initdef=99, persistent=True)
    storage = {inp.key: 'saved'}
    circuit.set_persistent_data(storage)
    init(circuit)

    assert storage == {inp.key: 'saved'}
    assert inp.output == 'saved'
    inp.event('put', value=3.14)
    assert storage == {inp.key: 3.14}


# feature will be removed
def NO_test_no_output_event(circuit):
    """Loading persistent state does not generate an ouput event."""
    mem_p = EventMemory('mem_p')
    inp_p = edzed.Input('inp_p', persistent=True, on_output=edzed.Event(mem_p))
    mem_np = EventMemory('mem_np')
    inp_np = edzed.Input('inp_np', initdef=99, on_output=edzed.Event(mem_np))
    storage = {inp_p.key: 77}
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp_p.output == 77
    assert inp_np.output == 99

    assert mem_p.output is None
    assert mem_np.output == ('put', {'source': 'inp_np', 'previous': edzed.UNDEF, 'value': 99})

def test_no_save_on_error(circuit):
    """Event handling error disables saving of possibly incorrect state."""
    class InputE(edzed.Input):
        def _event_errput(self, *, value, err=False, **data):
            self.set_output(value)
            if err:
                raise RuntimeError('test error')

    inp = InputE('inp', persistent=True, initdef=0)
    storage = {}
    circuit.set_persistent_data(storage)
    init(circuit)

    assert storage[inp.key] == inp.output == 0
    inp.event('errput', value=44)
    assert storage[inp.key] == inp.output == 44
    assert circuit.is_ready()
    assert inp.persistent

    with pytest.raises(ValueError): # wrong usage
        inp.event('wrong')
    assert circuit.is_ready()       # harmless error, because the event handler was not called
    assert inp.persistent
    with pytest.raises(TypeError):  # again not an event handling error
        inp.event('errput')         # value missing
    assert circuit.is_ready()
    assert inp.persistent

    with pytest.raises(RuntimeError):   # but this is serious, an error raised in the handler
        inp.event('errput', value=7, err=True)
    assert not circuit.is_ready()   # simulation stopped
    assert not inp.persistent       # state tainted?, saving of state prevented
    assert inp.output == 7
    assert storage[inp.key] == 44

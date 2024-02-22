"""
Test the persistent state.
"""

# pylint: disable=missing-class-docstring

import time

import pytest

import edzed

# pylint: disable=unused-argument
# pylint: disable-next=unused-import
from .utils import fixture_circuit
from .utils import init


def test_keys(circuit):
    """Test keys identifying the persistent block data."""
    assert edzed.Input('ipers').key == "<Input 'ipers'>"
    assert edzed.Timer('tpers').key == "<Timer 'tpers'>"


def test_save_state_sync(circuit):
    """By default the state is saved after each event (sync_state=True)."""
    storage = {}
    inp = edzed.Input('ipers', initdef=99, persistent=True)
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp.output == 99
    assert storage == {inp.key: 99}
    inp.event('put', value=3.14)
    assert storage == {inp.key: 3.14}


def test_save_state_nosync(circuit):
    """Test with sync_state disabled."""
    storage = {}
    inp = edzed.Input('ipers', initdef=99, sync_state=False, persistent=True)
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp.output == 99
    assert not storage
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


def test_remove_unused(circuit):
    """
    Verify that unused keys are removed.

    All 'edzed-*' keys are reserved for internal use and are preserved.
    """
    inp = edzed.Input('ipers', initdef=1, persistent=True)
    storage = {inp.key: 2, 'wtf': 3, 'edzed-xyz': 4}
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp.output == 2
    assert storage == {inp.key: 2, 'edzed-xyz': 4}  # without the 'wtf' item


def test_expiration(circuit):
    """Test the internal state expiration"""
    inp1 = edzed.Input('inp1', initdef=91, persistent=True)
    inp2 = edzed.Input('inp2', initdef=92, persistent=True, expiration=None)
    inp3 = edzed.Input('inp3', initdef=93, persistent=True, expiration=10)
    inp4 = edzed.Input('inp4', initdef=94, persistent=True, expiration="1m30s")

    storage = {
        inp1.key: 1, inp2.key: 2, inp3.key: 3, inp4.key: 4,
        'edzed-stop-time': time.time() - 12.0,  # 12 seconds old
        }
    circuit.set_persistent_data(storage)
    init(circuit)

    assert inp1.output == 1     # no expiration
    assert inp2.output == 2     # no expiration
    assert inp3.output == 93    # state expired, init from default
    assert inp4.output == 4     # not expired


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

    with pytest.raises(edzed.EdzedUnknownEvent): # wrong usage
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
    assert not inp.persistent       # possibly tainted state -> saving of state prevented
    assert inp.output == 7
    assert storage[inp.key] == 44

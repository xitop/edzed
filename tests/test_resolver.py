"""
Test the name to block resolver.
"""

# pylint: disable=protected-access

import types

import pytest

import edzed

# pylint: disable-next=unused-import
from .utils import fixture_circuit


def test_resolver_basic(circuit):
    """Test the basic function."""
    tmr = edzed.Timer('tmr_name')

    resolver = circuit._resolver

    t = types.SimpleNamespace(a='tmr_name')
    circuit.resolve_name(t, 'a')
    assert len(resolver._unresolved) == 1
    resolver.resolve()
    assert len(resolver._unresolved) == 0
    assert t.a is tmr


def test_resolver_noop(circuit):
    """Only names need to be resolved."""
    tmr = edzed.Timer('tmr_name')

    t = types.SimpleNamespace(a=tmr)
    circuit.resolve_name(t, 'a')
    assert len(circuit._resolver._unresolved) == 0


def test_resolver_type_checking1(circuit):
    """Successful type check."""
    tmr = edzed.Timer('tmr_name')

    t = types.SimpleNamespace(a='tmr_name', b='tmr_name')
    circuit.resolve_name(t, 'a', edzed.SBlock)
    circuit.resolve_name(t, 'b', edzed.Timer)
    circuit._resolver.resolve()
    assert t.a is t.b is tmr


def test_resolver_type_checking2(circuit):
    """Unsuccessful type check."""
    edzed.Timer('tmr_name')

    t = types.SimpleNamespace(c='tmr_name')
    circuit.resolve_name(t, 'c', edzed.Input)
    with pytest.raises(TypeError, match='should be Input'):
        circuit._resolver.resolve()


def test_resolver_type_checking3(circuit):
    """Unsuccessful type check without resolving."""
    tmr = edzed.Timer(None)

    t = types.SimpleNamespace(c=tmr)
    with pytest.raises(TypeError, match='should be Counter'):
        circuit.resolve_name(t, 'c', edzed.Counter)


def test_resolver_block_not_found(circuit):
    """Block not found."""
    t = types.SimpleNamespace(d='ghost')
    circuit.resolve_name(t, 'd', object)
    with pytest.raises(Exception):  # actually a KeyError
        circuit._resolver.resolve()

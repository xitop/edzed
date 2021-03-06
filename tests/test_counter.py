"""
Test the Counter block.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import collections

import edzed

from .utils import *


def test_inc_dec(circuit):
    """Test the basic increment/decrement."""
    cnt = edzed.Counter('cnt')
    cnt100 = edzed.Counter('cnt_100', initdef=100)
    init(circuit)
    for i in range(5):
        assert cnt.output == i
        assert cnt100.output == 100+i
        cnt.event('inc')
        cnt100.event('inc')
    for i in reversed(range(5)):
        cnt.event('dec')
        cnt100.event('dec')
        assert cnt.output == i
        assert cnt100.output == 100+i


def test_amount_1(circuit):
    """Test variable amounts."""
    cnt = edzed.Counter('cnt')
    init(circuit)
    for i in range(10):
        # sum of first N odd numbers = N**2 (example: 1+3+5+7 = 16)
        assert cnt.output == i*i
        cnt.event('inc', amount=2*i + 1)


def test_amount_2(circuit):
    """Test variable amounts."""
    cnt = edzed.Counter('cnt', initdef=1)
    init(circuit)
    for i in range(16):
        cnt.event('inc', amount=cnt.output)
    assert cnt.output == 2**16
    for i in range(16):
        cnt.event('dec', amount=cnt.output//2)
    assert cnt.output == 1


def test_amount_3(circuit):
    """Test variable amounts."""
    cnt = edzed.Counter('cnt')
    init(circuit)
    for v in range(-10, 10, 1):
        cnt.event('inc', amount=v)
        cnt.event('dec', amount=v)
        assert cnt.output == 0


def test_put(circuit):
    """Test put events."""
    cnt = edzed.Counter('cnt')
    cnt11 = edzed.Counter('cnt_mod_11', modulo=11)
    init(circuit)

    for i in range(-300, +300, 7):
        cnt.put(i)
        assert cnt.output == i
        cnt11.put(i)
        assert cnt11.output == i % 11


def test_modulo_1(circuit):
    """Test modulo arithmetics."""
    MOD = 9
    ROUNDS = 15
    START = 4   # any integer 0 to MOD-1
    cycle = edzed.Counter('cnt_mod', modulo=MOD, initdef=START)
    init(circuit)

    values = collections.defaultdict(int)
    for i in range(MOD * ROUNDS):
        cycle.event('inc')
        values[cycle.output] += 1
    assert cycle.output == START
    assert set(values) == set(range(MOD))
    assert set(values.values()) == {ROUNDS}


def test_modulo_2(circuit):
    """Test modulo arithmetics."""
    cnt = edzed.Counter('cnt')
    cnt24 = edzed.Counter('cnt_mod_24', modulo=24)
    cnt37 = edzed.Counter('cnt_mod_37', modulo=37)
    init(circuit)

    for v in range(-200, +300, 7):
        cnt.event('inc', amount=v)
        cnt24.event('inc', amount=v)
        cnt37.event('dec', amount=-v)
    assert cnt.output % 24 == cnt24.output  # congruent mod 24
    assert cnt.output % 37 == cnt37.output  # congruent mod 37


def test_modulo_initdef(circuit):
    """Test modulo arithmetics on initial values."""
    cnt24 = edzed.Counter('cnt_mod_24', modulo=24, initdef=241)
    cnt37 = edzed.Counter('cnt_mod_37', modulo=37, initdef=-1)
    init(circuit)

    assert cnt24.output == 1
    assert cnt37.output == 36

"""
Test SBlock events and event filters.
"""

# pylint: disable=missing-docstring, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import pytest

import edzed

from .utils import *


def test_filter(circuit):
    """Test event filter."""
    def even_numbers_only(data):
        return data.get('value', 1) % 2 == 0

    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input('src', on_output=edzed.Event(dest, efilter=even_numbers_only), initdef=0)
    init(circuit)

    assert src.output == 0
    assert dest.output == 0
    src.put(1)
    assert src.output == 1
    assert dest.output == 0
    src.put(8)
    assert src.output == 8
    assert dest.output == 8
    src.put(33)
    assert src.output == 33
    assert dest.output == 8


def test_filter_pipe(circuit):
    """Test a pipe of event filters."""
    def new_X(data):
        return {'new': 'X', **data}
    def add_Y(data):
        return {**data, 'new': data['new'] + 'Y'}
    def add_Z(data):
        # modify in place
        data['new'] += 'Z'
        return data
    def add_qmark(data):
        return {**data, 'new': data['new'] + '?'}
    def del_previous(data):
        del data['previous']
        return data

    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            'dest',
            efilter=(new_X, add_Y, add_Z, add_qmark, add_qmark, del_previous)),
        initdef=None)
    dest = EventMemory('dest')
    init(circuit)

    src.put('V')
    assert dest.output == (
        'put', {'source': 'src', 'trigger': 'output', 'value': 'V', 'new': 'XYZ??'})


def test_dataedit_filter(circuit):
    """Test the DataEdit helper."""
    def check(expected):
        def _check(data):
            assert data == expected
            return data
        return _check

    CDATA = {'source': 'src', 'trigger': 'output'}
    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            'dest',
            efilter=(
                edzed.not_from_undef,
                check({**CDATA, 'previous': None, 'value': 'V'}),
                edzed.DataEdit.copy('value', 'saved'),
                check({**CDATA, 'previous': None, 'value': 'V', 'saved': 'V'}),
                edzed.DataEdit.add(a=1, b=2, c=3),
                check({
                    **CDATA,
                    'previous': None, 'value': 'V', 'saved': 'V', 'a': 1, 'b': 2, 'c': 3}),
                edzed.DataEdit.permit('source', 'saved', 'a'),
                check({'source': 'src', 'saved': 'V', 'a': 1}),
                edzed.DataEdit.copy('saved', 'value'),
                check({'source': 'src', 'saved': 'V', 'value': 'V', 'a': 1}),
                edzed.DataEdit.setdefault(saved='NO'),
                check({'source': 'src', 'saved': 'V', 'value': 'V', 'a': 1}),
                edzed.DataEdit.delete('saved'),
                check({'source': 'src', 'value': 'V', 'a': 1}),
                edzed.DataEdit.modify('a', lambda x: x+50),
                check({'source': 'src', 'value': 'V', 'a': 51}),
                edzed.DataEdit.setdefault(saved='YES'),
                check({'source': 'src', 'saved': 'YES', 'value': 'V', 'a': 51}),
                edzed.DataEdit.setdefault(saved='MAYBE'),
                check({'source': 'src', 'value': 'V', 'a': 51, 'saved': 'YES'}),
                edzed.DataEdit.modify('a', lambda a: edzed.DataEdit.DELETE if a == 52 else a+1),
                check({'source': 'src', 'value': 'V', 'a': 52, 'saved': 'YES'}),
                edzed.DataEdit.modify('a', lambda a: edzed.DataEdit.DELETE if a == 52 else a+1),
                check({'source': 'src', 'value': 'V', 'saved': 'YES'})
            )),
        initdef=None)
    dest = EventMemory('dest')
    init(circuit)

    src.put('V')
    assert dest.output == ('put', {'source': 'src', 'value': 'V', 'saved': 'YES'})


def test_chained_dataedit(circuit):
    """Chaining of event data edit functions is allowed."""
    def check(expected):
        def _check(data):
            assert data == expected
            return data
        return _check

    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            'dest',
            efilter=(
                edzed.not_from_undef,
                check({'source': 'src', 'trigger': 'output', 'previous': None, 'value': 'V'}),
                edzed.DataEdit \
                    .permit('source', 'trigger', 'value') \
                    .setdefault(source='fake') \
                    .copy('value', 'saved') \
                    .rename('source', 'src'),
                check(
                    {'src': 'src', 'trigger': 'output', 'saved': 'V', 'value': 'V'}),
                edzed.DataEdit.permit('trigger', 'src') \
                    .modify('src', lambda x: x[::-1]) \
                    .add(a=1)
            )),
        initdef=None)
    dest = EventMemory('dest')
    init(circuit)

    src.put('V')
    assert dest.output == ('put', {'a':1, 'src': 'crs', 'trigger': 'output'})

def test_dataedit_add_output(circuit):
    """Test add_output."""
    add = edzed.Input('add', initdef=12)
    dest = EventMemory('dest')
    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            dest, etype='ev',
            efilter=edzed.DataEdit.add_output('A', add).add_output('self', 'src'),
            ),
        initdef=3)
    init(circuit)

    CDATA = {'source': 'src', 'trigger': 'output'}
    src.put(4)
    assert dest.output[1] == {**CDATA, 'previous': 3, 'value': 4, 'self': 4, 'A': 12}
    add.put('old')
    add.put('new')
    src.put(5)
    assert dest.output[1] == {**CDATA, 'previous': 4, 'value': 5, 'self': 5, 'A': 'new'}
    src.put(6)
    assert dest.output[1] == {**CDATA, 'previous': 5, 'value': 6, 'self': 6, 'A': 'new'}


def test_dataedit_modify_reject(circuit):
    """Test event rejecting in DataEdit.modify."""
    dest = EventMemory('dest')
    src = edzed.Input(
        'src',
        on_output=edzed.Event(
            dest, etype='ev',
            efilter=edzed.DataEdit.modify(
                'value',
                lambda x: edzed.DataEdit.REJECT if x < 0 else x),
            ),
        initdef=3)
    init(circuit)

    CDATA = {'source': 'src', 'trigger': 'output'}
    src.put(911)
    after911 = {**CDATA, 'previous': 3, 'value': 911}
    assert dest.output[1] == after911
    src.put(-4)
    assert dest.output[1] == after911
    src.put(4)
    assert dest.output[1] == {**CDATA, 'previous': -4, 'value': 4}


def test_edge_detector_from_undef(circuit):
    """Test the edge detector's parameters u_rise, u_fall."""
    setup = []
    i = 0
    for value in (False, True):
        for ur in (False, True, None):
            for uf in (False, True):
                for r in (False, True):
                    dest = edzed.Input(f'test_event_{i}', initdef=None)
                    edzed.Input(
                        f"test_edge_{i}",
                        on_output=edzed.Event(
                            dest, efilter=edzed.Edge(rise=r, u_rise=ur, u_fall=uf)),
                        initdef=value
                        )
                    if ur is None:
                        ur = r
                    event = ur if value else uf
                    result = value if event else None
                    setup.append((dest, result, (value, ur, uf, r)))
                    i += 1
    init(circuit)
    for dest, result, args in setup:
        assert dest.output is result, f"failed for (value, u_rise, u_fall, rise) = {args}"


def test_edge_detector(circuit):
    """Test the edge detector's parameters rise and fall."""
    SEQ1 = (False, True, False, True, False, True, False, True)
    SEQ2 = (True, False, True, False, True)

    cnt = edzed.Counter('counter')
    i = 0
    setup = []
    for r in (False, True):
        for f in (False, True):
            inp1 = edzed.Input(
                f"test{i}_seq1",
                on_output=edzed.Event(cnt, 'inc', efilter=edzed.Edge(rise=r, fall=f)),
                initdef=SEQ1[0]
                )
            inp2 = edzed.Input(
                f"test{i}_seq2",
                on_output=edzed.Event(cnt, 'inc', efilter=edzed.Edge(rise=r, fall=f)),
                initdef=SEQ2[0]
                )
            s1 = s2 = 0     # s1, s2 = expected event count for SEQ1, SEQ2
            if r:
                s1 += 4     # 4 rising edges
                s2 += 2     # 3 rising edges, but 1 of them is initial
                            # and is counted immediately at the block creation
            if f:
                s1 += 3     # 4 falling edges, but 1 of them is initial
                            # and is suppressed by uf=False (default)
                s2 += 2     # 2 falling edges
            setup.append((inp1, SEQ1, s1, (r, f)))
            setup.append((inp2, SEQ2, s2, (r, f)))
            i += 1
    init(circuit)
    assert cnt.output == 2  # 2 times the initial rising edge of S2R1F10 and S2R1F1

    for inp, seq, result, args in setup:
        cnt.put(0)
        assert cnt.output == 0
        for val in seq:
            inp.put(val)
        assert cnt.output == result, f"failed for {inp.name}, (rise, fall) = {args}"


def test_not_from_undef(circuit):
    """Test the not_from_undef filter."""
    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input(
        'src',
        on_output=edzed.Event(dest, efilter=edzed.not_from_undef),
        initdef=1)
    init(circuit)

    assert src.output == 1
    assert dest.output is None  # UNDEF -> 1 suppressed by the filter
    src.put(3)
    assert src.output == 3
    assert dest.output == 3
    src.put(5)
    assert src.output == 5
    assert dest.output == 5


def test_delta(circuit):
    """Test the Delta filter."""
    trace = []
    def tee(data):
        trace.append(data['value'])
        return data

    dest = edzed.Input('dest', initdef=None)
    src = edzed.Input(
        'src',
        on_output=edzed.Event(dest, efilter=[edzed.Delta(1.7), tee]),
        initdef=0)
    init(circuit)

    for num in (0, 1, 0, 2, 3.69, 3.71, 5, 6, 7, 8, 15, 13.5, 16.5, 12):
        src.put(num)
    assert trace == [0, 2, 3.71, 6, 8, 15, 12]
    assert dest.output == 12


def test_ifoutput(circuit):
    """Test the IfOutput."""

    enable = edzed.Input('enable', initdef='truthy')
    cnt = edzed.Counter('cnt')
    cnt2 = edzed.Counter('cnt2')
    increment = edzed.Event('cnt', 'inc', efilter=edzed.IfOutput(enable))
    increment2 = edzed.Event('cnt2', 'inc', efilter=edzed.IfOutput('_not_enable'))
    src = Noop('src', comment='faked event source')

    init(circuit)
    inv = circuit.findblock('_not_enable')

    assert cnt.output == cnt2.output == 0

    assert increment.send(src)
    assert cnt.output == 1
    assert not increment2.send(src)
    assert cnt2.output == 0

    assert increment.send(src)
    assert cnt.output == 2
    assert not increment2.send(src)
    assert cnt2.output == 0

    enable.put(False)
    inv.eval_block()
    assert not increment.send(src)
    assert cnt.output == 2
    assert increment2.send(src)
    assert cnt2.output == 1
    enable.put(0)
    inv.eval_block()
    assert not increment.send(src)
    assert cnt.output == 2
    assert increment2.send(src)
    assert cnt2.output == 2
    enable.put(1)
    inv.eval_block()
    assert increment.send(src)
    assert cnt.output == 3
    assert not increment2.send(src)
    assert cnt2.output == 2

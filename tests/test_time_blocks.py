"""
Test the TimeDate, Timer, TimeSpan blocks.
"""

# pylint: disable=unused-argument

import pytest

import edzed

from .utils import init

def test_timedate_no_initdef(circuit):
    with pytest.raises(TypeError):
        edzed.TimeDate(None, initdef={})


def test_timedate_parse():
    parse = edzed.TimeDate.parse
    assert parse(None, None, None) == {'times': None, 'dates': None, 'weekdays': None}
    assert parse("17:0:30-18:14", "Nov30", "134") == {
        'times': [[[17,0,30,0], [18,14,0,0]]],
        'dates': [[[11,30], [11,30]]],
        'weekdays': [1,3,4]
        }


def test_timer_static(circuit):
    """Test states, events, output."""
    bis = edzed.Timer('timer')
    init(circuit)

    def trans(event, state):
        bis.event(event)
        assert bis.state == 'on' if state else 'off'
        assert bis.output is bool(state)

    assert bis.output is False
    trans('start', True)
    trans('stop', False)
    trans('stop', False)
    trans('toggle', True)
    trans('start', True)
    trans('start', True)
    trans('toggle', False)
    trans('toggle', True)
    trans('start', True)
    trans('toggle', False)
    trans('start', True)


def test_timer_args(circuit):
    with pytest.raises(TypeError):
        edzed.Timer(None, t_on=1, t_period=1)
    with pytest.raises(TypeError):
        edzed.Timer(None, t_off=1, t_period=1)


def test_timer_period(circuit):
    a = edzed.Timer('timer a', t_on=1, t_off=1)
    b = edzed.Timer('timer b', t_period='2s')

    # pylint: disable=protected-access
    assert a._duration == b._duration == {'on': 1.0, 'off': 1.0}


def test_timespan_parse():
    parse = edzed.TimeSpan.parse
    assert parse('') == []
    assert (
        parse("2001 August 31. 1:2:3.400-31.may 2008 1:59")
        == parse("2001-08-31 1:2:3.400 - 2008-05-31 01:59:0")
        == parse("2001-08-31 1:2:3,400 - 2008-05-31 01:59:0,0;")
        == parse("1:2:3.400 2001 August 31./31.may 2008 1:59")
        == [[[2001,8,31,1,2,3,400_000], [2008,5,31,1,59,0,0]]])

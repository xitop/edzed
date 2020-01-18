"""
Event filters.
"""

import logging

from .. import block


__all__ = ['not_from_undef', 'Edge', 'Delta', 'DataEdit']

_logger = logging.getLogger(__package__)


def not_from_undef(data):
    """Filter out the initial change from UNDEF to the first real value."""
    return None if data.get('previous', block.UNDEF) is block.UNDEF else data


class Edge:
    """
    Event filter for logical values.

    IMPORTANT: This filter is designed to work with 'on_output' events.
    It requires items 'previous' and 'value' to be present in the event
    data.

    An Edge filter compares logical levels (i.e. boolean values)
    of previous and current value and passes through only explicitly
    allowed combinations. These changes are often called the rising
    and the falling edge in logical circuits, hence the name.

    Parameters:
        rise -- allow: False -> True
        fall -- allow: True -> False
        u_rise -- allow: UNDEF -> True (default: same as rise)
        u_fall -- allow: UNDEF -> False

    Note: UNDEF has False boolean value. That's why rise includes
    UNDEF -> True. If this is not desired, use rise=True, u_rise=False
    to filter it out.
    """
    def __init__(self, rise=False, fall=False, u_rise=None, u_fall=False):
        self._rise = bool(rise)
        self._fall = bool(fall)
        self._urise = bool(u_rise) if u_rise is not None else self._rise
        self._ufall = bool(u_fall)
        if not (rise or fall or u_rise or u_fall):
            _logger.warning(
                "%s: all events will be filtered out!",
                type(self).__name__)

    def __call__(self, data):
        value = data['value']
        previous = data['previous']
        if previous is block.UNDEF:
            if self._urise if value else self._ufall:
                return data
        else:
            previous = bool(previous)
            if (not previous and self._rise) if value else (previous and self._fall):
                return data
        return None


class Delta:
    """
    Event filter for numeric values.

    Compare the last accepted data value with the current value.
    If the difference is smaller than 'delta', filter out the
    data value.
    """
    def __init__(self, delta):
        self._delta = delta
        self._last = block.UNDEF

    def __call__(self, data):
        value = data['value']
        if self._last is block.UNDEF or abs(self._last - value) >= self._delta:
            self._last = value
            return data
        return None


class DataEdit:
    """
    Modify the event data.

    DataEdit accepts all events.
    """
    def __init__(self, func):
        self._func = func

    @classmethod
    def add(cls, **kwargs):
        """Add key=value pairs. Existing values wil be overwritten."""
        return cls(lambda data: {**data, **kwargs})

    @classmethod
    def default(cls, **kwargs):
        """Add key=value pairs only if key is missing."""
        return cls(lambda data: {**kwargs, **data})

    @classmethod
    def delete(cls, *args):
        """Delete listed keys. Non-existing keys are ignored."""
        def _edit(data):
            for key in args:
                data.pop(key, None)
            return data
        return cls(_edit)

    @classmethod
    def delete_except(cls, *args):
        """Delete all but listed keys."""
        def _edit(data):
            for key in list(data):
                if key not in args:
                    del data[key]
            return data
        return cls(_edit)

    @classmethod
    def copy(cls, src, dst):
        """Copy data[src] to data[dst]."""
        def _edit(data):
            data[dst] = data[src]
            return data
        return cls(_edit)

    def __call__(self, data):
        return self._func(data)

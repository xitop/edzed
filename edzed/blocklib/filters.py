"""
Event filters.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import logging

from .. import block


__all__ = ['not_from_undef', 'Edge', 'Delta', 'DataEdit']

_logger = logging.getLogger(__package__)


def not_from_undef(data):
    """Filter out the initial change from UNDEF to the first real value."""
    return data.get('previous', block.UNDEF) is not block.UNDEF


class Edge:
    """
    Event filter for logical values.
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
                return True
        else:
            previous = bool(previous)
            if (not previous and self._rise) if value else (previous and self._fall):
                return True
        return False


class Delta:
    """
    Event filter for numeric values.
    """

    def __init__(self, delta):
        self._delta = delta
        self._last = block.UNDEF

    def __call__(self, data):
        value = data['value']
        if self._last is block.UNDEF or abs(self._last - value) >= self._delta:
            self._last = value
            return True
        return False


class DataEdit:
    """
    Modify the event data.
    """

    def __init__(self, func):
        self._func = func

    def __getattribute__(self, name):
        """
        Disallow chaining of edit functions.

        Without this check, expressions similar to this one:
            DataEdit.add(key1).delete(key2)
        would be valid code, but wouldn't work as expected. Only the
        last operation will be performed. We better disallow this
        type of usage entirely.
        """
        attr = super().__getattribute__(name)   # raises if attr not found
        if not name.startswith('_'):
            # hide the filter functions in instances, the class must be the only source
            raise AttributeError(
                f"'{type(self).__name__}' object does not allow access to attribute '{name}'")
        return attr

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
    def permit(cls, *args):
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

    REJECT = object()

    @classmethod
    def modify(cls, key, func):
        """Apply the func to a value identified by key."""
        def _edit(data):
            current = data[key]
            replacement = func(current)
            if replacement is cls.REJECT:
                return None
            data[key] = replacement
            return data
        return cls(_edit)

    def __call__(self, data):
        return self._func(data)

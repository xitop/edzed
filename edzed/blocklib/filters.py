"""
Event filters.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import logging
import types

from .. import block
from .. import simulator


__all__ = ['not_from_undef', 'Edge', 'Delta', 'DataEdit', 'IfOutput', 'IfNotIitialized']

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


class IfOutput:
    """
    Enable/disable events depending on block's output.
    """

    def __init__(self, control_block: [str, block.Block]):
        self._ctrl_blk = control_block
        simulator.get_circuit().resolve_name(self, '_ctrl_blk')

    def __call__(self, data):
        return data if self._ctrl_blk.output else None


class IfNotIitialized:
    """
    Enable/disable events depending on block's init state.
    """

    def __init__(self, control_block: [str, block.SBlock]):
        self._ctrl_blk = control_block
        simulator.get_circuit().resolve_name(self, '_ctrl_blk', block_type=block.SBlock)

    def __call__(self, data):
        return None if self._ctrl_blk.is_initialized() else data


class dualmethod(classmethod):
    """
    Dual (class/instance) method decorator.

    When the decorated method is called as a class method,
    create an instance on the fly.

    When called as an instance method, proceed normally,
    i.e. as if not decorated.
    """

    def __get__(self, instance, cls):
        if instance is None:
            instance = cls()
        return self.__func__.__get__(instance, cls)


class DataEdit:
    """
    Modify the event data.

    Methods may be chained.
    """

    def __init__(self):
        self._editlist = []

    # @dualmethod confuses pylint a little
    # pylint: disable=bad-classmethod-argument, no-member
    @dualmethod
    def add(self, **kwargs):
        """Add key=value pairs. Existing values will be overwritten."""
        self._editlist.append(lambda data: {**data, **kwargs})
        return self

    @dualmethod
    def add_output(self, key, source):
        """Add key=block's output. Existing value will be overwritten."""
        # cannot store the 'source' as an instance attribute, because
        # next 'add_output' call would overwrite it. In order to prevent
        # that a separate container must be created each time.
        src = types.SimpleNamespace(block=source)
        simulator.get_circuit().resolve_name(src, 'block')
        self._editlist.append(lambda data: {**data, key: src.block.output})
        return self

    @dualmethod
    def copy(self, src, dst):
        """Copy data[src] to data[dst]."""
        def _edit(data):
            data[dst] = data[src]
            return data
        self._editlist.append(_edit)
        return self

    @dualmethod
    def delete(self, *args):
        """Delete listed keys. Non-existing keys are ignored."""
        def _edit(data):
            for key in args:
                data.pop(key, None)
            return data
        self._editlist.append(_edit)
        return self

    DELETE = object()
    REJECT = object()

    @dualmethod
    def modify(self, key, func):
        """Apply the func to a value identified by key."""
        def _edit(data):
            current = data[key]
            replacement = func(current)
            if replacement is self.REJECT:
                return None
            if replacement is self.DELETE:
                del data[key]
            else:
                data[key] = replacement
            return data
        self._editlist.append(_edit)
        return self

    @dualmethod
    def permit(self, *args):
        """Delete all but listed keys."""
        def _edit(data):
            for key in list(data):
                if key not in args:
                    del data[key]
            return data
        self._editlist.append(_edit)
        return self

    @dualmethod
    def rename(self, src, dst):
        """Rename key: data[src] -> data[dst]."""
        def _edit(data):
            data[dst] = data[src]
            del data[src]
            return data
        self._editlist.append(_edit)
        return self

    @dualmethod
    def setdefault(self, **kwargs):
        """Add key=value pairs only if key is missing."""
        self._editlist.append(lambda data: {**kwargs, **data})
        return self

    def __call__(self, data):
        for func in self._editlist:
            data = func(data)
            if not isinstance(data, dict):
                break
        return data

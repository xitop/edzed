"""
Circuit blocks.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Project home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import abc
from collections.abc import (
    Callable, Coroutine, Iterator, Mapping, MutableMapping, Sequence, Set)
import dataclasses as dc
import difflib
import enum
import logging
import sys
from typing import Any, ClassVar, Final, Optional, overload, TypeVar, Union
import warnings
import weakref

from .exceptions import EdzedCircuitError, EdzedInvalidState, EdzedUnknownEvent


__all__ = [
    'UNDEF', 'Const', 'Block', 'CBlock', 'SBlock',
    'Event', 'ExtEvent', 'EventType', 'EventCond', 'event_tuple', 'check_name',
    ]

P3_10 = sys.version_info >= (3, 10)

_logger = logging.getLogger(__package__)


# See PEP 484 - Support for singleton types in unions
class _UndefType(enum.Enum):
    UNDEF = None

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return '<UNDEF>'

    def __str__(self) -> str:
        return '<UNDEF>'


# Uninitialized circuit block's output or state value
UNDEF: Final = _UndefType.UNDEF


class Const:
    """
    A constant value to be fed into a circuit block's input.

    Unlike other blocks, Const blocks are not subclassed from the Block
    base class and they are not stored in a Circuit object. They appear
    only as inputs of other blocks.

    Public attributes for compatibility with other blocks:
        name -- automatically created from the value
        output -- constant value
    """

    __slots__ = ('_output', '__weakref__')
    _instances: MutableMapping[Any, Const] = weakref.WeakValueDictionary()

    def __new__(cls, const: Any) -> Const:
        try:
            return cls._instances[const]
            # __init__ will be invoked anyway
        except KeyError:
            hashable = True
        except TypeError:
            hashable = False
        new = super().__new__(cls)
        if hashable:
            cls._instances[const] = new
        return new

    def __init__(self, const: Any) -> None:
        if const is UNDEF:
            raise ValueError("<UNDEF> is not a valid value.")
        self._output = const

    @property
    def output(self) -> Any:
        return self._output

    @property
    def name(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"<{type(self).__name__} {self.output!r}>"


def check_name(name: Any, nametype: str) -> None:
    """Raise if name is not valid."""
    if not isinstance(name, str):
        raise TypeError(f"{nametype} must be a string, but got {name!r}")
    if not name:
        raise ValueError(f"{nametype} must be a non-empty string")


def _is_multiple(arg: Any) -> bool:
    """
    Check if arg specifies multiple ordered items (inputs, events, etc.)

    The check is based on the type. The actual item count does not
    matter and can be any value including zero or one.

    Iterators are also considered to be multiple items with defined
    order, but their use is discouraged, because they can be iterated
    over only once.

    The str type arg is considered as a single name and not as a string
    of multiple characters; the return value is False.

    A set is unordered and thus not recognized as multiple items by
    this function; the return value is False.

    """
    if isinstance(arg, Iterator):
        warnings.warn(
            "Specifying multiple events, event filters or inputs with an iterator "
            + "is deprecated. Use a tuple or a list instead.",
            DeprecationWarning,
            stacklevel=2)
        return True
    return not isinstance(arg, str) and isinstance(arg, Sequence)


_T_zero_or_more = TypeVar("_T_zero_or_more")
# using Union, because T1|T2 is not supported in Python 3.9
zero_or_more = Optional[Union[_T_zero_or_more, Sequence[_T_zero_or_more]]]


class Block:
    """
    Base class for a circuit building block.
    """

    def __init__(
            self,
            name: Optional[str],
            *,
            comment: str = "",
            on_output: zero_or_more[Event] = None,
            _reserved: bool = False,
            debug: bool = False,
            **x_kwargs) -> None:
        """Create new block. Add it to the circuit."""
        self.circuit = simulator.get_circuit()
        if name is None:
            # automatically assign name _TYPE_0, _TYPE_1, _TYPE_2, ...
            prefix = f"_{type(self).__name__}_"
            cnt = sum(
                1 for blk in self.circuit.getblocks(type(self))
                if blk.name.startswith(prefix))
            name = prefix + str(cnt)
        else:
            check_name(name, "block name")
            if name.startswith('_') and not _reserved:
                raise ValueError(f"{name!r} is a reserved name (starting with an underscore")
        self.name: str = name
        is_cblock = isinstance(self, CBlock)
        is_sblock = isinstance(self, SBlock)
        if not is_sblock and not is_cblock:
            raise TypeError("Can't instantiate abstract Block class")
        if is_sblock and is_cblock:
            raise TypeError("A block cannot be both sequential and combinational")
        for key, value in x_kwargs.items():
            if not key.startswith('x_') and not key.startswith('X_'):
                raise TypeError(
                    f"'{key}' is an invalid keyword argument for {type(self).__name__}()")
            setattr(self, key, value)
        self.comment = comment
        self.debug = bool(debug)
        self._output_events = event_tuple(on_output)
        # oconnections will be populated by Circuit._finalize():
        self.oconnections: set[CBlock] = set()  # output is connected to these blocks
        self._output: Any = UNDEF
        self.circuit.addblock(self)

    def is_initialized(self) -> bool:
        """Return True if the output has been initialized."""
        return self._output is not UNDEF

    @property
    def output(self) -> Any:
        """Read-only access to the output value."""
        return self._output

    def log_msg(self, msg: str, *args: Any, level: int, **kwargs) -> None:
        """Add own name and log the message with given priority level."""
        _logger.log(level, f"{self}: {msg}", *args, **kwargs)

    def log_debug(self, msg: str, *args: Any, **kwargs) -> None:
        """Log a message only if debugging is enabled."""
        if self.debug:
            self.log_msg(msg, *args, level=logging.DEBUG, **kwargs)

    def log_info(self, msg: str, *args: Any, **kwargs) -> None:
        """Log a message with INFO priority."""
        self.log_msg(msg, *args, level=logging.INFO, **kwargs)

    def log_warning(self, msg: str, *args: Any, **kwargs) -> None:
        """Log a message with WARNING priority."""
        self.log_msg(msg, *args, level=logging.WARNING, **kwargs)

    def log_error(self, msg: str, *args: Any, **kwargs) -> None:
        """Log a message with ERROR priority."""
        self.log_msg(msg, *args, level=logging.ERROR, **kwargs)

    def start(self) -> None:
        """Pre-simulation hook."""

    def stop(self) -> None:
        """Post-simulation hook."""

    def has_method(self, method: str) -> bool:
        """Check if a method is defined and is not a dummy."""
        try:
            attr = getattr(self, method)
        except AttributeError:
            return False
        if any(
                # pylint: disable=comparison-with-callable
                # must convert the class method to a bound method for comparison
                attr == dm.__get__(self, type(self))
                for dm in (SBlock.dummy_method, SBlock.dummy_async_method)):
            return False
        return callable(attr)

    def dummy_method(self, *args, **kwargs):
        """
        A placeholder for all optional methods.

        Key properties:
            1. it can be safely called as super().method(...)
               from any overridden method.
            2. has_method() returns False for this method
        """

    async def dummy_async_method(self, *args, **kwargs):
        """A dummy async method, see dummy_method."""

    def get_conf(self) -> dict[str, Any]:
        """Return static block information as a dict."""
        return {
            'class': type(self).__name__,
            'debug': self.debug,
            'comment': self.comment,
            'name': self.name,
            }

    def __str__(self) -> str:
        try:
            return f"<{type(self).__name__} '{self.name}'>"
        except AttributeError:
            # A fallback for the case the self.name was not set yet, because repr()
            # and str() are supposed to always succeed.
            # The name is not set only in a derived class' __init__() before block.__init__().
            # Try to avoid repr() and str() there.
            return super().__str__()


class CBlock(Block, metaclass=abc.ABCMeta):
    """
    Base class for combinational blocks.
    """

    class InputGetter:
        """
        A helper class for a convenient access to input values.

        An input value can be retrieved using the name as a key
        or as an attribute.
        """

        __slots__ = ['_blk']

        def __init__(self, blk: CBlock) -> None:
            self._blk = blk

        def __getitem__(self, name: str) -> Any:
            iblk = self._blk.inputs[name]
            if isinstance(iblk, tuple):
                return tuple(b.output for b in iblk)
            return iblk.output

        def __getattr__(self, name: str) -> Any:
            try:
                return self[name]
            except KeyError:
                raise AttributeError(f"{self._blk} has no input {name!r}") from None

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """Verify that no SBlock add-ons were added to a CBlock."""
        if issubclass(cls, Addon):
            # DO NOT catch this error until https://bugs.python.org/issue38085 is fixed
            raise TypeError(f"{cls.__name__}: SBlock add-ons are not compatible with a CBlock")
        super().__init_subclass__(*args, **kwargs)

    def __init__(self, *args, **kwargs) -> None:
        self.iconnections: set[Block] = set()   # will be populated by Circuit._finalize()
        self.inputs: dict[str, Any] = {}
            # {"name": input(s)} where input is either:
            #   - a block providing the input value, or
            #   - a Const object providing the input value, or
            #   - a tuple of blocks or Consts in case of an input group
            # When building a circuit, i.e. before finalizing it:
            #   - input blocks may be temporarily represented by their names
            #   - Const pseudo-blocks may be temporarily represented by their values
        self._in = self.InputGetter(self)   # _in.name and _in[name] are two ways of getting
                                            # the value of the input or input group 'name'
        super().__init__(*args, **kwargs)

    def connect(self, *args, **kwargs) -> CBlock:
        """
        Connect inputs and input groups. Return self.

        connect() only saves the block's input connections data.
        The circuit-wide processing of interconnections will take place
        in Circuit.finalize().
        """
        self.circuit.check_not_finalized()
        if self.inputs:
            raise EdzedInvalidState("connect() may by called only once")
        if not args and not kwargs:
            raise ValueError("No inputs to connect were given")
        if '_' in kwargs:
            raise ValueError("Input name '_' is reserved")
        # save the data for later processing by Circuit.finalize
        if args:
            for inp in args:
                if _is_multiple(inp):
                    raise ValueError(
                        f"{inp!r} is not a single input specification; "
                        + "(wrap it in Const() if it is a constant)")
            self.inputs['_'] = args
        for iname, inp in kwargs.items():
            self.inputs[iname] = tuple(inp) if _is_multiple(inp) else inp
        return self

    def input_signature(self) -> dict[str, None|int]:
        """
        Return a dict with so called input signature.

        The signature has the following structure:
            key = input name
            value = None, if the input is a single input, or
                    number of inputs in a group, if the input is a group
        """
        if not self.inputs:
            raise EdzedInvalidState("not connect()'ed yet")
        return {
            iname: len(ival) if isinstance(ival, tuple) else None
            for iname, ival in self.inputs.items()}

    def check_signature(self, esig: Mapping[str, None|int|Sequence[int]]) -> dict:
        """
        Check an expected signature 'esig' with the actual one.
        """
        def setdiff_msg(actual: Set[str], expected: Set[str]) -> str:
            """Return a message describing a diff of two sets of names."""
            unexpected = actual - expected
            missing = expected - actual
            msgparts = []
            if unexpected:
                subparts = []
                for name in unexpected:
                    if (suggestions := difflib.get_close_matches(name, missing, n=3)):
                        top3 = ' or '.join(repr(s) for s in suggestions)
                        subparts.append(f"{name!r} (did you mean {top3} ?)")
                    else:
                        subparts.append(repr(name))
                msgparts.append("unexpected: " + ', '.join(subparts))
            if missing:
                msgparts.append("missing: " + ', '.join(repr(name) for name in missing))
            return ", ".join(msgparts)

        def valuediff_msg(
                name: str,
                value: None|int,
                expected: None|int|Sequence[None|int]
                ) -> Optional[str]:
            """Return a message describing a diff in signature items."""
            if expected is None:
                if value is not None:
                    return f"{name}: is a group, expected was a single input"
            elif value is None:
                return f"{name}: is a single input, expected was a group"
            elif isinstance(expected, int):
                if value != expected:
                    return f"group {name}: input count is {value}, expected was {expected}"
            else:
                try:
                    cmin, cmax = expected
                except Exception:
                    raise ValueError(
                        f"check_signature: input {name!r}: invalid value {expected!r}"
                        ) from None
                if cmin is not None and value < cmin:
                    return f"group {name}: input count is {value}, minimum is {cmin}"
                if cmax is not None and value > cmax:
                    return f"group {name}: input count is {value}, maximum is {cmax}"
            return None # no error

        bsig = self.input_signature()   # block signature
        if bsig != esig:
            if bsig.keys() != esig.keys():
                # names differ
                errmsg = setdiff_msg(bsig.keys(), esig.keys())
                raise ValueError(f"Not connected correctly: {errmsg}")
            # if names are OK, values must differ
            errors = [
                msg for msg in (
                    valuediff_msg(name, bsig[name], expected)
                    for name, expected in esig.items())
                if msg is not None]
            if errors:
                raise ValueError(f"Not connected correctly: {'; '.join(errors)}")
        return bsig

    @abc.abstractmethod
    def calc_output(self) -> Any:
        """Calculate and return the output value."""

    def eval_block(self) -> bool:
        """
        Compute new output value. Return an output change indicator.
        """
        previous = self._output
        value = self.calc_output()
        if value is UNDEF:
            raise ValueError("Output value must not be <UNDEF>")
        if previous == value:
            return False
        self.log_debug("output: %s -> %s", previous, value)
        self._output = value
        for event in self._output_events:
            event.send(self, trigger='output', previous=previous, value=value)
        return True

    def get_conf(self) -> dict[str, Any]:
        conf = super().get_conf()
        conf['type'] = 'combinational'
        if self.circuit.is_finalized():
            conf['inputs'] = {
                iname: tuple(g.name for g in ival) if isinstance(ival, tuple) else ival.name
                for iname, ival in self.inputs.items()}
        return conf


class SBlock(Block):
    """
    Base class for sequential blocks, i.e. blocks with internal state.
    """

    _ct_handlers: dict[str, Callable]   # event handling methods _event_NAME

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """
        Verify that all add-ons precede the SBlock in the class hierarchy.

        This is important for a correct order of method calls.
        """
        super().__init_subclass__(*args, **kwargs)
        cls._ct_handlers = {}
        sblock_seen = False
        for mro in cls.__mro__:
            if sblock_seen:
                if issubclass(mro, Addon):
                    # DO NOT catch this error until https://bugs.python.org/issue38085 is fixed
                    raise TypeError(
                        f"The order of {cls.__name__} base classes is incorrect: "
                        + f"add-ons like {mro.__name__} must appear before SBlock")
            elif mro is SBlock:
                sblock_seen = True

            if issubclass(mro, (SBlock, Addon)):
                for method_name, method in vars(mro).items():
                    etype = method_name.removeprefix('_event_')
                    # .removeprefix() returns the string unchanged if prefix was not found
                    if etype is not method_name and etype not in cls._ct_handlers:
                        cls._ct_handlers[etype] = method
        assert sblock_seen

    def __init__(
            self, *args,
            on_every_output: zero_or_more[Event] = None,
            **kwargs) -> None:
        if self.has_method('init_from_value'):
            self.initdef = kwargs.pop('initdef', UNDEF)
        self._event_active = False      # guard against event recursion
        self._every_output_events = event_tuple(on_every_output)
        # completed Circuit.init_sblock initialization steps (2 in total)
        # value -1 or -2 means initialization step 1 or 2 respectively is in progress
        self.init_steps_completed = 0
        super().__init__(*args, **kwargs)

    def set_output(self, value: Any) -> None:
        """Set new output value."""
        if value is UNDEF:
            raise ValueError("Output value must not be <UNDEF>")
        previous = self._output
        if previous == value:
            if not self._every_output_events:
                return
            self.log_debug("output: %s (unchanged)", value)
        else:
            self.log_debug("output: %s -> %s", previous, value)
            self._output = value
            self.circuit.sblock_queue.put_nowait(self)
            for event in self._output_events:
                event.send(self, trigger='output', previous=previous, value=value)
        for event in self._every_output_events:
            event.send(self, trigger='output', previous=previous, value=value)

    def _event(self, etype: str|EventType, data: Mapping[str, Any]) -> Any:
        """
        The default event handler. Not to be called directly.

        The base class does not recognize any events.
        """
        raise EdzedUnknownEvent(f"{self}: Unknown event type {etype!r}")

    def event(self, etype: str|EventType, /, **data) -> Any:
        """
        An entry point for events.

        Evaluate so called conditional events. See the EventCond class.

        Respond with ValueError to unknown event types.

        Handle the received event ETYPE:
            - invoke the specialized _event_ETYPE() method if such
              method exists; otherwise
            - invoke the general _event() method

        IMPORTANT: application code should check Circuit.is_ready()
        before submitting external events for processing. The event()
        function must process events also during cleanup, when the
        simulator is no longer ready, but cannot distinguish internal
        and external events.
        """
        if isinstance(etype, str):
            if not etype:
                raise ValueError("Event name must not be empty")
        elif not isinstance(etype, EventType):
            raise TypeError(
                f"Event type must be either a string or an EventType, but got {etype!r}")
        self.log_debug("got event %r, data: %s", etype, data)
        if self._event_active:
            raise EdzedCircuitError(f"{self}: Forbidden recursive event() call")
        self._event_active = True
        try:
            while isinstance(etype, EventCond):
                cond_etype = etype.etrue if data.get('value') else etype.efalse
                self.log_debug("conditional event -> %r", etype)
                if cond_etype is None:
                    return None
                etype = cond_etype
            if 0 <= self.init_steps_completed < 2:
                # a destination block may be uninitialized, because events
                # may be generated during the initialization process
                self.log_debug("pending event, initializing early")
                # the initialization may be carried out with an event, let's enable it
                with self._enable_event:    # type: ignore[attr-defined]
                    self.circuit.init_sblock(self, full=True)
            if isinstance(etype, str):
                handler = type(self)._ct_handlers.get(etype)
            else:
                handler = None
            try:
                if handler:
                    # handler is an unbound method
                    retval = handler(self, **data)
                else:
                    retval = self._event(etype, data)
            except EdzedUnknownEvent:
                raise
            except Exception as err:
                assert err.__traceback__ is not None
                if err.__traceback__.tb_next is not None:
                    # The traceback has more than just one level, i.e. the handler function
                    # call itself succeeded. Errors like missing arguments are thus ruled out
                    # and the error must have occurred inside the handler. The internal state
                    # of the block could have been corrupted. That's a sufficient reason for
                    # aborting the simulation.
                    sim_err: Exception|None
                    sim_err = EdzedCircuitError(
                        f"{self}: {type(err).__name__} during handling of event "
                        + f"'{etype}', data: {data}: {err}")
                    sim_err.__cause__ = err
                    self.circuit.abort(sim_err)
                    # break a reference cycle
                    sim_err = None
                raise
            return retval
        finally:
            self._event_active = False

    # property + class is an awesome combination, isn't it?
    @property
    class _enable_event:
        """
        A context manager temporarily enabling recursive events.

        Usage:
            ... while handling an event ...
            with self._enable_event:
                self.event(...) # without _enable_event this would
                                # raise "Forbidden recursive event"
        """

        __slots__ = ['_block', '_event_saved']

        def __init__(self, block: SBlock) -> None:
            self._block = block
            self._event_saved: bool

        def __enter__(self):
            block = self._block
            self._event_saved = block._event_active
            block._event_active = False
            return block

        def __exit__(self, *exc_info):
            self._block._event_active = self._event_saved

    def get_state(self) -> Any:
        """
        Return the internal state.

        The default implementation assumes the state is equal output.
        Must be redefined for more complex SBlocks.
        """
        if self._output is UNDEF:
            raise EdzedInvalidState(f"get_state() on uninitialized block {self}")
        return self._output

    def init_regular(self) -> Any:
        """
        Initialize the internal state and the output.

        The return value is ignored.
        """

    # optional methods (can't get the arg type annotation right)
    # init_async and stop_async accept no args, init_from_value expects 1 arg
    # in all three cases the return value is ignored
    init_async: ClassVar[Callable[..., Coroutine[Any, Any, Any]]] = Block.dummy_async_method
    stop_async: ClassVar[Callable[..., Coroutine[Any, Any, Any]]] = Block.dummy_async_method
    init_from_value: ClassVar[Callable[..., Any]] = Block.dummy_method

    def get_conf(self) -> dict[str, Any]:
        conf = super().get_conf()
        conf['type'] = 'sequential'
        return conf


class Addon:
    """
    Base class for all SBlock add-ons.
    """


class EventType:
    """
    A base class for all special event types.

    The regular event type is str (plain string like 'put').
    """


dc_slots = {'slots': True} if P3_10 else {}
@dc.dataclass(frozen=True, **dc_slots)
class EventCond(EventType):
    """
    A conditional event type.

    Roughly equivalent to:
        etype = etrue if value else efalse
    where the value is taken from the event data item 'value'.
    Missing value is evaluated as False, i.e. 'efalse' is selected.

    None as etrue or efalse means no event in the respective case.
    """

    etrue: Optional[str|EventType]
    efalse: Optional[str|EventType]

EvDataType = MutableMapping[str, Any]
EvFilterType = Callable[[EvDataType], Any]


class Event:
    """
    An internal (block to block) event.
    """

    # pylint: disable-next=too-many-arguments
    def __init__(
            self,
            dest: str|SBlock,
            etype: str|EventType = 'put',
            *,
            efilter: zero_or_more[EvFilterType] = None,
            repeat: Optional[float|str] = None,
            count: Optional[int] = None) -> None:
        if repeat is not None:
            destname = dest if isinstance(dest, str) else dest.name
            dest = sblocks1.Repeat(
                None,
                comment=f"automatic repeat: event={etype!r}, destination={destname!r}",
                dest=dest, etype=etype, interval=repeat, count=count)
        elif count is not None:
            raise ValueError("Argument 'count' is valid only with 'repeat'")
        self.typecheck(etype)
        self._dest = dest
        self._etype = etype
        self._filters = efilter_tuple(efilter)
        simulator.get_circuit().resolve_name(self, '_dest', SBlock)

    @property
    def dest(self) -> SBlock:
        if isinstance(self._dest, str):
            raise EdzedInvalidState(
                f"{self}: destination block object not available in an unfinalized circuit")
        return self._dest

    @property
    def etype(self) -> str|EventType:
        return self._etype

    @classmethod
    def abort(cls) -> Event:
        return cls('_ctrl', 'abort')

    @staticmethod
    def typecheck(etype: Any) -> None:
        if isinstance(etype, str):
            if not etype:
                raise ValueError("Event name must be a non-empty string")
        elif not isinstance(etype, EventType):
            raise TypeError(f"Event type must be a string or EventType, but got {etype!r}")

    def send(self, source: Block, /, **data) -> bool:
        """
        Apply filters and send the event to the destination block.

        Add sender block's name to the event data as 'source'.

        Return True if sent, False if rejected by a filter.
        """
        dest = self._dest
        # in a finalized circuit there are no references by name
        assert isinstance(dest, SBlock), (
            f"Incorrect destination type in {self}, circuit not finalized?")
        if not source.circuit is dest.circuit is simulator.get_circuit():
            raise EdzedCircuitError(
                f"{self}: source {source} and/or destination not in the current circuit")
        data['source'] = source.name
        for efilter in self._filters:
            retval = efilter(data)
            if isinstance(retval, MutableMapping):
                for key in retval:
                    if not isinstance(key, str):
                        raise TypeError(
                            f"Event filter {efilter.__name__} returned non-string key {key!r} "
                            + f"(value {retval[key]})")
                data = retval   # type: ignore[assignment]
            elif not retval:
                source.log_debug(f"Not sending event {self} (rejected by a filter)")
                return False
        source.log_debug("sending event %s", self)
        dest.event(self._etype, **data)
        return True

    def __str__(self):
        dest = self._dest
        # give correct result even before resolving the dest name to the dest block
        dest_name = dest if not isinstance(dest, Block) else dest.name
        return f"<{type(self).__name__} dest='{dest_name}', event='{self._etype}'>"


class ExtEvent:
    """
    An event with an external source.

    Main differences to the internal Event:
        - usable after the circuit initialization
        - no filters
        - .send() returns the event handler's exit value
    """
    def __init__(self, dest: str|SBlock, etype: str = 'put', source: str = '_ext_'):
        if isinstance(dest, str):
            dest_block = simulator.get_circuit().findblock(dest)
        elif isinstance(dest, Block):
            dest_block = dest
        else:
            raise TypeError(
                f"Expected was a destination block object or its name, but got {dest!r}")
        if not isinstance(dest_block, SBlock):
            raise TypeError(f"Cannot send events to a non-sequential block {dest_block}")
        if not isinstance(etype, str) or not etype:
            raise TypeError("External event type must be a non-empty string")
        if not isinstance(source, str):
            raise TypeError("Default source must be a string")
        self._dest = dest_block
        self._etype = etype
        self._source = source if source.startswith("_ext_") else "_ext_" + source

    @property
    def dest(self) -> SBlock:
        return self._dest

    @property
    def etype(self) -> str:
        return self._etype

    def send(self, value=UNDEF, **data) -> Any:
        """
        Send the event to the destination block.

        Add sender's name (with '_ext_' prepended) to the event
        data as 'source'.

        Return the event handler's exit value.
        """
        if not simulator.get_circuit().is_ready():
            raise EdzedInvalidState("The circuit simulation is shutting down or not running")
        if value is not UNDEF:
            data['value'] = value
        try:
            source = data['source']
        except KeyError:
            data['source'] = self._source
        else:
            if not isinstance(source, str):
                raise TypeError(f"Event source must be a string, but got {source!r}")
            if not source.startswith("_ext_"):
                data['source'] = "_ext_" + source
        return self._dest.event(self._etype, **data)

    def __str__(self):
        return f"<{type(self).__name__} dest='{self._dest.name}', event='{self._etype}'>"


_T_item = TypeVar("_T_item")
@overload
def _to_tuple(args: None, validator: Callable[[_T_item], Any]) -> tuple[()]:
    ...
@overload
def _to_tuple(args: _T_item, validator: Callable[[_T_item], Any]) -> tuple[_T_item]:
    ...
@overload
def _to_tuple(
        args: Sequence[_T_item], validator: Callable[[_T_item], Any]
        ) -> tuple[_T_item, ...]:
    ...
def _to_tuple(args, validator):
    """
    Transform 'args' to a tuple of items. Validate each item.

    The validation is deemed successful unless the validator raises.
    """
    if args is None:
        return ()
    if isinstance(args, tuple):
        pass
    elif _is_multiple(args):
        args = tuple(args)
    else:
        args = (args,)
    for arg in args:
        validator(arg)
    return args


def event_tuple(events: zero_or_more[Event])-> tuple[Event, ...]:
    """
    Transform the argument to a tuple of events.

    Accept a single event or a sequence of events.
    """
    def validator(event):
        if not hasattr(event, 'send'):
            raise TypeError(f"Expected was an Event-like object, got {event!r}")

    return _to_tuple(events, validator)


def efilter_tuple(
        efilters: zero_or_more[EvFilterType]) -> tuple[EvFilterType, ...]:
    """
    Transform the argument to a tuple of event filters.

    Accept a single event filter or a sequence of filters.
    """
    def validator(efilter):
        if not callable(efilter):
            raise TypeError(f"Expected was a callable, got {efilter!r}")

    return _to_tuple(efilters, validator)


# importing at the end when all names are defined resolves a circular import issue
# pylint: disable=wrong-import-position
from . import simulator
from .blocklib import sblocks1

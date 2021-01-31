"""
Circuit blocks.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Project home: https://github.com/xitop/edzed/
"""

import abc
import collections.abc as cabc
from dataclasses import dataclass
import difflib
import logging
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Union
import weakref

from .exceptions import EdzedError, EdzedInvalidState


__all__ = [
    'UNDEF', 'Const', 'Block', 'CBlock', 'SBlock',
    'Event', 'EventType', 'EventCond', 'event_tuple', 'checkname',
    ]

_logger = logging.getLogger(__package__)


class _UndefType:
    """
    Type for uninitialized circuit block's output value (UNDEF).

    UNDEF is a singleton.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    def __repr__(self):
        return "<UNDEF>"


UNDEF = _UndefType()


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
    _instances = weakref.WeakValueDictionary()

    def __new__(cls, const):
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

    def __init__(self, const: Any):
        self._output = const

    @property
    def output(self) -> Any:
        return self._output

    @property
    def name(self) -> str:
        return str(self)

    def __str__(self):
        return f"<{type(self).__name__} {self.output!r}>"


def checkname(name, nametype):
    """Raise if name is not valid."""
    if not isinstance(name, str):
        raise TypeError(f"{nametype} must be a string, but got {name!r}")
    if not name:
        raise ValueError(f"{nametype} must be a non-empty string")


class EventType:
    """
    A base class for all special event types.

    The regular event type is str (plain string like 'put').
    """


EFilter = Callable[[Mapping], Any]
EventsArg = Union['Event', Iterable['Event'], Sequence['Event']]
EFiltersArg = Union[EFilter, Iterable[EFilter], Sequence[EFilter]]


class Event:
    """
    An event to be send.
    """

    # all circuit Events to check by Circuit._resolve_events, cleared afterward
    instances = weakref.WeakSet()

    def __init__(
            self,
            dest: Union[str, 'SBlock'],
            etype: Union[str, EventType] = 'put',
            *, efilter: EFiltersArg = ()):
        self.typecheck(etype)
        self.dest = dest
        self.etype = etype
        self._filters = efilter_tuple(efilter)
        type(self).instances.add(self)

    @staticmethod
    def typecheck(etype):
        """Raise if etype is not a valid event type value."""
        if isinstance(etype, str):
            if not etype:
                raise ValueError("event name must be a non-empty string")
        elif not isinstance(etype, EventType):
            raise TypeError(f"event type must be a string or EventType, but got {etype!r}")

    # TODO in Python3.8+ (see SBlock.event for an explanation):
    #   def send(self, source: 'Block', /, **data) -> bool:
    # pylint: disable=no-method-argument, protected-access
    def send(*args, **data) -> bool:
        """
        Apply filters and send the event to the dest block.

        Add sender block's name to the event data as 'source'.

        Return True if sent, False if rejected by a filter.
        """
        self, source = args
        if self.dest.circuit is not source.circuit:
            raise EdzedError(f"event destination {self.dest} is not in the current circuit")
        data['source'] = source.name
        for efilter in self._filters:
            retval = efilter(data)
            if isinstance(retval, dict):
                data = retval
            elif not retval:
                source.log(f"Not sending event {self} (rejected by a filter)")
                return False
        dest = self.dest
        if not dest.is_initialized():
            # a destination block may be uninitialized, because events
            # may be generated during initialization process
            dest.log("pending event, initializing early")
            source.circuit.init_sblock(dest)
        source.log("sending event %s", self)
        dest.event(self.etype, **data)
        return True

    def __str__(self):
        dest = self.dest
        # give correct result even before resolving the dest name to the dest block
        dest_name = dest if isinstance(dest, str) else dest.name
        return f"<{type(self).__name__} dest='{dest_name}', event='{self.etype}'>"


def _is_multiple(arg):
    """
    Check if arg specifies multiple ordered items (inputs, events, etc.)

    The check is based on the type. The actual item count does not
    matter and can be any value including zero or one.

    Iterators are also considered to be multiple items. Remember that
    they can be iterated over only once.

    The str type arg is considered as a single name and not as a string
    of multiple characters. That's why the return value is False.

    A set is unordered and thus not recognized as multiple items by
    this function. Return value is False.

    """
    return not isinstance(arg, str) and isinstance(arg, (cabc.Sequence, cabc.Iterator))


def _to_tuple(args, validator):
    """
    Transform 'args' to a tuple of items. Validate each item.

    The validation is deemed successful unless the validator raises.
    """
    if isinstance(args, tuple):
        pass
    elif _is_multiple(args):
        args = tuple(args)
    else:
        args = (args,)
    for arg in args:
        validator(arg)
    return args


def event_tuple(events: EventsArg) -> Tuple[Event, ...]:
    """
    Transform the argument to a tuple of events.

    Accept a single event or a sequence of events.
    """
    def validator(event):
        if not hasattr(event, 'send'):
            raise TypeError(f"Expected was an Event-like object, got {event!r}")

    return _to_tuple(events, validator)


def efilter_tuple(efilters: EFiltersArg) -> Tuple[EFilter, ...]:
    """
    Transform the argument to a tuple of event filters.

    Accept a single event filter or a sequence of filters.
    """
    def validator(efilter):
        if not callable(efilter):
            raise TypeError(f"Expected was a callable, got {efilter!r}")

    return _to_tuple(efilters, validator)


class Block:
    """
    Base class for a circuit building block.
    """
    def __init__(
            self,
            name: Optional[str], *,
            desc: str = "",
            on_output: EventsArg = (),
            _reserved: bool = False,
            debug: bool = False,
            **kwargs):
        """
        Create a block. Add it to the circuit.
        """
        if name is None:
            name = "_@" + hex(id(self))[2:]  # id() is unique
        else:
            checkname(name, "block name")
            if name.startswith('_') and not _reserved:
                raise ValueError(f"{name!r} is a reserved name (starting with an underscore")
        self.name = name
        is_cblock = isinstance(self, CBlock)
        is_sblock = isinstance(self, SBlock)
        if not is_sblock and not is_cblock:
            raise TypeError("Can't instantiate abstract Block class")
        assert not (is_sblock and is_cblock)
        for key, value in kwargs.items():
            if not key.startswith('x_') and not key.startswith('X_'):
                raise TypeError(
                    f"'{key}' is an invalid keyword argument for {type(self).__name__}()")
            setattr(self, key, value)
        self.desc = desc
        self.debug = bool(debug)
        self._output_events = event_tuple(on_output)
        # oconnections will be populated by Circuit._init_connections:
        self.oconnections = set()   # output is connected to these blocks
        self._output = UNDEF
        self.circuit = simulator.get_circuit()
        self.circuit.addblock(self)

    def is_initialized(self) -> bool:
        """Return True if the output has been initialized."""
        return self._output is not UNDEF

    @property
    def output(self) -> Any:
        """Read-only access to the output value."""
        return self._output

    def log(self, msg: str, *args, **kwargs) -> None:
        """
        Log a message if debugging is enabled.

        Block debug messages are logged with INFO severity, because
        the debug severity is used mainly for the simulator itself.
        """
        if self.debug:
            _logger.info(f"{self}: {msg}", *args, **kwargs)

    def warn(self, msg: str, *args, **kwargs) -> None:
        """Log a warning message."""
        _logger.warning(f"{self}: {msg}", *args, **kwargs)

    def _send_output_events(self, previous, value):
        for event in self._output_events:
            event.send(self, previous=previous, value=value)

    def start(self) -> None:
        """
        Pre-simulation hook.
        """

    def stop(self) -> None:
        """
        Post-simulation hook.
        """

    def has_method(self, method: str) -> bool:
        """Check if a method is defined and is not a dummy."""
        try:
            method = getattr(self, method)
        except AttributeError:
            return False
        cls = type(self)
        if method is cls.dummy_method or method is cls.dummy_async_method:
            return False
        return callable(method)

    def dummy_method(self, *args, **kwargs):
        """
        A placeholder for all optional methods.

        Key properties:
            1. it can be safely called as super().method(...)
               from any overriden method.
            2. has_method() returns False for this method
        """

    async def dummy_async_method(self, *args, **kwargs):
        """A dummy async method, see dummy_method."""

    def get_conf(self) -> Mapping[str, Any]:
        """Return static block information as a dict."""
        return {
            'class': type(self).__name__,
            'debug': self.debug,
            'desc': self.desc,
            'name': self.name,
            }

    def __str__(self):
        try:
            return f"<{type(self).__name__} '{self.name}'>"
        except AttributeError:
            # A fallback for the case the self.name was not set yet, because repr()
            # and str() are supposed to always succeed.
            # The name is not set only in a derived class' __init__() before block.__init__().
            # Try to avoid repr() and str() there.
            return super().__str__()


class Addon:
    """
    Base class for all SBlock add-ons.
    """


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

        def __init__(self, blk):
            self._blk = blk

        def __getitem__(self, name):
            iblk = self._blk.inputs[name]
            if isinstance(iblk, tuple):
                return tuple(b.output for b in iblk)
            return iblk.output

        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(f"{self._blk} has no input '{name}'") from None

    def __init_subclass__(cls, *args, **kwargs):
        """Verify that no SBlock add-ons were added to a CBlock."""
        if issubclass(cls, Addon):
            # https://bugs.python.org/issue38085
            # raise TypeError(
            _logger.error(
                f"{cls.__name__}: SBlock add-ons are not compatible with a CBlock")
        super().__init_subclass__(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        self.iconnections = set()   # will be populated by Circuit._init_connections()
        self.inputs = {}    # {"name": input(s)} where input is either:
                            #   - a block providing the input value, or
                            #   - a tuple of blocks in case of an input group
                            # When building a circuit, input blocks may be
                            # temporarily represented by their names
        self._in = self.InputGetter(self)   # _in.name and _in[name] are two ways of getting
                                            # the value of the input or input group 'name'
        super().__init__(*args, **kwargs)

    def connect(self, *args, **kwargs):
        """
        Connect inputs and input groups.

        connect() only saves the block's input connections data.
        The circuit-wide processing of interconnections will take place
        in Circuit._init_connections().
        """
        self.circuit.check_not_finalized()
        if self.inputs:
            raise EdzedInvalidState("connect() may by called only once")
        if not args and not kwargs:
            raise ValueError("No inputs to connect were given")
        if '_' in kwargs:
            raise ValueError("Input name '_' is reserved")
        # save the data for later processing by Circuit._init_connections
        if args:
            for inp in args:
                if _is_multiple(inp):
                    raise ValueError(
                        f"{inp!r} is not a single input specification; "
                        "(wrap it in Const() if it is a constant)")
            self.inputs['_'] = args
        for iname, inp in kwargs.items():
            if _is_multiple(inp):
                inp = tuple(inp)
            if inp == '':
                inp = iname
            self.inputs[iname] = inp
        return self

    def input_signature(self) -> dict:
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

    def check_signature(self, esig: Mapping) -> dict:
        """
        Check an expected signature 'esig' with the actual one.
        """
        def setdiff_msg(actual, expected):
            """Return a message describing a diff of two sets of names."""
            unexpected = actual - expected
            missing = expected - actual
            msgparts = []
            if unexpected:
                subparts = []
                for name in unexpected:
                    suggestions = difflib.get_close_matches(name, missing, n=3)
                    if suggestions:
                        top3 = ' or '.join(repr(s) for s in suggestions)
                        subparts.append(f"{name!r} (did you mean {top3} ?)")
                    else:
                        subparts.append(repr(name))
                msgparts.append("unexpected: " + ', '.join(subparts))
            if missing:
                msgparts.append("missing: " + ', '.join(repr(name) for name in missing))
            return ", ".join(msgparts)

        def valuediff_msg(name, value, expected):
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
                errmsg = setdiff_msg(set(bsig), set(esig))
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
    def _eval(self) -> Any:
        """Compute and return the output value."""

    def eval_block(self) -> bool:
        """
        Compute new output value. Return an output change indicator.
        """
        previous = self._output
        value = self._eval()
        if value is UNDEF:
            raise ValueError("Output value must not be <UNDEF>")
        if previous == value:
            return False
        self.log("output: %s -> %s", previous, value)
        self._output = value
        self._send_output_events(previous, value)
        return True

    def get_conf(self) -> Mapping[str, Any]:
        conf = super().get_conf()
        conf['type'] = 'combinational'
        if self.circuit.is_finalized():
            conf['inputs'] = {
                iname: tuple(g.name for g in ival) if isinstance(ival, tuple) else ival.name
                for iname, ival in self.inputs.items()}
        return conf


@dataclass(frozen=True)
class EventCond(EventType):
    """
    A conditional event type.

    Roughly equivalent to:
        etype = etrue if value else efalse
    where the value is taken from the event data item ['value'].
    Missing value is evaluated as False, i.e. 'efalse' is selected.

    None value means no event.
    """
    __slots__ = ['etrue', 'efalse']
    etrue: Union[None, str, EventType]
    efalse: Union[None, str, EventType]


class SBlock(Block):
    """
    Base class for sequential blocks, i.e. blocks with internal state.
    """

    def __init_subclass__(cls, *args, **kwargs):
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
                    # https://bugs.python.org/issue38085
                    # raise TypeError(
                    _logger.error(
                        f"The order of {cls.__name__} base classes is incorrect: "
                        f"add-ons like {mro.__name__} must appear before SBlock")
            elif mro is SBlock:
                sblock_seen = True

            if issubclass(mro, (SBlock, Addon)):
                for method_name, method in vars(mro).items():
                    if method_name.startswith('_event_'):
                        etype = method_name[7:]     # strip '_event_'
                        if etype not in cls._ct_handlers:
                            cls._ct_handlers[etype] = method
        assert sblock_seen

    def __init__(self, *args, **kwargs):
        if self.has_method('init_from_value'):
            self.initdef = kwargs.pop('initdef', UNDEF)
        self._event_active = False      # guard against event recursion
        super().__init__(*args, **kwargs)

    def set_output(self, value: Any) -> None:
        """Set new output value."""
        if value is UNDEF:
            raise ValueError("Output value must not be <UNDEF>")
        previous = self._output
        if previous == value:
            return
        self.log("output: %s -> %s", previous, value)
        self._output = value
        self.circuit.sblock_queue.put_nowait(self)
        self._send_output_events(previous, value)

    def _event(self, etype, data):  # pylint: disable=unused-argument, no-self-use
        """
        Handle an event.
        """
        return NotImplemented

    # TODO: There is an issue fixed in Python3.8+ by PEP570, but
    # we want to support Python 3.7, so a workaround must be used.
    #
    # Python 3.8 function definition will be:
    #   def event(self, etype: Union[str, EventType], /, **data) -> Any:
    #
    # The problem with:
    #   def event(self, etype, **data):     # type hints removed
    # is that names used as positional arguments (self and etype in this case)
    # cannot be used as a keyword argument in a call:
    #   block.event('foo', etype=1)         # TypeError
    #
    # pylint: disable=no-method-argument, protected-access
    def event(*args, **data) -> Any:
        """
        Error handling wrapper, see _event for function usage.

        Evaluate so called conditional events. See the EventCond class.

        Respond with ValueError to unknown event types.

        Handle the received event ETYPE:
            - invoke the specialzed _event_ETYPE() method if such
              method exists; otherwise
            - invoke the general _event() method

        IMPORTANT: application code should check Circuit.is_ready()
        before submitting external events for processing. The event()
        function must process events also during cleanup, when the
        simulator is no longer ready, but cannot distinguish internal
        and external events.
        """
        self, etype = args
        Event.typecheck(etype)
        if data:
            self.log("got event %r, data: %s", etype, data)
        else:
            self.log("got event %r", etype)
        if self._event_active:
            raise EdzedError(f"{self}: Forbidden recursive event() call")
        self._event_active = True
        try:
            while isinstance(etype, EventCond):
                etype = etype.etrue if data.get('value') else etype.efalse
                self.log("conditional event -> %r", etype)
                if etype is None:
                    return None
            handler = type(self)._ct_handlers.get(etype)    # pylint: disable=protected-access
            try:
                # handler is an unbound method, bind it with handler.__get__(self)
                retval = handler.__get__(self)(**data) if handler else self._event(etype, data)
            except Exception as err:
                if not self.circuit.is_current_task() and err.__traceback__.tb_next is not None:
                    # 1. The raised exception won't be handled by the simulation task.
                    # 2. The traceback has more than one level only, i.e. the handler function
                    # call itself succeded. Errors like missing arguments are thus ruled out
                    # and the error must have occurred inside the handler. The internal state
                    # of the block could have been corrupted. That's a sufficient reason for
                    # aborting the simulation.
                    sim_err = EdzedError(
                        f"{self}: {type(err).__name__} during handling of event "
                        f"'{etype}', data: {data}: {err}")
                    sim_err.__cause__ = err
                    self.circuit.abort(sim_err)
                raise
            if retval is NotImplemented:
                raise ValueError(f"{self}: Unknown event type '{etype}'")
            return retval
        finally:
            self._event_active = False

    @property
    class _enable_event:
        """
        A context manager temporarily enabling recursive events.

        Usage:
            ... during handling of an event ...
            with self._enable_event:
                self.event(...) # without _enable_event this would
                                # raise "Forbidden recursive event()"
        """
        def __init__(self, block: 'SBlock'):
            self._block = block
            self._event_saved = None

        # pylint: disable=protected-access
        def __enter__(self):
            block = self._block
            self._event_saved = block._event_active
            block._event_active = False
            return block

        def __exit__(self, *exc_info):
            self._block._event_active = self._event_saved

    def put(self, value: Any, **data) -> Any:
        """put(x) is a shortcut for event('put', value=x)."""
        return self.event('put', **data, value=value)

    def get_state(self) -> Any:
        """
        Return the internal state.

        The default implementation assumes the state is equal output.
        Must be redefined for more complex SBlocks.
        """
        return self._output

    def init_regular(self) -> None:
        """
        Initialize the internal state and the output.
        """

    # optional methods
    init_async = Block.dummy_async_method
    stop_async = Block.dummy_async_method
    init_from_value = Block.dummy_method

    def get_conf(self) -> Mapping[str, Any]:
        conf = super().get_conf()
        conf['type'] = 'sequential'
        return conf


# importing at the end when all names are defined resolves a circular import issue
# pylint: disable=wrong-import-position
from . import simulator

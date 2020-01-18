"""
Circuit blocks.

Basic block types:
    Const -- a trivial container for a constant value.
    CBlock -- a combinational block.
        A block with inputs. The output is depending on input values
        only. When an input value changes, the simulator calls
        the block's eval_block() method to recalculate the output value.
    SBlock -- a sequential block.
        A block without inputs. The output value is determined by its
        internal state. This state is influenced by:
            - events sent from other blocks,
            - events coming from external sources,
            - the block's own activity like timers, or
              readouts of sensors and gauges
        When SBlock's output value changes, the block notifies the
        simulator.
"""

import abc
import collections.abc as cabc
from dataclasses import dataclass
import logging
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Union
import weakref

from .exceptions import EdzedError, EdzedInvalidState
from .utils import corrections


__all__ = [
    'UNDEF', 'Const', 'Block', 'CBlock', 'SBlock',
    'Event', 'EventType', 'EventCond', 'event_tuple', 'checkname',
    ]

_logger = logging.getLogger(__package__)


class _UndefType:
    """
    Type for uninitialized circuit block's output value (UNDEF).

    UNDEF is often used as a sentinel. It is a singleton.

    Warning: UNDEF is not JSON serializable.
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

    An Event consist of a destination sequential block and an event
    type. Default type is 'put'. The block may be given by its name.
    The names will be resolved before starting the simulation.

    The optional 'efilter' function(s) are called with the event data
    as its sole argument (a dict). If it returns a dict, the returned
    dict becomes the new event data. It is fine to return the input
    dict modified as needed. If the function returns anything other
    than a dict, the event will be filtered out. efilter is a keyword
    only argument.

    The Event accepts a single event filter or a sequence of zero or
    more filters. Default is no filtering. Multiple filters are called
    in their definition order like a "pipeline".

    The send() methods adds the source name if it is missing:
        "source": "name of event source block"

    Note that 'put' data must contain by convention:
        "value": VALUE
    however this is not checked by the send() method.

    Event data may contain arbitrary key:value pairs. The recipient
    must ignore all data it does not understand.
    """

    # all circuit Events to check by Circuit._resolve_events, cleared afterward
    instances = weakref.WeakSet()

    def __init__(
            self,
            dest: Union[str, 'Block'],
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

    # TODO in Python3.8+ (see Block.event for an explanation):
    #   def send(self, source: 'Block', /, **data) -> bool:
    # pylint: disable=no-method-argument, protected-access
    def send(*args, **data) -> bool:
        """
        Apply filters and send the event to the dest block.

        Add sender block's name to the event data as 'source'.

        Return True is sent, False if rejected by a filter.
        """
        self, source = args
        if self.dest.circuit is not source.circuit:
            raise EdzedError(f"event destination {self.dest} is not in the current circuit")
        data['source'] = source.name
        for efilter in self._filters:
            data = efilter(data)
            if not isinstance(data, dict):
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

    Attributes:
        debug -- boolean, enable debug messages,
            (note: messages are logged with INFO severity, not DEBUG)
        desc -- str, any remark, not used internally
        name -- non-empty str, unique identifier
                or None for an automatically generated name,
            The name used in messages. Names are arbitrary except
            that names prefixed by an underscore are reserved for
            automatically created blocks.
            Use automatically generated names only for auxilliary
            blocks that you will not need to reference.
        oconnections -- set, all blocks where the output is connected to
        circuit -- Circuit object the block belongs to
        _output -- output value storage
        _output_events -- tuple of zero or more Events created
            from the 'on_output' argument. These events are
            to be sent when the output has changed. Following data
            is attached to each event:
                previous=<value before change>
                value=<current value>
                source=<sender block name>
    """
    def __init__(
            self, name: Optional[str], *,
            desc: Optional[str] = None, on_output: EventsArg = (), **kwargs):
        """
        Create a block. Add it to the circuit.

        'on_output' may be a single Event or multiple Events
        (see _is_multiple() for a definition)

        Keyword arguments starting with 'x_' or 'X_' are ignored.
        They are reserved for storing arbitrary application data
        as block attributes.
        """
        if name is not None:
            checkname(name, "block name")
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
        self.desc = desc or str(self)
        self.debug = False
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

        start() is called when the circuit simulation is about to
        start.

        Usage in CBlocks:
        By definition CBlocks should not require initialization.
        start typically just calls the check_signature().

        Usage in SBlocks:
        To setup resources, e.g. to create asyncio tasks. Note that
        init_regular() is the preferred place for initializing the
        block's internal state and output. start() is a distinct step
        preceding the initialization. However it is fully acceptable
        to initialize block's state in start(), provided that:
        - the block must define start() anyway.
        - the initialization does not start a timer or at least not
          a timer with a short duration. There might be a considerable
          delay (for async initialization) between start() and the
          rest of the circuit initialization. The timer could generate
          events during the delay or the delay could spoil timings.

        IMPORTANT: When using start() in subclasses, always call
        the super().start()
        """

    def stop(self) -> None:
        """
        Post-simulation hook.

        stop() is called when the circuit simulation has finished.
        Note that if an error occurs during circuit initialization,
        stop() may be called even when start() hasn't been called.

        An exception in stop() will be logged, but otherwise ignored.

        Usage in CBlocks:
        By definition CBlocks should not require cleanup, so stop
        is usually empty. A possible use might be gathering of some
        statistics data for instance.

        Usage in SBlocks:
        Cleanup, e.g. stop any asyncio tasks.

        IMPORTANT: When using stop() in subclasses, always call
        the super().stop().
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
        A dummy method. A placeholder for all optional methods.

        Key properties:
        1. it can be safely called as super().method(...)
           from any overriden method.
        2. has_method() returns False for this method
        """

    async def dummy_async_method(self, *args, **kwargs):
        """A dummy async method, see dummy_method."""

    def get_conf(self) -> Mapping[str, Any]:
        """Return comprehensive static info in form of a dict."""
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

    Attributes:
        i -- object providing access to input values
        i0, i1, i2 -- shortcuts for first 3 inputs
        inputs -- a dict of input and input groups by name
        iconnections -- set of all blocks where the inputs are
                        connected from, Const blocks excluded
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
        self.i = self.InputGetter(self)     # i.name and i[name] are two ways of getting
                                            # the value of the input or input group 'name'
        super().__init__(*args, **kwargs)

    def _get_input(self, index):
        try:
            return self.i['_'][index]
        except LookupError:     # LookupError = KeyError or IndexError
            raise LookupError(f"{self}: input #{index} not connected") from None

    @property
    def i0(self):   # pylint: disable=invalid-name
        """Shortcut: get the first unnamed input."""
        return self._get_input(0)

    @property
    def i1(self):   # pylint: disable=invalid-name
        """Shortcut: get the second unnamed input."""
        return self._get_input(1)

    @property
    def i2(self):   # pylint: disable=invalid-name
        """Shortcut: get the third unnamed input."""
        return self._get_input(2)

    def connect(self, *args, **kwargs):
        """
        Connect inputs and input groups.

        Inputs given as positional args (i.e. unnamed) will be stored
        as a group named '_'. This group is created only if unnamed
        inputs exist. Avoid '_' as a name for named inputs in kwargs.

        A single input could be entered as:
            - a Block object
            - name of a Block object
            - "_not_name" derived from another block's "name" as
              a shortcut for connecting a logically inverted output.
              A new block
                  Invert('_not_name').connect(name)
              will be created automatically if it does not exist
              already. The original name must not begin with an
              underscore. "_not__not_name" will not create an Invert.
            - a Const object
            - anything else except multiple inputs (see below),
              the value will be automatically wrapped into a Const

        To connect a single named input:
            name=input

        An empty name is a shortcut for connecting an eponymous block:
            foo='' is equivalent to foo='foo'

        To connect a group:
            name=multiple inputs, i.e. any sequence (e.g. tuple, list),
            or iterator of single inputs.

        connect() must be called before the circuit initialization
        takes place and may be called only once.

        All inputs must be connected. A group may have no inputs, but
        it must be explicitly connected as such: group=() or group=[].

        Return self in order to allow a 'fluent interface'.

        connect() only saves the block's input connections data.
        The circuit-wide processing of interconnections will take place
        in Circuit._init_connections().
        """
        self.circuit.check_not_frozen()
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

        The reserved group name '_' represents the group of unnamed
        inputs if any.
        """
        return {
            iname: len(ival) if isinstance(ival, tuple) else None
            for iname, ival in self.inputs.items()}

    def check_signature(self, esig: Mapping):
        """
        Check an expected signature 'esig' with the actual one.

        Edzed does not support optional inputs. For a successful check
        all keys in the 'esig' must match the actual keys from
        input_signature().

        In order to support variable input groups sizes, the expected
        size can be given also as a range of valid values using
        a sequence of two values [min, max] where 'max' may be None
        for no maximum. 'min' can be also None for no minimum, but
        zero - the lowest possible input count - has the same effect.

        Raise a ValueError with a helpful description of all
        differences if any mismatches are found.

        Examples of 'esig' items:
            'name': None        # a single input (not a group)
            'name': 1           # a group with one input, it is not
                                # the same as a single input!
            'ingroup': 4            # exactly 4 inputs
            'ingroup': [2, None]    # 2 or more inputs
            'ingroup': [0, 4]       # 4 or less
            'ingroup': [None, None] # input count doesn't matter

        Note: an input group may be empty (0 inputs), but must be
        explicitly connected as any other group, see connect().

        Return the input_signature() data for possible further analysis.
        """
        def setdiff_msg(actual, expected):
            """Return a message describing a diff of two sets of names."""
            unexpected = actual - expected
            missing = expected - actual
            msgparts = []
            if unexpected:
                subparts = []
                for name in unexpected:
                    suggestions = corrections.suggest_corrections(name, missing)
                    if suggestions:
                        top3 = ' or '.join(repr(s) for s in suggestions[:3])
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
        return {
            'inputs': {
                iname: tuple(g.name for g in ival) if isinstance(ival, tuple) else ival.name
                for iname, ival in self.inputs.items()},
            'type': 'combinational',
            **super().get_conf()
        }


@dataclass(frozen=True)
class EventCond(EventType):
    """
    A conditional event type.

    Roughly equivalent to:
        etype = etrue if value else efalse
    where the value is taken from the event data item ['value'].
    Missing value is evaluated as False, i.e. 'efalse' is selected

    None value means no event.

    This feature simplifies the block-to-block event interface.
    """
    __slots__ = ['etrue', 'efalse']
    etrue: Union[None, str, EventType]
    efalse: Union[None, str, EventType]


class SBlock(Block):
    """
    Base class for sequential blocks, i.e. blocks with internal state.

    The internal state and the output change in response to received
    events. See event().

    The internal state is returned by get_state(). The state of a
    basic SBlock object is identical to its output. A derived class
    with different internal state must customize its get_state().

    SBlocks do not have directly connected inputs as CBlocks do, but
    they can be connected indirectly using 'on_output' events.

    To setup/cleanup other resources (but not the internal state)
    use start() and its counterpart stop().

    SBlocks require initialization. For this purpose init_regular()
    method is provided. Other initialization methods are available
    as add-ons.

    A block is deemed initialized when its output value changes from
    UNDEF to any other value. i.e. after first set_output(). An
    initialized block must be able to process events.

    Using asyncio coroutines and tasks.
    -----------------------------------
    See the AddonAsync for asynchronous initialization and cleanup.
    Without the add-on, the support is limited to start()'s ability
    to create asynchronous tasks, because it is a regular function.

    See also other Addon* classes extending the SBlocks' capabilities.
    """

    def __init_subclass__(cls, *args, **kwargs):
        """
        Verify that all add-ons precede the SBlock in the class hierarchy.

        This is important for a correct order of method calls.

        When defining a new class derived from SBlock:
            class NewBlock(Addon1, Addon2, SBlock): ...     # correct
            class NewBlock(Wrong, Addon1, Addon2): ...      # wrong!
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
        """
        Process the 'initdef' keyword argument.

        'initdef' specifies the initial internal state. Its precise
        meaning varies depending on SBlock:
            A. initdef is not accepted, because the internal state
               is not adjustable (e.g. determined by date or time)
            B. initdef is the main initial value generally used
               to initialize the block
            C. initdef is the default value just for the case
               the regular initialization fails

        The initdef value is saved as a attribute.

        To enable the initdef keyword argument a supporting method
        named init_from_value() is required.

        Synopsis:
            def init_from_value(self, value):

        Description:
            Initialization from a constant is expected to be error free
            in general. Nevertheless if it is not possible to initialize
            the block, leave it uninitialized and return.

            Unlike start() it is usually not necessary to call
            super().init_from_value(), because once the block is
            initialized, there is nothing left to do.
        """
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

        ******************************************************
        **  event() is the circuit's data input interface.  **
        ******************************************************

        The block may change its state and its output in response
        to the event.

        The block may return an arbitrary value. The simulator
        makes no use of the returned value except checking for
        the NotImplemented special value.

        An event may require specific event data to be passed with
        the event. Any additional data not needed by the event must
        be silently ignored.

        If an event is unknown, return the NotImplemented constant.
        (do not return or raise the NotImplementedError exception!)
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
    #   block.event('foo', event=1)         # TypeError
    #
    # pylint: disable=no-method-argument, protected-access
    def event(*args, **data) -> Any:
        """
        Error handling wrapper, see _event for function usage.

        Evaluate so called conditional events. See the EventCond class.

        Respond with ValueError to unknown event types unless the error
        is explicitly disabled with '_ignore_unknown=True' added to
        event data. If the error is disabled, NotImplemented is returned
        for unknown events.

        Handle the received event ETYPE:
            - invoke the specialzed _event_ETYPE() method if such
              method exists; otherwise
            - invoke the general _event() method
        Note the different signatures:
            def _event_ETYPE(self, **data)
            def _event(self, etype, data)

        When an error occurs during the event handling, raise and if the
        event was not called from within the simulator task, also abort
        the simulator. An unkown event error described above is not
        considered an event handling error and will not abort the
        simulation if event() was called from other task.

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
            if isinstance(etype, EventCond):
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
                if not data.get('_ignore_unknown', False):
                    raise ValueError(f"Unknown event type '{etype}'")
                self.warn(f"unknown event type '{etype}' ignored")
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
        """put(x) is a shortcut for event(put, value=x)."""
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

        If the block gets its initialization elsewhere, leave
        this function empty.

        If it is not possible to initialize the block, leave it
        uninitialized and return.

        Unlike start() it is usually not necessary to call
        super().init_regular(), because once the block is
        initialized, there is nothing left to do.
        """

    # optional methods
    init_async = Block.dummy_async_method
    stop_async = Block.dummy_async_method
    init_from_value = Block.dummy_method

    def get_conf(self) -> Mapping[str, Any]:
        return {
            'type': 'sequential',
            **super().get_conf()
        }


# importing at the end when all names are defined resolves a circular import issue
# pylint: disable=wrong-import-position
from . import simulator

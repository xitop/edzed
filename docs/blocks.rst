.. currentmodule:: edzed

==============
Circuit blocks
==============

There are two types of building blocks.
Each block is either **combinational** or **sequential**.
The main differences are:

.. csv-table::
  :header: "combinational", "sequential"

  "has **inputs**", "does not have inputs"
  "does not have internal state", "has **internal state** (memory, time) and thus requires initialization"
  "does not accept events", "accepts **events**"
  "can generate events only on output change", "can generate events also on internal state changes"


Common features
===============

Regardless of type, every block has the following properties:

.. class:: Block(name: Optional[str], *, desc: str = "", on_output=(), debug: bool = False, **kwargs)

  :class:`Block` is the base class for all blocks.
  It cannot be instantiated directly.

  .. important::

    Each created block is automatically added to the current circuit.

  Mandatory arguments:

  The *name* is block's unique identifier, a non-empty string.

  Names prefixed by an underscore are reserved for automatically created
  blocks and names.

  Enter ``None`` to request a generated name.
  Use this feature only for auxiliary blocks that you will not need
  to reference by name.

  Optional arguments:

  *desc* (block's description) is any arbitrary text.
  It is not used internally.

  The *on_output* argument specifies :ref:`events<Events>` to be sent on each
  output change. More details in :ref:`generating events<Generating events>` below.

  The *debug* argument initializes the *debug* attribute.

    .. versionadded:: 21.1.30 *debug*

  Keyword arguments starting with ``'x_'`` or ``'X_'`` are accepted and stored as
  block's attributes. These names are reserved for storing arbitrary
  application data.

  Overview of common attributes and methods,
  more details can be found :ref:`here <Inspecting blocks>`:

  .. attribute:: name
    :noindex:

    Block's name.

  .. attribute:: desc
    :noindex:

    Block's description.

  .. attribute:: output
    :noindex:

    Block's output value.

  .. attribute:: debug
    :noindex:

    Boolean, enable :ref:`logging of block's debugging information<Circuit block debug messages>`.

  .. method:: get_conf
    :noindex:

    Return static block information such as the name and type.

  .. method:: __str__

    The string representation of a block is ``"<Type 'name'>"``.


Combinational blocks
====================

The output of a combinational block depends only on its present input values.

.. class:: CBlock(*args, **kwargs)

  The base class for combinational blocks does not
  add any new arguments compared to :class:`Block`.

  .. method:: connect(*unnamed_inputs, **named_inputs)

    Connect block's inputs. Return ``self`` in order to allow a 'fluent interface'.

    An input is either a single input or a multiple input called group.
    A group consists of any number (zero or more) of single inputs.

    All inputs given as positional arguments (i.e. unnamed) will be stored
    as a group named ``"_"``. This group is created only if unnamed
    inputs exist, i.e. it cannot be empty.

    All inputs given as keyword arguments will have the given names.
    Avoid the reserved name ``"_"``.

    To connect a single named input, add a keyword argument::

      name=<single_input>  # see below

    An empty name is a shortcut for connecting an eponymous block:
    ``foo=''`` is equivalent to ``foo='foo'`` (connect output of ``foo``
    to the input named ``foo``).

    To connect a group::

      name=<multiple_inputs>  # any sequence (tuple, list, ...), or iterator of single inputs

    A single input could be connected:

    1. to another block's output specified with:

       - a :class:`Block` object

       - the name of a Block object

       - ``"_not_name"`` derived from another block's name by prepending
         a ``"_not_"`` prefix. This is a shortcut for connecting a logically
         inverted output. A new block::

          edzed.Invert('_not_name').connect(name)

         will be created automatically if it does not exist
         already. The original name must not begin with an
         underscore; ``"_not__not_name"`` will not create an :class:`Invert`.

    2. or to a constant value given as:

       - a :class:`Const` object

       - any ``value`` that does not specify an input or a group,
         i.e. not a string, tuple, list or similar.
         The value will be automatically wrapped into a :class:`Const`.
         If not sure, use ``Const(value)`` explicitly.

    :meth:`connect` must be called before the circuit initialization
    takes place and may be called only once.

    All block's inputs must be connected. A group may have no inputs, but
    it must be explicitly connected as such: ``group=()`` or ``group=[]``.

.. class:: Const(value: Any)

  A pseudo-block with a constant value on its output. ``Const`` objects
  are not registered as members of the circuit.


Sequential blocks
=================

Base class arguments
--------------------

.. class:: SBlock(*args, **kwargs)

  Arguments accepted by the :class:`SBlock` are not uniform.
  Refer to descriptions of individual blocks for details
  which arguments from the list below are appropriate.
  All arguments are keyword arguments and are optional
  unless noted otherwise.

  - Setting the initial state:
      Argument *initdef* specifies the initial internal state.
      Its precise meaning varies depending on the block:

      1. *initdef* is not accepted, because the internal state
         is not adjustable (e.g. determined by current date or time).
      2. *initdef* is the primary initial value used
         to initialize the block. In this case is the argument
         mandatory for the given block.
      3. *initdef* is the default value just for the case
         the regular initialization fails. In this case is the argument
         still optional, but highly recommended for the given block.

      If accepted, the *initdef* value is saved as an attribute.

  - Enabling persistent state:
      Several blocks support persistent state, i.e.
      their internal state is saved (most likely to a file) when
      the application stops and is restored on next start.

      This feature is controlled by two boolean flags:

      - *persistent*
         Enable the persistent state. Default is ``False``.

      - *sync_state*:
         Save the state also after each event. Default is ``True``.

      The :ref:`persistent data storage<Storage for persistent state>`
      must be provided by the circuit.

  - Timeout for asynchronous initialization and cleanup:
      Some blocks perform asynchronous operations. These
      arguments control the timeouts:

      - *init_timeout*:
         initialization timeout in seconds.
         Default timeout is 10 seconds.
         Value 0.0 or negative disables the async initialization.

      - *stop_timeout*:
         cleanup timeout in seconds.
         Default timeout is 10 seconds.
         Value 0.0 or negative disables the async cleanup.

      The timeout values must be given as a number (:class:`int`, :class:`float`)
      or ``None`` for the default timeout.


Internal state
--------------

The internal state consists of all data a sequential block maintains
in order to correctly perform the task it was designed to.

In its simplest form is the internal state equal to the output value.
Such blocks (e.g. :class:`Input`) act like a memory cell.

The internal state is affected by:

- events sent from other blocks,
- events coming from external sources,
- the block's own activity like timers, or
  readouts of sensors and gauges


Initialization
--------------

By definition a block is deemed initialized when its output
is not :const:`UNDEF`. The output is closely related to the internal
state, so block initialization basically means internal state
initialization.

Blocks are initialized at the beginning of circuit simulation.

The initialization process is carried out in consecutive steps
listed below until one of the steps succeeds to initialize the block.

Each block defines only those steps that are appropriate.

1. by the asynchronous initialization routine defined in the block's class
   (subject to *init_timeout* parameter);
   this step is skipped if an incoming event is pending
2. from saved persistent data
3. by the regular (i.e. not async) initialization routine
   defined in the block's class
4. from the *initdef* parameter
5. as a result of an incoming event triggered by
   other circuit block's initialization

   .. note:: An incoming event is always processed.
      It is listed here because some circuits
      rely on the side effect of setting the internal
      state.

The simulation fails if any block remains uninitialized.


Events
------

Events play a key role in sequential blocks' operation.

An event is a message addressed to a destination block.
It has a type and optional data. For example a common event type
is ``'put'``. By convention ``'put'`` events are always sent with
a ``'value'`` data item.

Events may be generated internally by circuit blocks or may originate from
external systems and be forwarded through some sort of input interface.

Receiving events
^^^^^^^^^^^^^^^^

An event is delivered by calling the :meth:`SBlock.event` method
of the destination block.

.. method:: SBlock.event(etype: Union[str, EventType], /, **data) -> Any

  Handle the event of type *etype* with attached *data* items (key=value pairs).

  In particular:

  - update the internal state, and
  - set the output value

  according to the block's rules.

  The event type *etype* is either a plain string identifier (a name)
  or an :ref:`event type<Event types>` object.

  .. note::

    *etype* is a positional-only parameter,
    see `PEP-570 <https://www.python.org/dev/peps/pep-0570/>`_.
    This is a new feature in Python 3.8, but
    the current code emulates it also in Python 3.7.

  :meth:`event` may return a value of any type except the ``NotImplemented``
  Python constant reserved for internal use. Other blocks ignore the returned
  value, but it may be useful for input interfaces to external systems.

  Accepted event types together with required data and returned values for each
  supported event type are part of the API for each particular block type.

  A block must ignore any additional data items.

  .. warning::

    If an exception (other than an unknown event type or a trivial parameter error)
    is raised during event handling, the simulation terminates with an error
    even if the caller handles the exception with a ``try-except`` construct.
    This is a measure to protect the integrity of internal state.

.. method:: SBlock.put(value: Any, **data) -> Any

  This is a shortcut for the frequently used ``event('put', value=value, ...)``.

Generating events
^^^^^^^^^^^^^^^^^

Every block (even a combinational one) can generate events on its
output change, so let's show the details on an example with ``on_output``.
Other generated events differ only in the trigger condition and in the
event data sent with the event.

The event type and the destination are set in the sender block's configuration::

   ExampleBlock(
      'block1', desc="example of sending put events to block2",
      on_output=edzed.Event(block2, 'put'))

.. important::

  Parameters instructing a block to send events in
  certain situations have names starting with an ``"on_"`` prefix.
  They accept either an :class:`Event` object or multiple (zero or more)
  Events objects given as a tuple, list or other sequence.

.. class:: Event(dest: Union[str, Block], etype: nion[str, EventType] = 'put', efilter=())

  Specify an event of type *etype* addressed to the *dest* block
  together with optional event filters to be applied.

  The *dest* argument is an :class:`SBlock` object or its name.

  :ref:`Event filters` are functions (*callables* to be exact) documented below. The *efilter* argument
  can be a single function or a tuple, list or other sequence of functions.

  .. method:: send(source: Block, /, **data) -> bool

    Apply filters and send this event with the given data.

    ``source=<block name of source>`` item is added to the event data.

    Return ``True`` if the event was sent, ``False`` if rejected by a filter

    .. note::

      block-to-block events are one-way communication. The return
      value from the :meth:`SBlock.event` is disregarded.

    .. note::

      *source* is a positional-only parameter,
      see `PEP-570 <https://www.python.org/dev/peps/pep-0570/>`_.
      This is a new feature in Python 3.8, but
      the current code emulates it also in Python 3.7.



Data describing the event is added each time a new event is triggered.
``on_output`` events are sent with three data items:

- ``'previous'`` = previous value (:const:`UNDEF` on first change after initialization)
- ``'value'`` = current output value
- ``'source'`` = sender's block name, which is always added

Thus, when the output of ``block1`` from our example changes e.g. from ``23`` to ``27``,
following code will be executed::

   block2.event('put', previous=23, value=27, source='block1')

Event types
^^^^^^^^^^^

A simple name (string) is commonly used to identify the event type.

Occasionally a string is not suitable to fully identify
more complex events. For those few cases we use event type objects
instead of names.

There is only one such event type for general use.
It's the conditional event simplifying the block-to-block event delivery:

.. class:: EventCond(etrue, efalse)

  A conditional event type, roughly equivalent to::

    etype = etrue if value else efalse

  where the ``value`` is taken from the event data item ``'value'``.
  Missing ``value`` is evaluated as ``False``, i.e. ``efalse`` is selected.

  ``None`` as *etrue* or *efalse* means no event in that case.

Event filters
^^^^^^^^^^^^^

Event filters serve two purposes. As the name suggests, they can filter out
an event, i.e. cancel its delivery. The second use is to modify the filter data.

An event filter function is called with the event data
as its sole argument (i.e. as a :class:`dict`).

- If it returns a :class:`dict`, the event is accepted and the returned
  dict becomes the new event data.

- If the function returns anything else than a :class:`dict` instance,
  the event will be accepted or rejected depending on the boolean value
  of the returned value (true = accept, false (e.g. ``False`` or ``None``) = reject).

  .. versionchanged:: 20.9.5
     every non-dict return value did mean a reject in previous releases.

Event filters may modify the event data in-place.

Multiple filters are called in their definition order like a *pipeline*.

Event filters are usually very simple, often an "one-liner" or a ``lambda``
is all it takes.

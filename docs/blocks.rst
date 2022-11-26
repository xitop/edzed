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
  "does not have an internal state", "has an **internal state** (memory, time) and thus requires initialization"
  "does not accept events", "accepts **events**"
  "can generate events only on output change", "can generate events also on internal state changes"


Common features
===============

.. class:: Block(name: Optional[str], *, comment: str = "", on_output=None, debug: bool = False, **x_kwargs)

  Create a block and add it to the current circuit.

  The ``Block`` implements common features of all circuit blocks, combinational and sequential.
  It cannot be instantiated directly (it is an *abstract* class).
  Concrete blocks must be derived either from the combinational
  base class :class:`CBlock` or from the sequential base class :class:`SBlock`.

  The mandatory argument *name* is block's unique identifier, a non-empty string.
  Names prefixed by an underscore are reserved for automatically created
  blocks. Enter ``None`` to request a generated name;
  use this feature only for auxiliary blocks that you will not need
  to reference by name.

  The optional *comment* may be any arbitrary text and is not used internally.

  The optional *on_output* argument specifies :ref:`events<Events>` to be sent on each
  output change.

  The *debug* argument initializes the *debug* attribute.

  All keyword arguments starting with ``'x_'`` or ``'X_'`` are accepted
  and stored as block's attributes. These names are reserved for storing
  arbitrary application data.

  Keyword arguments other than those mentioned above are not accepted.

  ---

  Following attributes and methods are defined.
  Do not modify any block attributes unless explicitly permitted.

  .. attribute:: circuit
    :type: Circuit

    The :class:`Circuit` object the block belongs to. Usually there is
    only one circuit. An application code should use :func:`get_circuit`
    to get a reference to it.

  .. attribute:: comment
    :type: str
    :value: ""

    Block's text description or comment. May be modified.

  .. attribute:: debug
    :type: bool
    :value: False

    Allow this block to :ref:`log debugging messages<Circuit block debug messages>`.
    May be modified.

  .. attribute:: name
    :type: str

    The assigned block's name.

  .. attribute:: output
    :type: Any

    Block's output value, a read-only property.

    Each block has exactly one output value of any type.

    A special :const:`UNDEF` value is assigned to newly created blocks.

  .. attribute:: x_anyname
    :type: Any
  .. attribute:: X_ANYNAME
    :type: Any

    (with any arbitrary name) Reserved for application data, ignored by ``edzed``.
    May be added/removed/modified.

  .. method:: get_conf() -> dict[str, Any]

    Return a summary of static block information.

    Example output::

      {
        'class': 'Counter',
        'debug': False,
        'comment': '',
        'name': 'cnt1',
        'persistent': False,
        'type': 'sequential'
      }

    All items are self-explaining. Not applicable items are excluded,
    e.g. 'inputs' is shown for combinational blocks in a finalized circuit only.
    New items may be added in future releases.
    Note that items like *name* or *comment* can be accessed also as block attributes.

.. data:: UNDEF

  A constant representing an undefined output. All other output values
  are valid, including ``None``. It is an error when ``edzed.UNDEF``
  value appears on block's output after the circuit initialization.


Constants
=========

.. class:: Const(value: Any)

  A pseudo-block with a constant *value* on its output. ``Const`` objects
  are not registered as members of the circuit and are not derived from
  the :class:`Block` base class.

  .. attribute:: name
    :type: str

    The automatically generated block's name.

  .. attribute:: output

    Block's constant output value, a read-only property.


Combinational blocks
====================

The output of a combinational block depends only on its present input values.

.. class:: CBlock(name, **block_kwargs)

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

      name=<single_input>  # defined below

    To connect a group::

      name=<multiple_inputs>  # any sequence (tuple, list, ...)
                              # or an iterator of single inputs

    A single input could be connected:

    1. to another block's output specified with:

      - a :class:`Block` object

      - the name of a Block object (string)

      - ``'_not_NAME'`` for connecting the :ref:`logically inverted output<Inverted output>`
        of another block.

    2. or to a constant value given as:

      - a :class:`Const` object

      - any ``value`` that does not specify an input or a group,
        i.e. not a string, tuple, list or similar.
        The value will be automatically wrapped into a :class:`Const`.

      It is recommended to use ``Const(value)`` explicitly for all
      values except the ``None``, ``True``, ``False`` and numbers.

    :meth:`connect` must be called before the circuit initialization
    takes place and may be called only once.

    All block's inputs must be connected. A group may have no inputs, but
    it must be explicitly connected as such: ``group=()`` or ``group=[]``.


Sequential blocks
=================

.. class:: SBlock(name, *, initdef=edzed.UNDEF, persistent=False, sync_state=True, expiration=None, init_timeout=None, stop_timeout=None, on_every_output=None, **block_kwargs)

  The base class for all sequential blocks. A subclass of :class:`Block`.

  The  optional argument *on_every_output* specifies :ref:`events<Events>` to be
  sent on each output event. It differs slightly from the *on_output*,
  more details in :ref:`output events<Output events>`.

  .. important::
    Only applicable arguments from the list below are accepted by concrete
    sequential block types. Refer to descriptions of individual blocks for details
    which arguments are supported by the given block.

  - Setting the initial state:
      Argument *initdef* (type: Any) specifies the initial or the default internal state.
      Its precise meaning varies depending on the block:

      - *initdef* is not accepted, because the internal state
        is not adjustable (e.g. determined by current date or time).
      - *initdef* is the primary initial value used
        to initialize the block. In this case is the argument
        mandatory for the given block.
      - *initdef* is the default value just for the case
        the regular initialization fails. In this case is the argument
        optional, but highly recommended for the given block.

      If accepted, the *initdef* value is saved as an attribute:

      .. attribute:: initdef
        :type: Any

        Saved value of the *initdef* argument or :const:`UNDEF`,
        if the argument was not given. Only present if the block
        accepts this argument. This attribute allows to implement
        a *reset* if need be.


  - Enabling persistent state:
      Persistent state means that the internal state is saved (most likely
      to a file) when the application stops and is restored on the next start.
      The data persistence is only possible in a circuit having a proper
      :ref:`persistent storage<Storage for persistent state>`. The settings
      below will have no effect without the storage.

      If a block supports this feature, it is controlled by these
      parameters:

      - *persistent* (bool):
          Enable the persistent state. Default is ``False``.

      - *sync_state* (bool):
          Save the state also after each event. Default is ``True``.

      - *expiration* (int or float or str or None):
          Expiration time measured since the program stop. An expired
          state is disregarded. Expiration value may be ``None``,
          number of seconds, or
          a :ref:`string with time units<Time intervals with units>`.

          The *expiration* value defaults to ``None`` which means
          that the saved state never expires.

  - Timeouts for asynchronous initialization and cleanup:
      Some blocks perform asynchronous operations. These
      arguments control the timeouts:

      - *init_timeout* (int or float or str or None):
         initialization timeout in seconds.
         Default timeout is 10 seconds.
         Value 0.0 or negative disables the async initialization.

      - *stop_timeout* (int or float or str or None):
         cleanup timeout in seconds.
         Default timeout is 10 seconds.
         Value 0.0 or negative disables the async cleanup.

      The timeout values must be given as a number of seconds,
      ``None`` for the default timeout, or
      a :ref:`string with time units<Time intervals with units>`.

      The timeouts should be explicitly set. A warning is logged,
      when the default is used.


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
During the process available block's sources of the initial state
are utilized in the order listed below. Which sources are defined
depends on the particular block.

1. from saved persistent data
2. by the asynchronous initialization routine;
   this step is skipped if an incoming event (see item 5) is pending
3. by the regular (i.e. not async) initialization routine
4. only if still not initialized: from the *initdef* parameter;
5. as a result of an incoming event triggered by
   other circuit block's initialization

When the routines from list items 2 and 3 are called, the block
may have been initialized already. In such case the routine may
keep the state or it may overwrite it.

The simulation fails if any block remains uninitialized.

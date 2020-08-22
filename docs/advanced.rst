===============
Advanced topics
===============

Feel free to skip this chapter or some of its sections.
Perfect ``edzed`` based applications can be written without
the information contained here.


Multiple circuits
=================

``edzed`` was deliberately designed to support only one active circuit at a time.

There cannot be multiple circuit simulations in parallel,
but it is possible to remove the current circuit and start over with
building of a new one.

.. function:: edzed.reset_circuit()

  Clear the circuit and create a new one.

  The simulation will be aborted if it is running. The simulation
  tasks should be awaited to ensure a proper cleanup as explained
  :ref:`here <Stopping the simulation>`.

  .. warning::

    A process restart is preferred over the circuit reset.
    A new process guarantees a clear state.

    A reset relies on the quality of cleanup routines. It cannot
    fully guarantee that the previous circuit has closed all files,
    cancelled all tasks, etc. Remember that the I/O routines
    are supplied mainly by the application.


Creating combinational blocks
=============================

As noted elsewhere, the :class:`edzed.FuncBlock` is an universal
combinational block and there is almost no reason to write a new one.

Instructions for creating a new CBlock:

- subclass from :class:`edzed.CBlock`
- define :meth:`edzed.CBlock._eval`
- optional: define :meth:`edzed.CBlock.start` and :meth:`edzed.CBlock.stop`

.. method:: edzed.CBlock._eval() -> Any
  :abstractmethod:

  Compute and return the output value.

.. attribute:: edzed.CBlock._in

  An object providing access to input values.

  An input value can be retrieved using the input name as a key ``self._in['myinput']``
  or as an attribute ``self._in.myinput``.

  The result is a single value or a tuple of values, if the input is a group.

.. method:: edzed.CBlock.start() -> None

  Pre-simulation hook.

  :meth:`start` is called when the circuit simulation is about to start.

  By definition CBlocks do not require any preparations.
  :meth:`start` typically just checks the :ref:`input signature <Input signatures>`.

  .. important::

    When using :meth:`start`, always call the ``super().start()``.

.. method:: edzed.CBlock.stop() -> None

  Post-simulation hook.

  :meth:`stop` is called when the circuit simulation has finished.

  By definition CBlocks do not require cleanup, so :meth:`stop`
  is usually not used. A possible use-case might be for instance retrieval
  of some gathered statistics data.

  Note that if an error occurs during circuit initialization,
  :meth:`stop` may be called even when :meth:`start` hasn't been called.

  An exception in :meth:`stop` will be logged, but otherwise ignored.

  .. important::

    When using :meth:`stop`, always call the ``super().stop()``


Input signatures
----------------

An input signature is a :class:`dict` with the following structure:

- key: the input name (string)
    The reserved group name ``'_'`` represents the group of unnamed inputs, if any.

- value: ``None`` or integer:

  - ``None``, if the input is a single input
  - the number of inputs in a group, if the input is a group

.. method:: edzed.CBlock.input_signature() -> dict

  Return the input signature. The data is available only after
  the simulation start.

.. method:: edzed.CBlock.check_signature(esig: Mapping) -> dict

  Compare the expected signature *esig* with the actual one.

  For a successful result items in the *esig* and
  items from :meth:`edzed.CBlock.input_signature` must match.

  If no problems are detected, the input signature data for possible further analysis
  is returned.

  If any mismatches are found, a :exc:`ValueError` with a description
  of all differences (missing items, etc.) is raised. :meth:`check_signature`
  tries to be really helpful in this respect, e.g. it provides suggestions
  for probably mistyped names.

  In order to support variable input group sizes, the expected
  size can be given also as a range of valid values using
  a sequence of two values ``[min, max]`` where ``max`` may be ``None``
  for no maximum. ``min`` can be also ``None`` for no minimum, but
  zero - the lowest possible input count - has the same effect.

  Examples of *esig* items::

    'name': None    # a single input (not a group)
    'name': 1       # a group with one input (not a single input)
    'ingroup': 4            # exactly 4 inputs
    'ingroup': [2, None]    # 2 or more inputs
    'ingroup': [0, 4]       # 4 or less
    'ingroup': [None, None] # input count doesn't matter


Example (Invert)
----------------

:class:`edzed.Invert` source::

  class Invert(edzed.CBlock):
      def _eval(self):
          return not self._in['_'][0]

      def start(self):
          super().start()
          self.check_signature({'_': 1})


Creating sequential blocks
==========================

Instructions for creating a new SBlock:

- subclass from :class:`edzed.SBlock` and appropriate :ref:`add-ons <Add-ons>`
- define :ref:`event handlers <Event handlers>`
- define :ref:`state related methods <State related methods>`
- define :ref:`start and stop methods <Start and stop>`

Before we dive into details, let's recap the :ref:`initialization order <Initialization>`
with links to corresponding sections added. Each block defines only those steps that are
appropriate to its functionality.

1. asynchronous initialization routine
     see: :class:`edzed.AddonAsync` and :meth:`edzed.SBlock.init_async`
2. from persistent data
     see: :class:`edzed.AddonPersistence` and :meth:`edzed.SBlock._restore_state`
3. regular initialization routine
     see :meth:`edzed.SBlock.init_regular`
4. from the *initdef* value
     see :meth:`edzed.SBlock.init_from_value`

.. important::

  The general rule for all four listed initialization functions:
  If it is not possible to initialize the block, leave it
  uninitialized and return. Do not raise on errors, only log
  a notice.


Event handlers
--------------

There are two ways to handle :ref:`events <Events>`:

1. Add specialized event handlers.

  .. method:: edzed.SBlock._event_ETYPE(**data) -> Any

    If a method with matching event type ``'ETYPE'`` is defined,
    it will be called to handle that event type.

  For example: :meth:`_event_put` will be called for all ``'put'`` events.

  .. note::

    This way a non-FSM event can be added to an FSM block, if need be.
    Take care not to interfere with the FSM operations.

  Customize the method signature to extract the expected event data.
  Always accept unused additional data (``**_data`` in the examples below).
  Examples::

    # event 'dec' accepts optional data item 'amount'
    def _event_dec(self, *, amount=1, **_data):
       ...

    # event 'put' requires data item 'value'
    def _event_put(self, *, value, **_data):
       ...

2. Utilize the default event handler.

  .. method:: edzed.SBlock._event(etype, data) -> Any

    :meth:`_event` will be called for events without a specialized event handler.

    Return :const:`NotImplemented` to indicate an unknown event type. Return
    anything else for recognized event types.

    Example::

      def _event(self, etype, data):
          if etype == 'ying':
              # handle event ying here
              return None

          if etype == 'yang':
              # handle event yang here
              return None

          # let the parent handle everything else,
          # the base class simply returns NotImplemented
          return super()._event(event, data)

Do not confuse the internal method :meth:`_event` with the API method :meth:`event`.
The latter should be left untouched.
The :meth:`edzed.SBlock.event` is responsible for:

- resolving the conditional events (see :class:`edzed.EventCond`)
- dispatching events to a proper handler
- translating :const:`NotImplemented` to raised :exc:`ValueError`
- aborting the simulation on error

.. note::

  Note the different ways the event data is passed to a handler::

    def _event_ETYPE(self, **data):  # as keyword args
    def _event(self, etype, data):   # as a dict


Setting the output
------------------

Event handlers and initialization functions manage the internal
state and the output value. The output setter is:

.. method:: edzed.SBlock.set_output(value: Any) -> None

  Set the output value. The *value* must not be :const:`edzed.UNDEF`.

  A block is deemed initialized when its output value changes from
  :const:`edzed.UNDEF` to any other value. i.e. after
  the first :meth:`set_output` call.


State related methods
---------------------

.. method:: edzed.SBlock.get_state() -> Any
  :noindex:

  Return the internal state.

  The default implementation assumes the state is equal to the output.

  This method *must* be redefined for more complex SBlocks
  to return the real internal state.

  It is recommended that this method produces JSON serializable data,
  especially when the block supports persistent state.
  JSON serializable data can be stored or transfered with minimum
  difficulties.

.. method:: edzed.SBlock.init_regular() -> None

  Initialize the internal state to a fixed value and set the output.

  Define only if the block can be initialized this way.

.. method:: edzed.SBlock.init_from_value(value) -> None

  Initialize the internal state from the given *value*
  and set the output.

  Define only if the block can be initialized this way.

  Defining this method automatically enables
  :class:`edzed.SBlock`\'s keyword argument *initdef*.


Start and stop
--------------

:meth:`start` is called when the circuit simulation is about to start,
before the block initialization;
:meth:`stop` is called when the circuit simulation has finished.

.. method:: edzed.SBlock.start() -> None

  Pre-simulation hook.

  Set up resources necessary for proper function of the block.
  Do not set the internal state here.

  .. important::

    When using :meth:`start`, always call the ``super().start()``.

  .. note::

    Why do we need :meth:`start` when we have :meth:`__init__`?

    Only the :meth:`start` is the right place for actions that:

    - have a side effect, or
    - are resource intensive (time, memory, CPU), or
    - require an asyncio event loop

    What we want to achieve is that blocks may be created at import time,
    i.e. defined at the module level. Importing such module should not
    have any negative effects.

.. method:: edzed.SBlock.stop() -> None

  Post-simulation hook.

  This is a function dedicated for cleanup actions.
  It's a counterpart of :meth:`edzed.SBlock.start`.

  If an error occurs during circuit initialization,
  :meth:`stop` may be called even when :meth:`start` hasn't been called.

  An exception in :meth:`stop` will be logged, but otherwise ignored.

  .. important::

    When using :meth:`stop`, always call the ``super().stop()``


Add-ons
-------

.. important::

  In the list of new block's bases always put the add-on classes
  before the :class:`edzed.SBlock`::

    class NewBlock(edzed.AddonPersistence, edzed.SBlock): ...


Persistent state add-on
+++++++++++++++++++++++

.. class:: edzed.AddonPersistence

  Inheriting from this class adds a persistent state.

  The internal state (as returned by :meth:`edzed.SBlock.get_state` can be
  saved to persistent storage provided by the circuit. Instances can enable
  persistent state feature with the *persistent* keyword argument.

  If enabled, the state is saved:

  - by calling :meth:`save_persistent_state` explicitly
  - at the end of a simulation
  - by default also after each event; this can be disabled
    with *sync_state* keyword argument.

  Saving of persistent state is disabled after an error in :meth:`edzed.SBlock.event`
  in order to prevent saving of possibly corrupted state.

  .. method:: save_persistent_state()

    Save the internal state to persistent storage.

    This method is usually called by the simulator.

For state restoration :meth:`_restore_state` must be implemented.
The simulator retrieves the saved state from the persistent storage
and passes it as an argument.

.. method:: edzed.SBlock._restore_state(state: Any) -> None
  :abstractmethod:

  Initialize by restoring the *state* (presumably created by :meth:`get_state`)
  and the corresponding output.

  Note that :meth:`_restore_state` is sometimes identical with
  :meth:`edzed.SBlock.init_from_value`.

.. attribute:: edzed.SBlock.key

  The persistent dict key associated with this block. It equals the string representation
  ``str(self)`` - see :meth:`edzed.Block.__str__` - but this may be changed in the future.


Async add-on
++++++++++++

.. class:: edzed.AddonAsync

  Inheriting from this class adds asynchronous support, in particular
  asynchronous initialization and asynchronous cleanup.

  This class also implements a helper for general use:

  .. method:: _task_wrapper(coro: Awaitable, is_service: bool = False) -> Any
    :async:

    A coroutine wrapper delivering exceptions to the simulator.

    Coroutines marked as services (*is_service*  is ``True``) are supposed
    to run until cancelled - even a normal exit is treated as an error.

    Cancellation is not considered an error, of course.

.. method:: edzed.SBlock.init_async()
  :async:

  Optional async initialization coroutine, define only when needed.

  The async initialization is intended to interact with external
  systems and as such should be utilized solely by circuit inputs.

  The existence of this method automatically enables the *init_timeout*
  :class:`edzed.SBlock` keyword argument.

  :meth:`init_async` is run as a task and is waited for *init_timeout*
  seconds. When a timeout occurs, the task is cancelled and the
  initialization continues with the next step.

  Implementation detail: The simulator may wait longer than
  specified if it is also concurrently initializing another
  :class:`edzed.AddonAsync` based block with a longer *init_timeout*.

  .. important::

    Should an event arrive during the async initialization, the block
    will get a regular synchronous initialization in order to
    be able to process the event immediately. For this reason,
    when :meth:`init_async` asynchronously obtains the initialization value,
    it should check whether the block is still uninitialized before applying
    the value.

.. method:: edzed.SBlock.stop_async()
  :async:

  Optional async cleanup coroutine, define only when needed.

  The existence of this method automatically enables the *stop_timeout*
  :class:`edzed.SBlock` keyword argument.

  This coroutine is awaited after the regular :meth:`edzed.SBlock.stop`.

  :meth:`stop_async` is run as a task and is waited for *stop_timeout*
  seconds. When a timeout occurs, the task is cancelled.
  The simulator logs the error and continues the cleanup.

  .. tip::

    Use :func:`edzed.utils.shield_cancel.shield_cancel` to protect small
    critical task sections from immediate cancellation.


Main task add-on
++++++++++++++++

.. class:: edzed.AddonMainTask

  A subclass of :class:`edzed.AddonAsync`. In addition to :class:`AddonAsync`\'s
  features, inheriting from this add-on adds support for a task running from
  simulation start to stop.

  The add-on manages everything from start to stop including
  task monitoring. If the task terminates before stop,
  the simulation will be aborted.

  Adjust the *stop_timeout* if necessary. Note that the *init_timeout* does
  not apply to the task, because task creation is a regular function.

  .. method:: _maintask()
    :abstractmethod:
    :async:

    The task coroutine.


Example (Input)
---------------

An input block like :class:`edzed.Input`, but without data validation::

  class Input(edzed.AddonPersistence, edzed.SBlock):
      def init_from_value(self, value):
          self.put(value)

      def _event_put(self, *, value, **_data):
          self.set_output(value)
          return True

      _restore_state = init_from_value


Helper methods
==============

When creating new blocks, you may find these methods useful:

.. method:: edzed.Block.is_initialized() -> bool

  Return ``True`` only if the block has been initialized.

  This method simply checks if the output is not :const:`edzed.UNDEF`.

.. method:: edzed.Block.log(msg: str, *args, **kwargs) -> None

  Log a debug message.

  If :ref:`debug messages <Circuit block debug messages>`
  are enabled for this block, the block name is prepended to the *msg*
  and then the arguments are passed to :meth:`logging.info`

.. method:: edzed.Block.warn(msg: str, *args, **kwargs) -> None

  Log a warning message.

  The block name is prepended to the *msg* and then
  the arguments are passed to :meth:`logging.warning`

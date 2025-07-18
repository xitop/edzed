.. currentmodule:: edzed

**--- INFORMATION FOR DEVELOPERS ---**

==========================
Creating sequential blocks
==========================


Topics to be considered during the planning phase:

- what fully defines the internal state?
- how will be the internal state initialized?
- how to calculate the output from the internal state?
- what events will be accepted?
- what data is expected and which value should be returned
  for each particular event?

Checklist for creating a new SBlock:

- subclass from :class:`SBlock` and appropriate :ref:`add-ons <Add-ons>`
- define :ref:`Initialization <SBlock initialization>` and other state related methods
- define :ref:`event handlers <Event handlers>`
- define :ref:`start and stop methods <Start and stop>`
- implement :ref:`event generation <Generating events>` (rarely needed)


SBlock initialization
=====================

The goal is to set the internal state and the output.

Let's recap the :ref:`initialization order <Initialization rules>`
with links to corresponding sections added. Each block defines only those steps
that are appropriate to its functionality.

1. from persistent data
     see: :class:`AddonPersistence` and :meth:`SBlock._restore_state`
2. asynchronous initialization routine
     see: :class:`AddonAsync` and :meth:`SBlock.init_async`
3. regular initialization routine
     see :meth:`SBlock.init_regular`
4. from the *initdef* value
     see :meth:`SBlock.init_from_value`

.. important::

  The general rule for all initialization functions:
  If it is not possible to initialize the block, leave it
  uninitialized and return. Do not raise on errors, only log
  a notice.

.. method:: SBlock.get_state() -> Any
  :noindex:

  Return the internal state. Raise an :exc:`EdzedInvalidState`
  when called before a successful initialization.

  The default implementation assumes the state is equal to the output.

  This method *must* be redefined for more complex SBlocks
  to return the real internal state.

  It is recommended that this method produces JSON serializable data,
  especially when the block supports persistent state.
  JSON serializable data can be stored or transferred with minimum
  difficulties.

.. method:: SBlock.init_regular() -> None

  Initialize the internal state to a fixed value and set the output.

  Define only if the block can be initialized this way.

.. method:: SBlock.init_from_value(value: Any, /) -> None

  Initialize the internal state from the given *value*
  and set the output.

  Define only if the block can be initialized this way.

  Defining this method automatically enables
  :class:`SBlock`\'s keyword argument *initdef*.


Event handling
==============

Dispatching events to handlers
------------------------------

Taking delivery of an event by its destination block is implemented
in the :meth:`SBlock.event` method.

.. method:: SBlock.event(etype: str|EventType, /, **data) -> Any

  Handle the incoming event of :ref:`type<Event types>` *etype* with attached *data*
  by dispatching it to the respective handler. Return the handler's exit value.
  Evaluate conditional events (see the :class:`EventCond`) before further processing.
  Raise :exc:`EdzedUnknownEvent` if there is no handler for the *etype*.

  ``event()`` may return a value of any type. It is useful as a reply to
  an external event, but it is unused in the case of internal events.
  Other circuit blocks ignore the returned value.

  .. warning::

    If an exception other than an unknown event type or a trivial parameter error
    is raised during the event handling, the simulation will be aborted even if
    the caller catches the exception with a ``try-except`` construct.

  .. versionchanged:: 23.8.25

    This method used to be an event entry point also for external events,
    but now is ``SBlock.event()`` considered for internal use only.
    Application code should not call it directly. To forward
    an external event, :meth:`ExtEvent.send` should be used instead.


Event handlers
--------------

There are two ways to define handlers for incoming :ref:`events <Events>`:

1. Add specialized event handlers.

  .. method:: SBlock._event_ETYPE(**data: Any) -> Any

    If a method with matching event type ``'ETYPE'`` is defined,
    it will be called to handle that event type.

  For example: :meth:`_event_put` will be called for all ``'put'`` events.

  .. note::

    This way a non-FSM event can be added to an FSM block if need be.
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

  .. method:: SBlock._event(etype: str|EventType, data: Mapping[str, Any]) -> Any

    :meth:`_event` will be called for events without a specialized event handler.

    Raise :exc:`EdzedUnknownEvent` if the *etype* is not supported.
    ``event()`` may return a response of any type. It has a significance only
    when interfacing with an external system. Other circuit blocks ignore
    the returned vale.

    Example::

      def _event(self, etype, data):
          if etype == 'ying':
              # handle event ying here
              return None

          if etype == 'yang':
              # handle event yang here
              return None

          # let the parent handle everything else,
          # the base class simply raises the EdzedUnknownEvent
          return super()._event(event, data)

    Note: Do not confuse this event handler ``_event()`` with the event dispatcher
    :meth:`event`. The latter should be left untouched.

----

.. note::

  Note the different ways the event data is passed to a handler (it is intentional)::

    def _event_ETYPE(self, **data):  # as keyword args
    def _event(self, etype, data):   # as a dict

.. important::

  A block must ignore any additional data items.


Setting the output
==================

Event handlers and initialization functions manage the internal
state and the output value. The output setter is:

.. method:: SBlock.set_output(value: Any) -> None

  Set the output value. The *value* must not be :const:`UNDEF`.

  A block is deemed initialized when its output value changes from
  :const:`UNDEF` to any other value. i.e. after
  the first :meth:`set_output` call.


Generating events
=================

The recommended way to implement events to be sent when some trigger
has fired is to add an *on_TRIGGER* keyword argument::

    class ExampleBlock(edzed.SBlock):

        def __init__(self, *args, on_bang=None, **kwargs):
            self._bang_events = edzed.event_tuple(on_bang)
            super().__init__(*args, **kwargs)

        def _send_bang_events(self):
            """Notify all recipients that a 'bang' has occurred."""
            for event in self._bang_events:
                event.send(self, trigger='bang')  # add event data as needed

.. function:: event_tuple(arg: None|Event|Sequence[Event]) -> tuple[Event, ...]

  A helper supporting multiple ways to specify event(s).

  Convert ``None``, a single :class:`Event` object or a sequence of :class:`Event`
  objects to a tuple with zero, one or more events.

  .. versionchanged:: 23.2.14

    Using an iterator to specify multiple events is deprecated.
    Use a tuple or a list instead.

.. method:: Event.send(source: Block, /, **data) -> bool

  Apply filters, add source item to the data and send this event.

  Return ``True`` if the event was sent, ``False`` if rejected by a filter.
  The return value may be important as a response to external events,
  but the internal block-to-block events are one-way communication and the
  return value from the :meth:`SBlock.event` is disregarded by sender blocks.

  Parameter *source* specifies the sender block. The destination is given
  by the :class:`Event`. The purpose of *data* (given as ``name=value`` keyword arguments)
  is to describe the event. Details depend on the particular sender and event type.

  ``'source': <name of sender block>`` item is added to the event data.

  Blocks provided by ``edzed`` also include ``'trigger': <trigger name>``
  where the trigger name is derived from the corresponding parameter
  mainly by stripping the ``'on_'`` prefix.


Start and stop
==============

:meth:`SBlock.start` is called when the circuit simulation is about to start,
before the block initialization;
:meth:`SBlock.stop` is called when the circuit simulation has finished.

.. method:: SBlock.start() -> None

  Pre-simulation hook.

  Set up resources necessary for proper function of the block.
  Do not set the internal state here.

  .. important::

    When using ``start()``, always call the ``super().start()``.

  .. note::

    Why do we need ``start()`` when we have ``__init__()``?

    Only the ``start()`` is the right place for actions that:

    - have a side effect, or
    - are resource intensive (time, memory, CPU), or
    - require an asyncio event loop

    What we want to achieve is that blocks may be created at import time,
    i.e. defined at the module level. Importing such module should not
    have any negative effects.

.. method:: SBlock.stop() -> None

  Post-simulation hook, a counterpart of :meth:`start`.

  ``stop()`` is dedicated for cleanup actions. It is called when the circuit
  simulation has finished, but only if :meth:`start` was successfully called.

  An exception in ``stop()`` will be logged, but otherwise ignored.

  .. important::

    When using ``stop()``, always call the ``super().stop()``


Add-ons
=======

.. important::

  In the list of new block's bases always put the add-on classes
  before the :class:`SBlock`::

    class NewBlock(edzed.AddonPersistence, edzed.SBlock): ...


Persistent state add-on
-----------------------

.. class:: AddonPersistence

  Inheriting from this class adds support for state persistence.
  The related arguments *persistent*, *sync_state*, and *expiration*
  are explained in the :class:`SBlock`\'s documentation.

  If enabled, the block's internal state (as returned by :meth:`SBlock.get_state`
  is saved to the persistent storage provided by the circuit in these
  situations:

  - when :meth:`SBlock.save_persistent_state` is called
  - at the end of a simulation
  - by default also after each event; this can be disabled
    with *sync_state* keyword argument.

  Saving of persistent state is disabled after an error in :meth:`SBlock.event`
  in order to prevent saving of possibly corrupted state.

  For state restoration :meth:`_restore_state` must be implemented.

  The simulator retrieves the saved state from the persistent storage,
  then it checks the expiration time and unless the state has expired,
  it is passed to :meth:`_restore_state`.

.. method:: SBlock.save_persistent_state() -> None

  Save the internal state to persistent storage.

  This method is usually called by the simulator.

.. method:: SBlock._restore_state(state: Any, /) -> None
  :abstractmethod:

  Initialize by restoring the *state* (presumably created by :meth:`get_state`)
  and the corresponding output.

  Note that :meth:`_restore_state` is sometimes identical with
  :meth:`SBlock.init_from_value`.

.. attribute:: SBlock.key
  :type: str

  The persistent dict key associated with this block. It equals the string representation
  ``str(self)``, but this is an implementation detail that may change in the future.


Async add-on
------------

.. class:: AddonAsync

  Inheriting from this class adds asynchronous support, in particular
  asynchronous initialization and asynchronous cleanup.

  .. note::

    If the only function to be implemented is an async initialization,
    consider using an :class:`InitAsync` helper block instead.

  This class also implements a helper for general use:

  .. method:: _create_monitored_task(coro: Awaitable, is_service: bool = False, **task_kwargs) -> asyncio.Task
    :async:

    Create a task monitored for an eventual failure.

    .. important::
      For the purpose of monitoring, the cancellation is never considered an error.
      Note that the :exc:`CancelledError` exception is *not* derived from the
      :exc:`Exception` class (it's a :exc:`BaseException` subclass) and as such
      it is not caught by the monitor.

    This function acts like :func:`asyncio.create_task`, but if the task exits
    due to an exception, the simulation will abort. ``_create_monitored_task()``
    also adds the block name to the exception notes (Python >= 3.11)
    or to the exception message (``Exception.args[0]`` if it is a string)
    for better problem identification.

    Coroutines marked as services (*is_service*  is ``True``) are supposed
    to run until cancelled - even a normal exit is treated as an error.

    Extra keyword arguments *\*\*task_kwargs* are passed to the :func:`asyncio.create_task`;
    as of Python 3.11 it accepts *name* and *context*.


.. method:: SBlock.init_async() -> None
  :async:

  Optional async initialization coroutine, define only when needed.

  The async initialization is intended to interact with external
  systems and as such should be utilized solely by circuit inputs.

  The existence of this method automatically enables the *init_timeout*
  :class:`SBlock` keyword argument.

  :meth:`init_async` is run as a task and is waited for *init_timeout*
  seconds. When a timeout occurs, the task is cancelled and the
  initialization continues with the next step.

  Implementation detail: The simulator may wait longer than
  specified if it is also concurrently initializing another
  :class:`AddonAsync` based block with a longer *init_timeout*.

  .. important::

    Should an event arrive during the async initialization, the block
    will get a regular synchronous initialization in order to
    be able to process the event immediately. For this reason,
    when :meth:`init_async` asynchronously obtains the initialization value,
    it should check whether the block is still uninitialized before applying
    the value.

.. method:: SBlock.stop_async() -> None
  :async:

  Optional async cleanup coroutine, define only when needed.

  The existence of this method automatically enables the *stop_timeout*
  :class:`SBlock` keyword argument.

  This coroutine is awaited after the regular :meth:`stop`.

  :meth:`stop_async` is run as a task and is waited for *stop_timeout*
  seconds. When a timeout occurs, the task is cancelled.
  The simulator logs the error and continues the cleanup.

  .. tip::

    Use :func:`utils.shield_cancel` to protect small
    critical task sections from immediate cancellation.


Main task add-on
----------------

.. class:: AddonMainTask(*args, **block_kwargs, **task_kwargs)

  A subclass of :class:`AddonAsync`. In addition to :class:`AddonAsync`\'s
  features, inheriting from this add-on adds support for a task automatically
  running from simulation start to stop.

  The add-on manages everything necessary including task monitoring. If the task
  terminates before stop, the simulation will be aborted.

  Adjust the *stop_timeout* (:class:`SBlock`\'s argument) if necessary.
  Note that the *init_timeout* argument does not apply, because task creation
  is a regular function.

  All keyword arguments starting with ``"task_"`` are passed to :func:`asyncio.create_task`
  with the ``"task_"`` prefix removed. Example ``"task_name="data acquisition task"``.

  .. versionadded:: 25.7.10
    *\*\*task_kwargs*
    (the illustrative signature in the heading is not syntactically correct)

  .. versionchanged:: 25.7.10
  
    The main task is now started after the circuit initialization finishes.
    See :meth:`Circuit.wait_init` for details. **Exception**: when combined
    with :class:`AddonAsyncInit`, the main task is started immediately.
    Inherit from :class:`AddonAsyncInit` if your block begins to fail with
    "not initialized" error after upgrade.

.. method:: AddonMainTask._maintask()
  :abstractmethod:
  :async:

  The task coroutine.


Async initialization add-on
---------------------------

.. class:: AddonAsyncInit

  There are blocks like the :class:`ValuePoll` lacking any initialization code,
  because they are collecting data as their main job and the first value they
  obtain automatically becomes the initialization value.

  This tiny add-on adds a :meth:`SBlock.init_async` implementation that ensures
  proper interfacing with the simulator in such cases. Its only function is
  to inform the simulator that the initialization took place.

  Presence of this add-on modifies the behavior of :class:`AddonMainTask`.


Note about eager tasks in asynchronous add-ons
----------------------------------------------
  
Python 3.12 introduced eagerly started asyncio tasks. This feature changes
the task execution order and that sometimes matters during the circuit start.

Normally, the developer decides whether eager tasks will be used
and will write the code accordingly, but sometimes an ``edzed``
application needs to support both cases. Following functions may be affected:

- :meth:`AddonAsync._create_monitored_task`
- :meth:`AddonMainTask._maintask`, but only if :class:`AddonMainTask`
  is used in conjunction with :class:`AddonAsyncInit`.

These measures can be taken if necessary:

- Python 3.14 (to be released in October 2025) will add a new option
  *eager_start* that you can add to *task_kwargs* in and :class:`AddonMainTask`
  (as *task_eager_start* in the latter case) and thus override the default
  task factory setting.

- Consider using a statement that re-orders the task execution. Put it at the top
  of the coroutine. This is what :class:`AddonMainTask` does when used *without*
  :class:`AddonAsyncInit`::

    circuit = edzed.get_circuit()
    await circuit.wait_init()       # wait until initialization is completed

  The moment when ``await`` returns from ``wait_init()`` does not depend
  on the method the task was started.


Helper methods
==============

When creating new blocks, you may find these methods useful:

.. method:: Block.log_msg(msg: str, *args, level: int, **kwargs) -> None

  Log a message.

  The block name is prepended to the *msg* and then
  the arguments are passed to :meth:`logging.log`
  with the given *level*.

.. method:: Block.log_debug(*args, **kwargs) -> None
.. method:: Block.log_info(*args, **kwargs) -> None
.. method:: Block.log_warning(*args, **kwargs) -> None
.. method:: Block.log_error(*args, **kwargs) -> None

  Log a debug/info/warning/error message respectively.

  A debug message is logged only if :ref:`debug messages <Circuit block debug messages>`
  are enabled for the block.

  These are simple :meth:`Block.log_msg` wrappers.


Example (Input)
===============

An input block like :class:`Input`, but without data validation::

  class Input(edzed.AddonPersistence, edzed.SBlock):
      def init_from_value(self, value):
          self.event('put', value=value)

      def _event_put(self, *, value, **_data):
          self.set_output(value)
          return True

      _restore_state = init_from_value

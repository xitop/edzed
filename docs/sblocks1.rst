.. currentmodule:: edzed

=============================
List of sequential blocks 1/2
=============================

List of sequential blocks offered by the ``edzed`` library - first part.

**Conventions used in this chapter:**

1. Only block specific parameters are listed in the signatures. In detail:

  - the mandatory positional argument *name* is documented in the base class :class:`Block`

  - common optional keyword arguments *on_output*, *debug*, *comment* and *x_NAME*
    are shown only as ``**block_kwargs``, they are documented in the base class :class:`Block`

  - if persistent state is supported, only the *persistent* parameter is listed,
    but *sync_state* and *expiration* are always supported together with *persistent*,
    refer to :class:`SBlock`

  - *initdef*, *init_timeout* and *stop_timeout* are listed in the class signature
    only if supported by the particular block type. Their descriptions are not repeated
    here, refer to :class:`SBlock`

2. all time duration values (timeouts, intervals, etc.) can be given as a number
   of seconds or as a :ref:`string with time units<Time durations with units>`
   The corresponding type is ``int|float|str`` and if optional, it could be also ``None``.

3. all *on_something* parameters expect zero, one or more :ref:`events<Events>`.
   The corresponding type is
   ``None|edzed.Event|Iterator[edzed.Event]|Sequence[edzed.Event]``
   and we omit this long annotation for brevity.

Inputs
======

Pushing external data into the circuit
--------------------------------------

.. important::

  Data are transported by events. To push new data use :meth:`ExtEvent.send`,
  refer to :ref:`external events<External events>`.

Depending on your application's needs, any sequential block
may serve as a part of the circuit's input interface.
The most common data entry block is the ``Input``.

----

.. class:: Input(name, *, check=None, allowed=None, schema=None, persistent=False, initdef=edzed.UNDEF, **block_kwargs)

  An input block with optional value validation.

  :param check:
    A value test function or ``None`` if unused.
    If the function's return value evaluates to true,
    new value is accepted, otherwise it is rejected.
  :type check: Callable[[Any], Any] or None

  :param collection allowed:
    A collection of allowed values or ``None`` if unused. Equivalent to:
    ``check=lambda value: value in ALLOWED``
  :type allowed: Collection or None

  :param schema:
    A function possibly modifying (preprocessing) the value or ``None`` if unused.
    If the function raises, value is rejected,
    otherwise the input is set to the returned value.
    *Schema* is the only validator capable of changing the value.
    It is called last to ensure all validators test the original
    input value.
  :type schema: Callable[[Any], Any] or None

  :param bool persistent: If true, initialize from the last known value

  :param Any initdef: Default value; must pass the validators.

  The ``Input`` accepts only ``'put'`` events.
  It stores and outputs the ``'value'`` data item sent with the event
  provided that it validates successfully. The event returns ``True``
  if the new value is accepted, ``False`` otherwise.

  You should always validate inputs. It is recommended to use only one validator,
  but any combination of *schema*, *check* and *allowed* is allowed.


.. class:: InputExp(name, *, duration, expired=None, check=None, allowed=None, schema=None, persistent=False, initdef=edzed.UNDEF, **block_kwargs)

  Like :class:`Input`, but after certain time after the ``'put'`` event
  replace the current value with the *expired* value.

  An ``InputExp`` takes the same arguments as :class:`Input`
  plus two additional ones:

  :param duration:
    The default duration in seconds before a value expires.
    May be overridden on a per-event basis. The argument
    may be ``None`` for no default duration. Without a default,
    every event must explicitly specify the duration.

  :type duration: int or float or str or None

  :param Any expired:
    A value to be applied after expiration; must pass the validators.

  If a ``'duration'`` item (with the same format as the *duration* parameter)
  is present in the event data, it overrides the default duration.

Polling data sources
--------------------

A specialized block is provided for this task:

.. class:: ValuePoll(name, *, func, interval, init_timeout=None, initdef=edzed.UNDEF, **block_kwargs)

  A source of measured or computed values.
  This block outputs the result of an acquisition function *func* every
  *interval* seconds.

  :param Callable func:
    The data acquisition function *func*. It could be a regular function
    (defined with ``def``) or a coroutine function (defined with ``async def``).

  :param interval:
    The interval between function calls. The duration
    of the call itself represents an additional delay.
  :type interval: int or float or str

  A data acquisition error (i.e. any unhandled exception in *func*)
  terminates the simulation.
  If a real value could become unavailable, the function should handle such
  condition. It has these basic options:

  - return some default value
  - return some sentinel value understood by connected
    circuit blocks as missing value
  - return :const:`UNDEF`. If it returns :const:`UNDEF`, it will be ignored
    and no output change will happen

  Initialization rules:
  If the very first value is not obtained within the *init_timeout*
  limit, the *initdef* value will be used as a default. If *initdef*
  is not defined, the initialization fails.


Outputs
=======

The output blocks invoke a function in response to a ``'put'`` event.

.. seealso::

  the :class:`Repeat` block. Repeated output actions
  may increase the robustness of applications.

Error handling
--------------

Both output blocks described in this section require the error handling to be set explicitly.
The options are:

- ``on_error=None`` to ignore errors
- ``on_error=edzed.Event.abort()`` to make every error fatal;
  see the :meth:`Event.abort`
- customized error handling: specify events which will notify
  circuit blocks created for this purpose

In each case the error will be logged.

Output blocks
-------------

Output blocks invoke a supplied function to perform an output operation.
The appropriate block type depends on the output function's type:

- :class:`OutputFunc` - for regular non-blocking functions
- :class:`OutputAsync` with :class:`InExecutor` - for regular blocking functions::

    edzed.OutputAsync(..., coro=edzed.InExecutor(blocking_function), ...)

- :class:`OutputAsync` - for coroutine functions

In this context, a *blocking function* is a function that does not
always return in a short time, because it could do a CPU intensive computation
or slow I/O. Local file access is considered not blocking, but
any network communication is a typical example of blocking I/O.

----

.. class:: OutputFunc(name, *, func, f_args=['value'], f_kwargs=(), on_success=None, on_error, stop_data=None, **block_kwargs)

  Call a function when a ``'put'`` event arrives.

  :param Callable func: function to be invoked on each ``'put'`` event
  :param Sequence[str] f_args:
    specifies which event data values will be passed to *func*
    as positional arguments (args)
  :param Sequence[str] f_kwargs:
    specifies which event data values will be passed to *func*
    as keyword arguments (kwargs)

  :param on_error:
    event(s) to be sent on a function call error, this is a mandatory parameter

  :param on_success: event(s) to be sent after a successful function call

  :param stop_data:
    event data (a ``{'name': value}`` dictionary) or ``None`` if not used.
    See the "Final state" paragraph below..
  :type stop_data: Mapping[str, Any] or None

  **Output function and its arguments:**
  The function *func* is called with arguments extracted from the event data.
  The default *f_args* and *f_kwargs* values cause the *func* to be called
  with ``data['value']`` as its sole argument. This covers most use-cases,
  but the argument passing can be easily configured differently by adjusting
  *f_args*  and *f_kwargs*.

  The keys of values to be extracted as positional (keyword) arguments
  are specified with the *f_args* (*f_kwargs*) respectively.
  The event data of every received ``'put'`` event must contain
  all keys listed in *f_args* and *f_kwargs*.

  (side note: due to a software limitation, the default *f_args*
  value is shown as a list, but it is a tuple.)

  **Generated events:**
  After calling the output function *func*, any returned value is considered a success.
  An exception means an error.

  On success:
    - *on_success* :ref:`events<Events>` are triggered and the
      returned value is added to the event data as ``'value'``
    - the ``'put'`` event returns ``('result', <returned_value>)``

  On error (see :ref:`error handling<Error handling>`):
    - *on_error* :ref:`events<Events>` are triggered and the
      the exception is added to the *on_error* event data as: ``'error'``.
    - the ``'put'`` event returns ``('error', <exception>)``

  **Final state:**
  If the *stop_data* is not ``None``, it is used as the event data of a synthetic
  event delivered to the block during the cleanup and processed as the
  last item before stopping. This allows to leave the controlled process
  in a well-defined state.

  **Output:** The output of an OutputFunc block is always ``False``.

.. class:: OutputAsync(name, *, coro, mode: str, f_args=['value'], f_kwargs=(), guard_time=None, on_success=None, on_cancel=None, on_error, stop_data=None, stop_timeout=None, **block_kwargs)

  Run an async function *coro* in an asyncio task when a ``'put'`` event arrives.
  The async function is invoked with arguments extracted from the event data.
  The event returns immediately and does not return any result.

  Parameters *f_args*, *f_kwargs*, *on_success*, *on_error*, and *stop_data* have
  the same meaning as in :class:`OutputFunc`.

  **Operation modes:**
  There are three operation modes. The difference is in the behavior when
  a new ``'put'`` event arrives before the processing of the previous one
  has finished:

  ======  ===================
  mode    event handling
  ======  ===================
  cancel  the latest one only
  wait    sequential (FIFO)
  start   concurrent
  ======  ===================

  In detail:

  - mode='cancel' or just 'c' (**c**\ancel before start)

    In this mode the task processing the previous event will be cancelled
    and awaited. Unprocessed events except the last one are discarded.
    Discarded events are reported as cancelled, even if their task was never
    started.

  - mode='wait' or just 'w' (**w**\ait before start)

    In this mode the task processing the previous event will be awaited
    before the next one is started. All events are enqueued and processed
    one by one in order of arrival. This may introduce delays. Make sure
    the coroutine can keep up with the rate of incoming events.

  - mode='start' or 's' (**s**\tart immediately)

    In this mode a new task is immediately started for each new event
    regardless of the state of previously started tasks. Unlike other
    modes, multiple output tasks may be running concurrently. The order
    of their termination may differ from the order they were started.

  **Output:**
  The output of an OutputAsync block is the number of active output tasks,
  a non-negative integer. It can be only 0 (idle) or 1 (active) in the
  ``'cancel'`` and ``'wait'`` modes. In the ``'start'`` mode the active
  task count is not limited.

  **Generated events:**
  The block triggers *on_success*, *on_cancel* and *on_error* :ref:`events<Events>`
  depending on the result of the task. A normal termination is considered
  a success and the returned value is added to the *on_success* event data as ``'value'``.
  An exception other than :exc:`asyncio.CancelledError` means an error;
  the raised exception is added to the *on_error* event data as ``'error'``.
  Cancelled tasks trigger *on_cancel* events. Note that tasks are
  cancelled only in the ``'cancel'`` mode. In all three cases (success, cancel, error)
  the original ``'put'`` event data is inserted into the output event data
  as item ``'put'``. This makes it possible to match an event with its result.

  .. note::

    Due to the asynchronous character of this block, some events may be generated
    during the simulation shutdown. It those events are sent to other asynchronous
    blocks, their effect is undefined, because those destination blocks are shutting
    down as well. Events sent to non-asynchronous blocks will be always processed
    normally.

  **Final state:**
  If the *stop_data* is defined, it is processed as the last item before stopping.
  As this happen during the stop phase, make sure the *stop_timeout* gives enough
  time for finishing all work in progress and then a successful output task
  run with *stop_data*.

  **Guard time:**
  The *guard_time* is the duration in seconds of a mandatory and uncancellable
  sleep after each run of the output task. No output activity can
  happen during the sleep. The purpose is to limit the frequency
  of actions, for instance when controlling a hardware switch.
  Default value is ``None`` for no guard_time, equivalent to 0.0 seconds.
  The *guard_time* must not be longer than the *stop_timeout*.

  .. note::

    The *guard_time* should not be used in the ``'start'`` mode
    which allows multiple output tasks running concurrently
    defeating the effect of a *guard_time* sleep.

.. class:: InExecutor(func, executor=concurrent.futures.ThreadPoolExecutor)

  Create a coroutine function - suitable as *coro* argument in :class:`OutputAsync` -
  that runs the provided regular function *func* in a thread pool or other *executor*,
  e.g. a process pool. This allows to run an otherwise blocking function without
  actually blocking the asyncio's event loop.

  ``InExecutor`` is a thin wrapper around the asyncio's
  `run_in_executor <https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor>`_.
  Starting with Python 3.9 asyncio provides
  `to_thread <https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread>`_
  with similar functionality, but different usage.


Initialization helper
=====================

.. class:: InitAsync(name, *, init_coro: Sequence, **block_kwargs)

  Run a coroutine once during the circuit initialization.

  This block usually initializes other blocks lacking an async support
  by sending an output event. For example it can obtain a value from
  an external command and send it to an :class:`Input` block in a
  ``'put'`` event.

  :param init_coro:
    a sequence (list, tuple, ...) containing the coroutine function
    (i.e. defined with ``async def``) to be awaited followed by its arguments.

  In order to fully utilize this block, you might need to specify additional
  parameters. Refer to the base class :class:`SBlock`.

  :param init_timeout:
    the coroutine timeout
  
  :param initdef:
    a default value for the case the coroutine fails

  :param on_output:
    an output event addressed to the block to be initialized

  If the coroutine finishes successfully, the block's output is set to
  the returned value. That generates an output event.

  If the coroutine fails (timeout, exception), the problem is logged
  and the output is set to the ``initdef`` value if it is defined.
  That generates an output event too.

  If the coroutine fails and the ``initdef`` value is not set, then
  *no output events* are generated. The output is set to ``None`` only to
  prevent a circuit failure. The block listed as the event recipient
  must initialize by itself.

  .. seealso:: :class:`NotIfInitialized` event filter


Counter
=======

.. class:: Counter(name, *, modulo: int|float|None = None, initdef=0, persistent=False, **kwarg)

  A counter.

  If *modulo* is set to a number M, count modulo M.
  For a positive integer M it means to count only from 0 to M-1
  and then wrap around. If *modulo* is not set, the output value
  is not bounded.

  The counter can process floats, but be prepared for inevitable
  rounding errors of floating point arithmetic.

  Initialization parameters:

  :param bool persistent:
    If true, initialize from the last known value

  :param initdef:
    Initial value, 0 by default

  Accepted events and relevant data items:

  - ``'inc'``
     increment (count up) by 1 or by the value of ``'amount'`` data item
     if such item is present in the event data
  - ``'dec'``
     decrement (count down) the counter by 1 or by ``'amount'``
  - ``'put'``
     set to ``'value'`` data item (mod M)
  - ``'reset'``
     reset to the initial value as defined by *initdef*

  All events return the updated output value.


Repeat
======

.. class:: Repeat(name, *, dest, etype = 'put', interval, count = None, **block_kwargs)

  Periodically repeat the last received event.

  :param etype: type of events to be repeated
  :type etype: str or EventType
  :param dest: destination block, an instance or its name
  :type dest: block.SBlock or str
  :param interval: time interval between repetitions
  :type interval: int or float or str
  :param count:
    optional limit for repetition count, the original event is not counted
  :type count: int or None

  .. tip::
     The :class:`Event` class offers a convenient automatic creation
     of a ``Repeat`` block for a given event. It is the preferred
     method for most cases. However, if there are multiple event sources
     for the given destination, an explicitly created ``Repeat`` block
     is necessary.

  The Event block is intended mainly to repeat output events and thus minimize
  the chance that some connected device will fail to act due to temporary
  communication problems. The key requirement is that repeating must not
  change the outcome, i.e. multiple invocations produce the same effect
  as a single invocation. Such actions are called *idempotent*.

  For a predictable operation only one selected event type *etype*
  is repeated and all others are ignored. This implies a separate ``Repeat``
  block for each event type. A warning is logged on the first encounter
  with an unexpected type.

  The event is sent to the destination block specified by *dest*.
  The received event is re-sent immediately
  and then duplicates are sent in time intervals specified by *interval*.
  The number of repetitions may be limited with *count*. If not ``None``,
  the repeating stops after *count* duplicates sent. The original event
  is always re-sent and not counted.

  A Repeat block saves the event data item ``'source'`` to ``'orig_source'``,
  because the block itself will become the source. It also adds a ``'repeat'``
  count value. The original event is sent with ``repeat=0``,
  subsequent repetitions are sent with ``repeat=N`` where N is 1, 2, 3, ...
  This repeat value is also copied to the output, the initial output is 0.

  .. important::

    It is not possible to repeat the conditional event :class:`EventCond`.
    The condition is evaluated and one of the two choices is selected before
    the event reaches the ``Repeat`` block.

  .. note::

    It is recommended to repeat only events identified by a string.

    The type of every received event is compared with the *etype*
    argument. This is a well-defined operation for strings, but the comparison
    result for special events (derived from the :class:`EventType`) depends
    on how the equality is defined in the particular class. This
    concerns mainly user-defined special events, because ``edzed``
    provides only two special events from which the :class:`EventCond`
    cannot be repeated and the :class:`Goto` should not be even sent
    from block to block.


Timer
======

.. class:: Timer(name, *, restartable=True, persistent=False, **block_kwargs)

  A timer (:ref:`source <Example (Timer)>`).

  This is an FSM block. The output is ``False`` in state ``'off'`` for time
  duration *t_off*, then ``True`` in state ``'on'`` for duration *t_on*,
  and then the cycle repeats.

  By default both durations are infinite (timer disabled), i.e. the
  block is bistable. If one duration is set, the block is monostable.
  If both durations are set, the block is astable.

  :param bool restartable:
    If ``True`` (default), a ``'start'`` event
    occurring while in the ``'on'`` state restarts the timer
    to measure the ``'t_on'`` time from the beginning. If not
    restartable, the timer will continue to measure the
    time and ignore the event. The same holds for the ``'stop'``
    event in the ``'off'`` state.

  The ``Timer`` accepts all standard :ref:`FSM parameters`
  and a *t_period* added for convenience:

  :param t_on:
    ``'on'`` state timer duration
  :param t_off:
    ``'off'`` state timer duration
  :param t_period:
    ``t_period=T`` is a shortcut for setting ``t_on = t_off = T/2``,
    i.e. to create a clock signal generator with the period ``T``
    (plus some small overhead) and a duty cycle of 50%.
    Arguments *t_period* and *t_on*, *t_off* are mutually exclusive.
  :param initdef:
    Set the initial state. Default is ``'off'``.
    Use ``initdef='on'`` to start in the ``'on'`` state.
  :param persistent:
    Enable persistent state.

  Events:

  - ``'start'``
      Go to the ``'on'`` state. See also: *restartable*.
  - ``'stop'``
      Go to the ``'off'`` state. See also: *restartable*.
  - ``'toggle'``
      Go from ``'on'`` to ``'off'`` or vice versa.

  .. hint::
    A conditional event :class:`EventCond`\ ``('start', 'stop')``
    is often used for ``Timer`` control.

  .. versionadded:: 22.12.4 *t_period*


Simulator control block
=======================

.. class:: ControlBlock(name, **block_kwargs)

  The simulator control block accepts two event types:

  - ``'shutdown'``
    Shut down the circuit.

  - ``'abort'``
    Abort the simulation due to an error. An ``'error'`` item
    is expected to be included in the event data. Its value may be
    an :exc:`Exception` object or just an error message.

  A ControlBlock named ``'_ctrl'`` will be automatically created if
  there exists a reference to this name in the circuit. The :class:`Event`
  class provides constructors :meth:`Event.abort` and :meth:`Event.shutdown`
  creating the corresponding events in a convenient way.

  The output value is fixed to ``None``.

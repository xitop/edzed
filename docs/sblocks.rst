.. currentmodule:: edzed

=========================
List of sequential blocks
=========================

This section lists sequential blocks offered by the ``edzed`` library.

Only block specific parameters are listed in the signatures. In detail:

- the mandatory positional argument *name* is documented in the base class :class:`Block`

- common optional keyword arguments *on_output*, *debug*, *comment* and *x_NAME*
  are shown only as ``**block_kwargs``, they are documented in the base class :class:`Block`

- if persistent state is supported, only the *persistent* parameter is listed,
  but *sync_state* and *expiration* are always supported together with *persistent*,
  refer to :class:`SBlock`

- *initdef*, *init_timeout* and *stop_timeout* are listed in the class signature
  only if supported by the particular block type. Their descriptions are not repeated
  here, refer to :class:`SBlock`


Inputs
======

Feeding data into the circuit
-----------------------------

.. important::

  :meth:`SBlock.event` is the data input entry point.

  Always check if the circuit is ready before forwarding external
  events to blocks. If not ready, the result is undefined!
  Refer to :meth:`Circuit.is_ready`.

Depending on your application's needs, any sequential block
may serve as a part of the circuit's input interface.
The most common data entry block is the ``Input``.

----

.. class:: Input(name, *, check=None, allowed=None, schema=None, persistent=False, initdef=edzed.UNDEF, **block_kwargs)

  An input block with optional value validation.

  .. note::

    Of course, you *should* validate input data.

  The ``Input`` accepts only ``'put'`` events.
  It stores and outputs the ``'value'`` data item sent with the event
  provided that it validates successfully. The event returns ``True``
  if the new value is accepted, ``False`` otherwise.

  Initialization parameters:

  :param bool persistent:
    If true, initialize from the last known value

  :param initdef:
    Default value; must pass the validators.

  Optional validators of input values, ``None`` if unused:

  :param callable check:
    A value test function.
    If the function's return value evaluates to true,
    new value is accepted, otherwise it is rejected.

  :param allowed:
    Allowed values, roughly equivalent to::

      check=lambda value: value in ALLOWED

  :type allowed: sequence or set

  :param callable schema:
    A function possibly modifying (preprocessing) the value.
    If the function raises, value is rejected,
    otherwise the input is set to the returned value.

  It is recommended to use only one validator, but any
  combination of *schema*, *check* and *allowed* is allowed.

  *Schema* is the only validator capable of changing the value.
  It is called last to ensure all validators test the original
  input value.


.. class:: InputExp(name, *, duration, expired=None, check=None, allowed=None, schema=None, persistent=False, initdef=edzed.UNDEF, **block_kwargs)

  Like :class:`Input`, but after certain time after the ``'put'`` event
  replace the current value with the *expired* value.

  An ``InputExp`` takes the same arguments as :class:`Input`
  plus two additional ones:

  :param duration:
    The default duration in seconds before a value expires.
    May be overridden on a per-event basis. The argument
    may be:

      - a numeric value, or
      - a :ref:`string with time units<Time intervals with units>`, or
      - ``None`` for no default duration. Without a default,
        every event must explicitly specify the duration.

  :param expired:
    A value to be applied after expiration; must pass the validators.

  If a ``'duration'`` item (with the same format as *duration* argument)
  is present in the event data, it overrides the default duration.

Polling data sources
--------------------

A specialized block is provided for this task:

.. class:: ValuePoll(name, *, func, interval, init_timeout=None, initdef=edzed.UNDEF, **block_kwargs)

  A source of measured or computed values.

  This block outputs the result of an acquisition function *func* every
  *interval* seconds.
  The *func* argument should be a regular function (defined with ``def``)
  or a coroutine function (defined with ``async def``).
  The *interval* may be written also as a
  :ref:`string with time units<Time intervals with units>`.

  The interval is measured between function calls. The duration
  of the call itself represents an additional delay.

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

.. tip::

  See also the :class:`Repeat` block. Repeated output actions
  may increase the robustness of applications. The key requirement
  is that repeating must not change the outcome, i.e. multiple invocations
  produce the same effect as a single invocation. Such actions are called
  *idempotent*.

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

---

.. class:: OutputFunc(name, *, func, f_args=['value'], f_kwargs=(), on_success=None, on_error, stop_data=None, **block_kwargs)

  Call a function when a ``'put'`` event arrives.

  **Output function and its arguments:**
  The function *func* is called with arguments extracted from the event data.
  The default *f_args* and *f_kwargs* values cause the *func* to be called
  with ``data['value']`` as its sole argument. This covers most use-cases,
  but the argument passing can be easily configured differently by adjusting
  *f_args*  and *f_kwargs*.

  The keys of values to be extracted as positional (keyword) arguments
  are specified with the *f_args* (*f_kwargs*) respectively. Both arguments must be
  sequences of strings. The event data of every received ``'put'`` event must contain
  the keys listed in *f_args* and *f_kwargs*.

  (note: due to a software limitation, the default *f_args*
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
  If the *stop_data* is not ``None``, it is used as the event data of a virtual
  event delivered to the block during the cleanup and processed as the
  last item before stopping. This allows to leave the controlled process
  in a well-defined state. *stop_data* argument must a dict.

  **Output:** The output of an OutputFunc block is always ``False``.

.. class:: OutputAsync(name, *, coro, mode, f_args=['value'], f_kwargs=(), guard_time=0.0, on_success=None, on_cancel=None, on_error, stop_data=None, stop_timeout=None, **block_kwargs)

  Run a coroutine function *coro* in an asycio task when a ``'put'`` event arrives.
  The coroutine function is invoked with arguments extracted from the event data.
  The event returns immediately and does not return any result.

  Parameters *f_args*, *f_kwargs*, *on_success*, *on_error*, and *stop_data* have
  the same meaning as in :class:`OutputFunc`.

  **Operation modes:**
  There are three operation modes. The difference is in the behavior when
  a new ``'put'`` event arrives before the processing of the previous one
  has finished:

  - mode='cancel' or just 'c' (**c**\ancel before start)

    In this mode the task processing the previous event will be cancelled
    and awaited. Unprocessed events except the last one are discarded.
    Discarded events are reported as cancelled, even if their task was never
    started.

  - mode='wait' or just 'w' (**w**\ait before start)

    In this mode the task processing the previous event will be awaited
    before the next one is started. All events are enqueued and processed
    one by one in order they have arrived. This may introduce delays. Make sure
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
  The *guard_time* is the duration of a mandatory and uncancellable sleep
  after each run of the output task. No output activity can
  happen during the sleep. The purpose is to limit the frequency
  of actions, for instance when controlling a hardware switch.
  Default value is 0.0 [seconds], i.e. no guard_time. The *guard_time*
  must not be longer than the *stop_timeout*.

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

  .. versionadded:: 21.10.27


Time and date
=============

Date and time strings
---------------------

``edzed`` understands these formats:

- time (e.g. ``'6:45:00'`` or ``'15:55'``)
    The time format is H:M:S or just H:M (i.e. H:M:0) with 24 hour clock.
    Numbers may have one or two digits. The day starts and also ends
    at midnight ``'0:0:0'``.

- date (e.g. ``'April 1'`` or ``'1.apr'``)

    The date is defined as a day and a month in any order, without a year.

    - day = one or two digits
    - month = English month name, may be abbreviated to three or more characters.
      Case insensitive.
    - one period (full stop) may be appended directly after the day or the month.

- year (e.g ``'1984'``) usually in addition to the date

    An integer >= 1970.

In all cases extra whitespace around values is allowed.

Periodic events
---------------

.. class:: TimeDate(name, *, times=None, dates=None, weekdays=None, utc=False, **block_kwargs)

  Block for periodic events occurring daily, weekly or yearly. A combination
  of conditions is possible (e.g. Every Monday morning 6-9 a.m., but only in April)

  If *utc* is ``False`` (which is the default), times are in the local timezone.
  If *utc* is ``True`` times are in UTC.

  The output is a boolean.
  When *times*, *dates* and *weekdays* are all ``None``, the output is ``False``.
  To configure the block define at least one of them.
  The output is then ``True`` only when the current time, date and the weekday
  match the specified arguments. Unused arguments are not taken into account.

  - *times*
      A sequence of time intervals. Each interval is given as
      a ``TimeFrom``, ``TimeTo`` pair. The intervals are left-closed
      and right-open intervals, i.e. ``TimeFrom`` <= time < ``TimeTo``.

      Two input data formats are supported:

      - as a human readable string:

        A comma separated list of time intervals:

          ``"TimeFrom1-TimeTo1, TimeFrom2-TimeTo2, ... TimeFromN-TimeToN"``

        Example:
          ``times="23:50-01:30, 3:20-5:10"``

      - as numbers:

        A sequence (typically a list or tuple) of time intervals.

        Example (same values as above):
          ``times=[[[23,50],[1,30]], [[3,20],[5,10]]]``

  - *dates*
      A comma separated list of date intervals. The ranges are closed intervals,
      i.e. ``DateFrom`` <= date <= ``DateTo``.

      - as a string:

        A comma separated list of date intervals:

          ``"DateFrom1-DateTo1, DateFrom2-DateTo2, ... DateFromN-DateToN"``

        As a shortcut, an one day interval (i.e ``DateFrom`` == date == ``DateTo``)
        can be written as a single date.

        Examples:
          | ``dates="02Mar-15MAR, 9.july - 20.aug."``
          | ``dates="Sept1-Sept2, DEC 31 - JAN 05"``
          | ``dates="May 4"``

      - as numbers:

        A sequence (typically a list or tuple) of date intervals. Dates are always
        written as a sequence of two numbers: the month (1-12) followed by the day (1-31).
        The shortcut mentioned in the string representation is not allowed here.

        Examples (same values as above):
          | ``dates=[[[3,2],[3,15]], [[7,9],[8,20]]]``
          | ``dates=[[[9,1],[9,2]], [[12,31],[1,5]]]``
          | ``dates=[[[5,4],[5,4]]]``


  - *weekdays*
      A list of weekday numbers, where:

        0=Sunday, 1=Monday, ... 5=Friday, 6=Saturday, 7=Sunday (same as 0)

        .. note::

          The weekday numbers in the standard library:

          - :func:`time.strftime`:  0 (Sunday) to 6 (Saturday)
          - :meth:`datetime.date.weekday` and :data:`time.struct_time.wday`: 0 (Monday) to 6 (Sunday)

      Examples:

      - as a string:

        | ``weekdays="12345"`` (working days)
        | ``weekdays="67"``    (the weekend)

      - in a numeric form:

        | ``weekdays=[1, 2, 3, 4, 5]``
        | ``weekdays=[6, 7]``

  .. note::

      Unused arguments *times*, *dates*, or *weekdays* are given as ``None``.
      This is different than an empty string or an empty sequence.

      - ``None`` means we don't care which time, date or weekday respectively.
        **Exception**: if all three parameters are ``None``, the block is disabled.

      - An empty value is a valid argument meaning no matching time or
        date or weekday. A ``TimeDate`` block with an empty parameter
        always outputs ``False``.

  The numeric form of parameters is used internally. Strings are converted
  to numbers before use. The internal parser is available should the need arise:

  .. classmethod:: parse(times, dates, weekdays) -> dict

      Parse the arguments, return a dict with keys ``'times'``, ``'dates'``, ``'weekdays'``
      and values in the numeric form, i.e. as lists or nested lists of integers or ``None``.


**Dynamic updates**

A ``TimeDate`` block can be reconfigured during a simulation
by a ``'reconfig'`` event with event data containing items
``'times'``, ``'dates'`` and ``'weekdays'`` with exactly the same format,
meaning and default values as the block's arguments with the same name.
The *utc* value is fixed and cannot be changed.

The mentioned three values (processed by :meth:`TimeDate.parse`) form the
internal state. They can be retrieved with :meth:`TimeDate.get_state`.

Upon receipt of a ``'reconfig'`` event, the block discards the old settings
and replaces them with the new values. To modify the settings, retrieve the
current values, edit them and send an event.

The block supports state persistence. The *persistent* parameter is described
:ref:`here <Base class arguments>`. Set to ``True`` to make the internal
state persistent. It is only useful with dynamic updates, that's why it is
documented here.

If a saved state exists, it has higher precedence than the arguments.
The arguments are only a default value and as such are copied to the
:data:`TimeDate.initdef` variable. An *initdef* argument is not accepted
though.

Non-periodic events
-------------------

.. class:: TimeSpan(name, *, span=(), utc=False, **block_kwargs)

  Block for non-periodic events occurring in intervals between start and stop
  defined with full date and time, i.e. year, month, day, hour, minute and second.
  Any number of intervals may be specified, including zero.

  If *utc* is ``False`` (which is the default), times are in the local timezone.
  If *utc* is ``True`` times are in UTC.

  The output is a boolean and it is ``True`` when the current time and date are inside
  of any of the intervals.

  The *span* argument is a sequence of intervals. Each interval is given as
  a ``DateTimeFrom``, ``DateTimeTo`` pair. The intervals are left-closed
  and right-open intervals, i.e. ``DateTimeFrom`` <= date_time < ``DateTimeTo``.

  Two input data formats are supported:

  - as a human readable string:

    A comma separated list of intervals. Each endpoint must contain the year, the date
    and the time in any order:

      ``"DateTimeFrom1-DateTimeTo1, ... DateTimeFromN-DateTimeToN"``

      Example::

        span="2020 March 1 12:00 - 2020 March 7 18:30," \
             "10:30 Oct. 10 2020 - 22:00 Oct.10 2020"

  - a numeric form:

    A sequence (typically a list or tuple) of time intervals.

    Example (same values as above). The seconds may be omitted if it zero::

      span=[
        [[2020,  3,  1, 12,  0],    [2020,  3,  7, 18, 30]   ],
        [[2020, 10, 10, 10, 30, 0], [2020, 10, 10, 22,  0, 0]],
        ]

  The numeric form of parameters is used internally. A string is converted
  with this parser:


  .. classmethod:: parse(span) -> list

      Parse the *span* and return a list of intervals, where each interval
      is defined by a pair of lists with 6 integers [year, month, day, hour, minute, second].

**Dynamic updates**

A ``TimeSpan`` block can be reconfigured during a simulation
by a ``'reconfig'`` event with event data containing a ``'span'`` item
with exactly the same format, meaning and default value as the block's
*span* argument. The *utc* value is fixed and cannot be changed.

The *span* value (processed by :meth:`TimeSpan.parse`) forms the internal state.
It can be retrieved with :meth:`TimeSpan.get_state`.

Upon receipt of a ``'reconfig'`` event, the block discards the old settings
and replaces them with the new values. To modify the settings, retrieve the
current values, edit them and send an event.

The block supports state persistence. The *persistent* parameter is described
:ref:`here <Base class arguments>`. Set to ``True`` to make the internal
state persistent.

If a saved state exists, it has higher precedence than the arguments.
The arguments are only a default value and as such are copied to the
:data:`TimeSpan.initdef` variable. An *initdef* argument is not accepted
though.

Monitoring aid
--------------

Blocks :class:`TimeDate` and :class:`TimeSpan` are implemented as clients
of an internal "cron" service. This service has a form of a common :class:`SBlock`.

The name of this automatically created block  is ``_cron_local`` or ``_cron_utc``
for local or UTC time respectively. It accepts an event named ``'get_schedule'``
and responds with a dump of the internal scheduling data in the form of a dict:
``{"HH:MM:SS": [block_names_to_recalculate]}``.


Counter
=======

.. class:: Counter(name, *, modulo=None, initdef=0, persistent=False, **kwarg)

  A counter.

  If *modulo* is set to a number M, count modulo M.
  For a positive integer M it means to count only from 0 to M-1
  and then wrap around. If *modulo* is not set, the output value
  is not bounded.

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

  The counter can process floating point numbers.


Repeat
======

.. class:: Repeat(name, *, dest, etype='put', interval, count=None, **block_kwargs)

  Periodically repeat the last received event.

  For a predictable operation only one selected event type *etype*
  is repeated. All other events are ignored. This limitation can
  be easily overcome with multiple ``Repeat`` blocks operating in parallel,
  if need be. Only events identified by a string can be repeated.

  The event is sent to the destination block specified by *dest*, which can
  be an instance or its name. The received event is re-sent immediately
  and then duplicates are sent in time intervals specified by *interval*
  which may be given as a number of seconds or as a
  :ref:`string with time units<Time intervals with units>`.

  The number of repetitions may be limited with *count*. If not ``None``,
  at most *count* duplicates are sent. The original event is always re-sent
  and not counted.

  A Repeat block saves the event data item ``'source'`` to ``'orig_source'``,
  because the block itself will become the source. It also adds a ``'repeat'``
  count value. The original event is sent with ``repeat=0``,
  subsequent repetitions are sent with ``repeat=N`` where N is 1, 2, 3, ...
  This repeat value is also copied to the output, the initial output is 0.

  .. note::

    The Event block is intended to repeat output events and thus minimize
    the chance that some connected system will fail to act due to external
    reasons. For a source of periodic events use a :class:`Timer` instead.


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

  The ``Timer`` accepts all standard :ref:`FSM parameters`:

  :param t_on:
    ``'on'`` state timer duration
  :param t_off:
    ``'off'`` state timer duration
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

  A conditional event :class:`EventCond`\ ``('start', 'stop')``
  is often used for ``Timer`` control.


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

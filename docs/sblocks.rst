=========================
List of sequential blocks
=========================

Only block specific properties are documented here. For
a description of common arguments like *initdef* or *persistent*
please refer to the :ref:`base class<Base class arguments>`.


Inputs
======

Feeding data into the circuit
-----------------------------

.. important::

  :meth:`edzed.SBlock.event` is the data input entry point.

.. important::

  Always check if the circuit is ready before forwarding external
  events to blocks. If not ready, the result is undefined!
  Refer to :meth:`Circuit.is_ready`.

----

Depending on your application's needs, any sequential block
may serve as a part of the circuit's input interface.

The most common data entry block is the :class:`Input`:

.. class:: edzed.Input(*args, schema=None, check=None, allowed=None, **kwargs)

  An input block with optional value validation.

  .. note::

    Of course, you *should* validate input data.

  The :class:`Input` accepts only ``'put'`` events.
  It stores and outputs the ``'value'`` data item sent with the event
  provided that it validates successfully. It returns ``True``
  if the new value is accepted, ``False`` otherwise.

  Arguments - initialization:

  - *persistent*
      If true, initialize from the last known value.
  - *initdef*
      Default value; must pass the validators.

  Arguments - optional validators of input values:

  - *check*
      A value test function.
      If the function's return value evaluates to true,
      new value is accepted, otherwise it is rejected.
  - *allowed*
      A sequence or set of allowed values.
      This is roughly equivalent to::

        check=lambda value: value in ALLOWED
  - *schema*
      A function possibly modifying (preprocessing) the value.
      If the function raises, value is rejected,
      otherwise the input is set to the returned value.

  It is recommended to use only one validator, but any
  combination of *schema*, *check* and *allowed* is allowed.

  *Schema* is the only validator capable of changing the value.
  It is called last to ensure all validators test the original
  input value.


.. class:: edzed.InputExp(*args, duration, expired=None, **kwargs)

  Like :class:`edzed.Input`, but after certain time after the ``'put'`` event
  replace the current value with the *expired* value.

  An InputExp takes the same arguments as :class:`edzed.Input`
  plus two additional ones:

  - *duration*
      The default duration in seconds before a value expires.
      Can be overridden on a per-event basis. Enter:

      - a numeric value, or
      - a :ref:`string with time units<Time intervals with units>`, or
      - ``None`` for no default duration. Without a default,
        every event must explicitly specify the duration.

  - *expired*
      A value to be applied after expiration; must pass the validators.

  If a ``'duration'`` item (with the same format as *duration* argument)
  is present in the event data, it overrides the default duration.

Polling data sources
--------------------

A specialized block is provided for this task:

.. class:: edzed.ValuePoll(*args, func, interval, **kwargs)

  A source of measured or computed values.

  This block outputs the result of an acquisition function *func* every
  *interval* seconds. The *interval* may be written also as a
  :ref:`string with time units<Time intervals with units>`.
  The *func* may be a regular or an async function, but not a coroutine.
  (reminder: ``async def aex(...):`` -- ``aex`` is a function and
  ``aex()`` is a coroutine)

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
    and no output change will happen.

  Initialization rules:

  If the very first value is not obtained within the *init_timeout*
  limit, the *initdef* value will be used as a default. If *initdef*
  is not defined, the initialization fails.


Outputs
=======

The output blocks invoke a function in response to a ``'put'`` event.

.. tip::

  See also the :class:`edzed.Repeat` block. Repeated output actions
  may increase the robustness of applications where it is appropriate.
  Note: actions that may be repeated without changing the result are called *idempotent*.


.. class:: edzed.OutputFunc(*args, func, on_success=(), on_error=None, stop_value=UNDEF, **kwargs)

  Call a function when a value arrives.

  The function *func* is called with a single argument, the ``'value'``
  item from the event data.

  The block can be instructed to trigger
  *on_success* and *on_error* :ref:`events<Generating events>`
  depending on the result of the function call. Any returned value is
  considered a success, and the value is added to the *on_success* event data
  as ``'value'``. An exception means an error, the exception is added to
  the *on_error* event data as: ``'error'``.

  By default *on_error* is set to ``edzed.Event('_ctrl', 'error')`` which
  terminates the simulation (see the :class:`edzed.ControlBlock`). To handle the
  error differently or to ignore it, set the *on_error* explicitly.

  If the *stop_value* is defined, it is fed into the block
  during cleanup and processed as the last item before stopping.
  This allows to leave the controlled process in a well-defined state.

  The output of an OutputFunc block is always ``False``.

.. class:: edzed.OutputAsync(*args, coro, guard_time=0.0, qmode=False, on_success=(), on_error=None, stop_value=block.UNDEF, **kwargs)

  Run a coroutine *coro* as an asycio task when a value arrives.

  The coroutine is invoked with a single argument, the ``'value'``
  item from the event data.

  There are two operation modes: the noqueue mode (*qmode* is ``False``,
  this is the default) and the queue mode (*qmode* is ``True``). The
  difference is in the behavior when a new value arrives before
  processing of the previous one has finished:

  - In the noqueue mode the task processing the previous value will be
    cancelled (and awaited) if it is still running. All unprocessed
    values except the last one are dropped.

  - In the queue mode all values are enqueued and processed one by one
    in order they have arrived. This may introduce delays. Make sure
    the coroutine can keep up with the rate of incoming values.

  The output of an OutputAsync block is a boolean busy flag:
  ``True``, when the block is running a task; ``False`` when idle.

  The block can trigger *on_success* and *on_error* :ref:`events<Generating events>`
  depending on the result of the task. A normal termination is
  considered a success (the returned value is added to the *on_success* event data as ``'value'``).
  An exception other than :exc:`asyncio.CancelledError` means an error
  (the exception is added to the *on_error* event data as ``'error'``).
  A cancelled task does not trigger any events.

  By default *on_error* is set to ``edzed.Event('_ctrl', 'error')`` which
  terminates the simulation (see the :class:`edzed.ControlBlock`). To handle the
  error differently or to ignore it, set the *on_error* explicitly.

  If the *stop_value* is defined, it is inserted into the queue
  and processed as the last item before stopping. This allows to leave
  the controlled process in a well-defined state. As this happen
  during the stop phase, make sure the *stop_timeout* gives enough time
  for a successful output task run.

  The *guard_time* is the duration of a mandatory and uncancellable sleep
  after each run of the output task. No output activity can
  happen during the sleep. The purpose is to limit the frequency
  of actions, for instance when controlling a hardware switch.
  Default value is 0.0 [seconds], i.e. no guard_time. The *guard_time*
  must not be longer than the *stop_timeout*.


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

----

.. class:: edzed.TimeDate(*args, times=None, dates=None, weekdays=None, utc=False, **kwargs)

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
      and right-open intervals, i.e. ``TimeFrom`` <= time < ``timeTo``.

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

      Unused arguments are given as ``None``. This is different
      than an empty string or an empty sequence. An empty value is
      a valid argument meaning no time or no date or no weekday and
      such block always outputs ``False``.

  The numeric form of parameters is used internally. Strings are converted
  to numbers before use. The internal parser is available should the need arise:

  .. classmethod:: parse(times, dates, weekdays) -> dict

      Parse the arguments, return a dict with keys ``'times'``, ``'dates'``, ``'weekdays'``
      and values in the numeric form, i.e. as lists or nested lists of integers or ``None``.


Dynamic updates
---------------

A :class:`edzed.TimeDate` block can be reconfigured during a simulation
by a ``'reconfig'`` event with event data containing items
``'times'``, ``'dates'`` and ``'weekdays'`` with exactly the same format,
meaning and default values as the block's arguments with the same name.
The *utc* value is fixed and cannot be changed.

The mentioned three values (processed by :meth:`edzed.TimeDate.parse`) form the
internal state. They can be retrieved with :meth:`TimeDate.get_state`.

Upon receipt of a ``'reconfig'`` event, the block discards the old settings
and replaces them with the new values. To modify the settings, retrieve the
current values, edit them and send an event.

The block supports state persistence. The *persistent* parameter is described
:ref:`here <Base class arguments>`. Set to ``True`` to make the internal
state persistent. It is only useful with dynamic updates, that's why it is
documented here.

If a saved state exists, it has a precedence over the arguments.
The arguments are only a default value and as such are copied to the
:data:`TimeDate.initdef` variable. An *initdef* argument is not accepted
though.


Counter
=======

.. class:: edzed.Counter(*args, modulo=None, initdef=0, **kwarg)

  A counter.

  If *modulo* is set to a number M, count modulo M.
  For a positive integer M it means to count only from 0 to M-1
  and then wrap around. If *modulo* is not set, the output value
  is not bounded.

  Arguments:

  - *persistent*
      if true, initialize from the last known value
  - *initdef*
      initial value, 0 by default

  Accepted events and relevant data items:

  - ``'inc'``
     increment (count up) by 1 or by the value of ``'amount'`` data item
     if such item is present in the event data
  - ``'dec'``
     decrement (count down) the counter by 1 or by ``'amount'``
  - ``'put'``
     set to ``'value'`` data item (mod M)

  The counter can process floating point numbers.


Repeat
======

.. class:: edzed.Repeat(*args, dest, etype='put', interval, **kwargs)

  Periodically repeat the last received event.

  For a predictable operation only one selected event type *etype*
  is repeated. All other events are ignored. This limitation can
  be easily overcome with multiple Repeat blocks operating in parallel,
  if need be.

  A Repeat block saves the event data item ``'source'`` to ``'orig-source'``,
  because the block itself will become the source. It also adds a ``'repeat'`` value.
  The original event is sent with ``repeat=False``,
  subsequent repetitions are sent with ``repeat=True``. This repeat value
  is also copied to the output, the initial output is ``False``.

  Arguments:

  - *dest*
      Destination block, an instance or a name.

  - *etype*
      Type of events to process, default is ``'put'``.

      .. important::

        Only events identified by a string can be repeated.

  - *interval*
      Time interval between repetitions in seconds
      or as a :ref:`string with time units<Time intervals with units>`


Simulator control block
=======================

.. class:: edzed.ControlBlock

 .. note::

  A ControlBlock named ``'_ctrl'`` will be automatically created if
  there is a reference to this name in the circuit.

 The simulator control block accepts two event types:

 - ``'shutdown'``
    Shut down the circuit.

 - ``'error'``
    Stop the simulation due to an error. An ``'error'`` item
    must be present in the event data, its value could be an :exc:`Exception`
    object or just an error message.

 There is no reason to have more than one control block in an circuit.

 The output value is fixed to ``None``.

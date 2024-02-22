.. currentmodule:: edzed

=======================================================
List of sequential blocks 2/2 - time and date intervals
=======================================================

List of sequential blocks offered by the ``edzed`` library - second part.

Specifying intervals
====================

Top level overview
-------------------

``Edzed`` supports intervals of three distinct types:

- times of day,
- dates within year,
- full dates with time.

An interval is a sequence of ranges (sub-intervals). A range is defined by
its two endpoints: start and stop.

There are two main alternatives for interval specification:

- human readable strings
- nested sequences of integers for computer processing. In Python, a sequence
  is usually a list or a tuple. 

A detailed description follows. It covers topics from the basic endpoints
up to the whole interval definition.


1. Range endpoints
------------------

1A. Traditional string formats for date and time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- time of day (e.g. ``'6:45:00'`` or ``'15:55'`` or ``'09:59:59.999'``)

  The time format is H:M:S or just H:M with a 24-hour clock.
  Hours, minutes and seconds may have one or two digits.
  Seconds may have a fractional part with 1 to 6 digits
  after a decimal point or a decimal comma.
  The day starts and also ends at midnight ``'0:0:0'``.

  .. versionadded:: 24.3.4 fractional seconds

- date within a year (e.g. ``'April 1'`` or ``'1.apr'``)

  The date is defined as a day and a month in any order.

  - day = one or two digits
  - month = English month name, may be abbreviated to three or more characters.
    Case insensitive.
  - one period (full stop) may be appended directly after the day or the month.

- complete date and time (e.g ``'April 1 1984 8:00'`` or ``'1984-APR-01 8:00'``)

  A complete date with time consist of year, month, day and the time of day.

  Supported formats are:

    - YYYY month day time-of-day
    - YYYY-MM-DD time-of-day
    - YYYY-month-DD time-of-day

  where the listed parts may by given in any order. The year YYYY is a 4-digit integer.
  MM and DD must have exactly two digits. The month, day and time-of-day
  are as described above.

Extra whitespace is ignored.


1B. ISO 8601 string formats for date and time
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. important::

  - The underlying support for ISO 8601 dates and times were added to Python
    in version 3.11. Parsing these formats with older Python versions will
    likely fail.
  - ``edzed`` accepts only times without a time zone.

- time of day (e.g. ``'T06:45:00'`` or ``'15:55'`` or ``'09:59:59,999'``)

  Refer to the
  `Python documentation with examples
  <https://docs.python.org/3/library/datetime.html#datetime.time.fromisoformat>`__

- date within a year (e.g. ``--1231'``)

  There is no valid ISO 8601 format for a day with an implied year. We are using
  ``'--MMDD'`` and ``'--MM-DD'`` as the closest approximation. (They were part
  of the standard in the past)

- date+time (e.g. ``'2025-10-20T06:45:00'`` or ``'20251020T0645'``)

  Refer to the
  `Python documentation with examples
  <https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat>`__

.. versionadded:: 24.3.4


1C. Date and time as sequences of integers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- time of day (e.g. ``[6, 45, 0]``)

  A time is defined by ``(hour, minute=0, second=0, microsecond=0)``, i.e. a sequence
  of one to four integers. The optional values default to zero.

- date (without a year) (e.g. ``[12, 31]``)

  Exactly two integers specify a date: ``(month, date)``

- date+time (e.g. ``[2025, 10, 20, 6, 45]``)

  Seven integers define a full date and time. The last two values are optional
  and default to zero:
  ``(year, month, date, hour, minute, second=0, microsecond=0)``

.. versionadded:: 24.3.4 microseconds


2. Ranges (sub-intervals)
-------------------------

A range is defined by its endpoints and contains all moments from start
to stop:

- ``5:00 - 7:30`` - from five o'clock to half past seven (every day)
- ``Mar 3 - Mar 4`` - two days in the March - 3rd and 4th (every year)

When the stop endpoint is before the start endpoint, periodic events
retain their usual meaning:

- ``22:00 - 00:30`` - means from 22:00 to 00:30 next day
  (duration 2 hours and 30 minutes)
- ``10.Dec - 15.Jan`` - means from the December 10th up to and including
  the 15th day of the following month.

Compare with a non-periodic event:

- ``2030-01-01 0:0 / 2015-01-01 0:0`` - never active (start after stop)


2A. Range strings
^^^^^^^^^^^^^^^^^

Range strings are created by joining the endpoints with a separator:

  range = "<start-endpoint> <separator> <stop-endpoint>"

The separator is either a hyphen ``'-'`` or a forward slash ``'/'``.

.. versionadded:: 24.3.4 the slash separator

**Special case:** for readability sake, a one-day range like ``"Feb 5 - Feb 5"`` can be written
as ``"Feb 5"``.


2B. Range sequences
^^^^^^^^^^^^^^^^^^^

A range in the form of a sequence is a pair ``[start_endpoint, end_endpoint]``,
where the endpoints may be strings or sequences.


3. Intervals
------------

An interval aggregates any number of ranges (sub-intervals). It may be empty.


3A. Interval strings
^^^^^^^^^^^^^^^^^^^^

Interval strings are created by joining the ranges with a delimiter. There
are two choices: either a comma ``','`` or a semicolon ``';'``. Only one type
of delimiters can be used in a single interval string.

  interval = "<range1> <delimiter> <range2> <delimiter>  ... <rangeN>"

The delimiter may be used also as a terminator.

  interval = "<range1> <delimiter> <range2> <delimiter> ... <rangeN> <delimiter>"

.. versionadded:: 24.3.4 semicolon delimiter, trailing delimiter

**Best practices for string intervals**

Adding support of ISO 8601 formats to the existing parser while maintaining
backward compatibility has created some potential issues. They could be worked
around by choosing slightly different format, but to be safe follow
these recommendations:

.. important::

  In order to fully avoid problems mentioned below:

    - Use ``'/'`` as an endpoint separator - the ISO standard.
    - Use ``';'`` as a range **terminator**.
  

1. Problem using the hyphen separator with dates containing hyphens as well::

    "2020-01-01T12:00-2025-12-31T12:00"   # ambiguous, parsing will fail!
         ^  ^        ^    ^  ^            # which hyphen is the separator?

    "2020-01-01T12:00 - 2025-12-31T12:00" # solution:
                     ^^^                  # add spaces around the separator

    "2020-01-01T12:00/2025-12-31T12:00"   # better solution:
                     ^                    # separate with a slash (spaces optional)


2. Problem using the comma delimiter with times containing
   a decimal comma::

    "T041010,5/T0411,134355,5/1344"     # ambiguous, parsing will fail!
            ^       ^      ^            # which comma is the delimiter?

    "T041010,5/T0411 , 134355,5/T1344"  # still wrong!
            ^        ^       ^          # adding spaces won't help here

    "T041010,5/T0411; 134355,5/T1344"   # solution:
                    ^                   # use the semicolon delimiter

    "T041010,5/T0411; 134355,5/T1344;"  # better solution:
                    ^               ^   # terminate ranges with the delimiter
    "T041010,5/T0411;"                  # it is mandatory for one-range intervals
                    ^                   # with a decimal comma


3B. Interval sequences
^^^^^^^^^^^^^^^^^^^^^^

Interval sequences are sequences of ranges in any valid form - string type
or sequence type.


Interval object types
---------------------

Short summary::

  Date_Time_Type = str|Sequence[int]
  # sequence length: time = 1..4, date = 2, datetime = 5..7

  Date_Time_Range_Type = str|Sequence[Date_Time_Type]
  # sequence length = 2

  Date_Time_Interval_Type = str|Sequence[Date_Time_Range_Type]|set[Date_Time_Range_Type]
  # sequence length | set size = any

- the type names are for illustration only
- related ``edzed`` functions generate nested sequences of integers
  always with the full length (i.e. time values with four items)
  and sorted.


Periodic events
===============

.. class:: TimeDate(name, *, times=None, dates=None, weekdays=None, utc: bool = False, **block_kwargs)

  Block for periodic events occurring daily, weekly or yearly. A combination
  of conditions is possible (e.g. Every Monday morning 6 to 9 a.m., but only in April)

  If *utc* is ``False`` (which is the default), times are in the local timezone.
  If *utc* is ``True``, times are in UTC.

  The output is a boolean.
  When *times*, *dates* and *weekdays* are all ``None``, the output is ``False``.
  To configure the block define at least one of them.
  The output is then ``True`` only when the current time, date and the weekday
  match the specified arguments. Unused arguments are not taken into account.

  - *times*
      Optional :ref:`time interval<Interval object types>`.

      Examples (same values in each line)::

        times="23:50 - 01:30, 3:20-5:10"
        times="T2350 / T0130; T03:20/T05:10;"
        times=[[[23,50],[1,30]], [[3,20],[5,10]]]
        times=[
          [[23,50,0,0], [1,30,0,0]],  # range 1
          [[ 3,20,0,0], [5,10,0,0]],  # range 2
          ]

  - *dates*
      Optional :ref:`date interval<Interval object types>`.

      Examples (strings)::

        dates="02Mar-15MAR, 9.july - 20.aug."
        dates="Sept1-Sept2, DEC 31 - JAN 05"
        dates="--0901/--0902; --1231/--0105;"
        dates="May 4"

      Examples (sequences, same values as above)::

        dates=[[[3,2],[3,15]], [[7,9],[8,20]]]
        dates=[[[9,1],[9,2]], [[12,31],[1,5]]]
        dates=[[[5,4],[5,4]]]


  - *weekdays*
      An optional list of weekday numbers, where:

        0=Sunday, 1=Monday, ... 5=Friday, 6=Saturday, 7=Sunday (same as 0)

        .. note::

          The weekday numbers in the standard library:

          - compatible with ``edzed``:

            - :func:`time.strftime` (directive ``"%w"``): 0 (Sunday) to 6 (Saturday)
            - :meth:`datetime.date.isoweekday`: 1 (Monday) to 7 (Sunday)

          - not compatible with ``edzed`` (add/substract 1 to adjust):

            - :meth:`datetime.date.weekday` and :data:`time.struct_time.wday`: 0 (Monday) to 6 (Sunday)

      Examples:

      - as a string:

        | ``weekdays="12345"`` (working days)
        | ``weekdays="67"``    (the weekend)

      - or in a numeric form:

        | ``weekdays=[1, 2, 3, 4, 5]``
        | ``weekdays=[6, 7]``

  .. note::

      Unused arguments *times*, *dates*, or *weekdays* are given as ``None``.
      This is different than an empty string or an empty sequence.

      - ``None`` means we don't care which time, date or weekday respectively.
        **Exception**: if all three parameters are ``None``, the block is disabled
        (unconfigured).

      - An empty value is a valid argument meaning no matching time or
        date or weekday. A ``TimeDate`` block with an empty parameter
        always outputs ``False``.

  The numeric form of parameters is used internally. Strings are converted
  to numbers before use. The internal parser is available should the need arise:

  .. classmethod:: parse(times, dates, weekdays) -> dict[str, list|None]

      Parse the arguments in any format accepted by the ``TimeDate``,
      return a dict with keys ``'times'``, ``'dates'``, ``'weekdays'``
      and values in the numeric form, i.e. as lists or nested lists of integers
      or ``None``.


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
:ref:`here <Sequential blocks>`. Set to ``True`` to make the internal
state persistent. It is only useful with dynamic updates, that's why it is
documented here.

If a saved state exists, it has higher precedence than the arguments.
The arguments are only a default value and as such are copied to the
:data:`TimeDate.initdef` variable. An *initdef* argument is not accepted
though.

Non-periodic events
===================

.. class:: TimeSpan(name, *, span=(), utc: bool = False, **block_kwargs)

  Block for non-periodic events occurring in ranges between start and stop
  defined with full date and time, i.e. year, month, day, hour, minute and second
  (may be fractional). Any number of ranges may be specified, including zero.

  If *utc* is ``False`` (which is the default), times are in the local timezone.
  If *utc* is ``True`` times are in UTC.

  The output is a boolean and it is ``True`` when the current time and date are inside
  of any of the ranges.

  The *span* argument is a :ref:`date+time interval<Interval object types>`. It is
  not optional. The default value is an empty sequence resulting in constant 'False'
  on output.

  Example (string)::

    span="2020 March 1 12:00 - 2020 March 7 18:30," \
         "10:30 Oct. 10 2020 - 22:00 Oct.10 2020"

  Example (sequence, same value as above)::

    span=[
      [[2020,  3,  1, 12,  0],    [2020,  3,  7, 18, 30]   ],
      [[2020, 10, 10, 10, 30, 0], [2020, 10, 10, 22,  0, 0]],
      ]

  The numeric form of parameters is used internally. A string is converted
  with this parser:

  .. classmethod:: parse(span) -> list

      Parse the *span* in any form accepted by the ``TimeSpan`` and return a list of intervals,
      where each interval is defined by a pair of lists with 7 integers
      ``[year, month, day, hour, minute, second. microsecond]``.

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
:ref:`here <Sequential blocks>`. Set to ``True`` to make the internal
state persistent.

If a saved state exists, it has higher precedence than the arguments.
The arguments are only a default value and as such are copied to the
:data:`TimeSpan.initdef` variable. An *initdef* argument is not accepted
though.

Monitoring aid
==============

Blocks :class:`TimeDate` and :class:`TimeSpan` are implemented as clients
of an internal "cron" service. This service has a form of a common :class:`SBlock`.

The name of this automatically created block  is ``'_cron_local'`` or ``'_cron_utc'``
for local or UTC time respectively. It accepts an event named ``'get_schedule'``
and responds with a dump of the internal scheduling data in the form of a dict:
``{"HH:MM:SS[.sss]": [list of block names to recalculate]}``.


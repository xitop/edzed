.. module:: edzed.utils

=======================
Miscellaneous utilities
=======================

Time durations with units
=========================

Time is measured in seconds, but edzed classes accept also
durations and time periods represented as strings with larger
time units day, hour and minute.

**The traditional format:**

  DURATION = [n D] [n H] [n M] [n S]

  Examples:

    | ``'2m'`` = 2 minutes = 120.0 seconds
    | ``'20h15m10'`` = 20 hours + 15 minutes + 10 seconds = 72_910.0
    | ``'2d 12h'`` = 2 days + 12 hours = 21_6000.0
    | ``'1.25h'`` = 1 and a quarter of and hour = 4_500.0

  .. versionchanged:: 24.3.4

    - An empty string is now rejected.
    - A decimal comma may be used.
    - Previously, fractional numbers were allowed only for seconds.

**The ISO 8601 format:**

  DURATION = P [0Y] [0M] [nD] T [nH] [nM] [nS]

  Description with examples: `Wikipedia <https://en.wikipedia.org/wiki/ISO_8601#Durations>`__

  .. versionadded:: 24.3.4

**Notes:**

  Both formats:

  - At least one part of the duration string must be present.
  - Only the smallest unit may have a fractional part.
    Both decimal point and decimal comma are supported.
  - Numbers do not have to be normalized, e.g. ``'72H'`` is fine.

  Traditional format only:

  -   Unit symbols ``D``, ``H``, ``M``, ``S`` may be entered also in lower case.
  -   Whitespace around numbers and units is allowed.

  ISO format only:

  - the largest usable unit is a day. Calendar years and months
    are not supported and must be set to 0 if present.

----

Conversions routines:

.. function:: timestr(seconds: int|float, sep: str = '', prec: int = 3) -> str

  Convert *seconds*, return a string with time units.

  The individual parts are separated with the *sep* string.

  Minutes (``m``) and seconds (``s``) are always present in the result.
  Days (``d``) and hours (``h``) are prepended only when needed.

  If the input value is a float, fractional seconds are formatted
  to *prec* decimal places.

  This is an inverse function to :func:`convert` below provided
  the separator is empty or whitespace only.

.. function:: timestr_approx(seconds: int|float, sep: str = '') -> str

  Convert *seconds* to a string using ``d``, ``h``, ``m``, and ``s``
  units with limited precision.

  The individual parts are separated with the *sep* string.

  This is an alternative to :func:`timestr`. It rounds off the least
  significant part of the value to make the result shorter and better
  human readable. Depending on the value magnitude, the seconds'
  decimal places are gradually reduced from three down to zero and
  for large values the seconds or even the minutes are omitted entirely.

  Compare:

  .. csv-table::
    :align: left
    :header: "timestr", "timestr_approx"

    "0m20.053s", "20.1s"
    "1d2h11m7.029s", "1d2h11m"
    "10d3h5m4.120s", "10d3h"


.. function:: convert(timestring: str) -> float

  Convert a :ref:`timestring<Time durations with units>` to number of seconds.
  See also the next function.

.. function:: time_period(period: int|float|str) -> float
.. function:: time_period(period: None) -> None
  :noindex:

  This is a convenience function accepting all time period formats used in ``edzed``:

  - ``time_period(None)`` returns ``None``.

  - ``time_period(number)`` returns the number as :class:`float`. Negative values are converted to ``0.0``.

  - ``time_period(string)`` converts the string with :func:`convert`.



Clock and calendar related constants
====================================

.. data:: SEC_PER_DAY
          SEC_PER_HOUR
          SEC_PER_MIN

    Seconds per day, hour, minute (integers).

.. data:: MONTH_NAMES

    English names for months 1 to 12, e.g. ``MONTH_NAMES[3]`` is ``"March"``.


Improved asyncio.shield
=======================

Use :func:`shield_cancel` to protect small critical
task sections from immediate cancellation.

.. function:: shield_cancel(aw: Awaitable) -> Any
  :async:

  Shield from cancellation while *aw* is awaited.

  Any pending :exc:`asyncio.CancelledError` is raised when *aw* is finished.

  Make the shielded code and its execution time as short as possible.

  .. warning:: Never suppress task cancellation completely!


Name to block resolver
======================

When referencing a circuit block, ``edzed`` generally allows to use
either a block name or a block object.

At some point the names need to be resolved, because the software works
only with objects internally. The resolver is a service provided by the
:doc:`circuit simulator<simulation>`.

.. method:: Circuit.resolve_name(obj, attr: str, block_type: type[Block] = edzed.Block)

  Register an object with the resolver.

  The object *obj* should be storing a reference to a circuit block
  in its attribute named *attr*.

  - If the reference is a name (i.e. a string), register the object
    to be processed by the resolver. The resolver will then replace the
    name by the corresponding block object and check its type
    before the simulation starts.

  - If the reference is a block object already, name resolving
    is not needed. Just check the type and return.

  The *block_type* is the required type of the referenced block.
  A :exc:`TypeError` is raised if the block is not an instance of this type.

Inverted output
---------------

The name to block resolver supports the ``'_not_NAME'`` notation, where the name
is derived from another block's NAME by prepending a ``'_not_'`` prefix.
The original NAME must not begin with an underscore.

This is a shortcut for connecting a logically inverted output. A new
:class:`Not` block will be created automatically if it does not
exist already::

  edzed.Not('_not_NAME').connect(NAME)

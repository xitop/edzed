=======================
Miscellaneous utilities
=======================

Time intervals with units
=========================

Time is measured in seconds, but edzed classes accept also
time periods written as strings with other usual time units, e.g.:

  | ``'2m'`` = 2 minutes = 120.0 seconds
  | ``'20h15m10'`` = 20 hours + 15 minutes + 10 seconds = 72910.0
  | ``'2d 12h'`` = 2 days + 12 hours = 216000.0

Format:
  TIMESTRING = [DAYS] [HOURS] [MINUTES] [SECONDS]

  where:
    - DAYS = <int> "D"
    - HOURS = <int> "H"
    - MINUTES = <int> "M"
    - SECONDS =  <int or float> ["S"]

Notes:
  - whitespace around numbers and units is allowed
  - numbers do not have to be normalized, e.g. ``'72h'`` is fine
  - unit symbols ``D``, ``H``, ``M``, ``S`` may be entered in upper or lower case
  - negative values are not allowed
  - float values with exponents are not supported

----

Conversions routines:

.. module:: edzed.utils.timeunits

.. function:: timestr(seconds: Union[int, float]) -> str

  Convert seconds, return a string with time units.

  Minutes (``m``) and seconds (``s``) are always present in the result.
  Days (``d``) and hours (``h``) are prepended only when needed.

  Partial seconds are formatted to 3 decimal places.

.. function:: convert(timestring: str) -> float

  Convert a string to number of seconds. See also the next function.

.. function:: time_period(period: Union[None, int, float, str]) -> Optional[float]

  This is a convenience function accepting all time period formats used in ``edzed``.

  ``time_period(None)`` returns ``None``.

  ``time_period(number)`` returns the number as :class:`float`. Negative values are converted to ``0.0``.

  ``time_period(string)`` converts the string with :func:`convert`.



Clock and calendar related constants
====================================


.. module:: edzed.utils.tconst

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

.. module:: edzed.utils.shield_cancel

.. function:: shield_cancel(aw: Awaitable) -> Any
  :async:

  Shield from cancellation while *aw* is awaited.

  Any pending :exc:`asyncio.CancelledError` is raised when *aw* is finished.

  Make the shielded code and its execution time as short as possible.

  .. warning:: Never suppress task cancellation completely!

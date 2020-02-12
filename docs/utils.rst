=======================
Miscellaneous utilities
=======================

Time intervals with units
=========================

Time is measured in seconds, but several edzed classes accept also
time spans written as strings with other usual time units, e.g.:

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

A complementary pair of conversion routines is provided:

.. module:: edzed.utils.timeunits

.. function:: convert(timestring: str) -> float

  Convert a string to number of seconds. See the description above.

.. function:: timestr(seconds: Union[int, float]) -> str

  Convert seconds, return a string with time units.

  Minutes (``m``) and seconds (``s``) are always present in the result.
  Days (``d``) and hours (``h``) are prepended only when needed.

  Partial seconds are formatted to 3 decimal places.


Clock related constants
=======================

Seconds per day, hour, minute (integers):

.. module:: edzed.utils.tconst

.. data:: SEC_PER_DAY
          SEC_PER_HOUR
          SEC_PER_MIN


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

=========
Changelog
=========

20.3.8
======

- No new features, only the version numbering scheme was changed.
  This change makes an upgrade not possible. Please remove and reinstall.
  Sorry for the inconvenience.

----

.. note::

  The early releases below used an incompatible version numbering.

2020.2.25
---------

- :class:`edzed.FuncBlock` now checks if the function signature
  is compatible with the connected inputs. This helps to find
  an error more quickly.

2020.2.24
---------

- :class:`edzed.TimeSpan` was added

2020.2.23
---------

- The :class:`edzed.TimeDateUTC` block was removed,
  use :class:`edzed.TimeDate` with ``utc=True`` instead.

- The specification of :class:`edzed.TimeDate`\'s arguments
  *dates*, *times*, or *weekdays* was updated.

- The :class:`edzed.TimeDate` now supports dynamic updates.

2020.2.11
=========

First public release.

.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).

20.9.10
=======

- :meth:`Circuit.finalize` and :attr:`Circuit.error` were added
- documentation: symbol references are printed without the ``edzed`` package name

20.9.5
======

- :ref:`Event filters`: (incompatible change) the meaning of the returned value
  was altered.

20.8.23
=======

- tests: asyncio warnings were fixed.
- tests: timing tests were modified in order to reduce false negative results.

20.8.4
======

- The :func:`DataEdit.modify` event filter was added.

20.3.8
======

- No new features, only the version numbering scheme was changed.
  This change makes an upgrade not possible. Please remove and reinstall.
  Sorry for the inconvenience.

----

Releases with old version numbering
===================================

.. note::

  The early releases below used an incompatible version numbering.

2020.2.25
---------

- :class:`FuncBlock` now checks if the function signature
  is compatible with the connected inputs. This helps to find
  an error more quickly.

2020.2.24
---------

- :class:`TimeSpan` was added

2020.2.23
---------

- The :class:`TimeDateUTC` block was removed,
  use :class:`TimeDate` with ``utc=True`` instead.

- The specification of :class:`TimeDate`\'s arguments
  *dates*, *times*, or *weekdays* was updated.

- The :class:`TimeDate` now supports dynamic updates.

2020.2.11
---------

First public release.

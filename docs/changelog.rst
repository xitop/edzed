.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).


25.4.25
=======

- Remove the deprecated ``SBlock.put()``.
- Update pytest configuration.

24.11.25
========

- Fix an incorrect test. The module itself was not changed.
  The bug was in test_timedate.py.

24.9.10
=======

- When exiting :func:`run`, do not wrap exceptions into a ``RuntimeError``.
- Edzed is not compatible with the asyncio eager tasks feature.
  Add a run-time check.
- Use the standard 'warning' module for deprecation warnings.
- Add a test for circular references caused by exceptions.
  This test is experimental. The reference cycles are harmless,
  but they increase overhead.
- Documentation: Correct the minimal Python version in requirements.
  It's Python >= 3.9.

24.3.4
======

- Improve :ref:`time/date intervals<List of sequential blocks 2/2 - time and date intervals>`:

  - Accept microseconds in time specifications.
    However, a microsecond precision cannot be expected
    from an asyncio based Python program.
  - Accept ISO 8601 time/date strings.
    (This feature is based based on Python's support of ISO formats which was
    quite limited in versions prior to 3.11.)
  - Introduce new endpoint separator and interval delimiter
    in order to solve ambiguities. The old syntax remains
    supported.
  - Rewrite time/date related functions using the standard
    `datetime <https://docs.python.org/3/library/datetime>`_
    module wherever possible.
  - Rewrite the :ref:`cron internal service <Monitoring aid>`.
    An issue with the schedule reload was found and fixed during the rewrite.

- Enhance the support for :ref:`durations with units<Time durations with units>`.
- Remove support for Python 3.8.
- Add latest Python 3.12 to the list of compatible versions.
- Improve compliance with the ``mypy`` type checker.
- Put ``pylint`` configuration into the ``pyproject.toml`` file.

23.8.25
=======

- Make interfacing with external systems easier:

  - In :func:`run` start supporting tasks after the simulation task.
  - Add :class:`ExtEvent` for events received from external systems.
    This implies further changes:

    - The existing :class:`Event` should be used for internally generated
      events only.
    - :meth:`SBlock.event` should not be used as an event entry point
      for external events.
    - The shortcut :meth:`SBlock.put` is deprecated because ``SBlock.event()``
      lost its importance.
- Document the attributes :attr:`Event.dest` and :attr:`Event.etype`
  (also present in :class:`ExtEvent`).
- Improve the code compliance with the ``mypy`` static type checker.


Older releases
==============

Only recent changes are listed here.
See the git repository for the full history.

- first stable release was 21.5.15
- first public release is dated February 2020

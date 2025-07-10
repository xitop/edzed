.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).

25.7.10
=======

- Edzed is now compatible with eager asyncio tasks.
- :class:`AddonMainTask` can pass keyword arguments to :func:`asyncio.create_task()`.
- :class:`AddonMainTask` changed the moment it starts the main task.
  In some cases it might break existing code. See the docs for a fix.
- Debug messages can be now enabled with
  :ref:`environment variables<Enabling debug messages with environment variables>`.
- Delete the documentation for the recently removed ``SBlock.put()``.

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


Older releases
==============

Only recent changes are listed here.
See the git repository for the full history.

- first stable release was 21.5.15
- first public release is dated February 2020

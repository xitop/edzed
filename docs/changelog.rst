.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).

22.11.2
=======
- Add Python version 3.11 classifier to ``setup.py``.
- Add a parameter controlling the number of decimal places
  in the output of :func:`utils.timestr`.
- Allow :meth:`AddonAsync._create_monitored_task` to pass
  arguments to the underlying :func:`asyncio.create_task`.
- Remove deprecated features in the demo tool:

  - the ``debug`` command was removed, use ``bdebug``
  - the ``demo.run_demo()`` entry point was removed,
    use ``edzed.run(edzed.demo.cli_repl())`` instead
- Give descriptive names to some asyncio tasks.
  This feature was added on a provisional basis.

22.6.13
=======
- Fix a minor issue in :func:`utils.timestr`. In rare cases it could
  return ``... 60.000s`` instead of counting it as 1 minute.
- Add an optional separator to :func:`utils.timestr`.
- Add new function :func:`utils.timestr_approx`.

22.3.1
======

- Drop support for Python 3.7.
- Change to positional-only arguments
  in :meth:`SBlock.init_from_value` and :meth:`SBlock._restore_state`
  in order to make them mutually fully compatible.
- Implement passing of keyword arguments in :class:`InExecutor`.
- Update :class:`Repeat` documentation regarding special event types.
- Small improvements and fixes to type annotations.
- Small code cleanup.

22.2.17
=======

- Switch to postponed evaluation of type hints.

  This should slightly reduce the load time. It also allows to use
  modern type annotation syntax while maintaining compatibility
  with older Python versions.

- Add type hints to function parameters and return values.

  Please note that all type hints are provided *only*
  as a documentation aid.

History
=======

Only recent changes are listed in this document.
See the git repository for the full history.

- first stable release was 21.5.15
- first public release is dated Febrary 2020

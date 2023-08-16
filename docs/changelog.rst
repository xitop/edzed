.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).

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

23.2.14
=======

- Add new syntax in :attr:`FSM.EVENTS`.
- Deprecate the use of iterators to specify multiple events,
  multiple event filters or a group of inputs.
- Small code improvements.

22.12.4
=======

- Implement a *t_period* argument in the :class:`Timer` block.
- Fix a bogus event handler being added to :class:`FSM` instances.

22.11.28
========

- Add :class:`Xor` block.
- Add :ref:`version information<Version information>`.
- When :func:`run` is called with `catch_sigterm=True`,
  uninstall the ``SIGTERM`` handler before returning.
- Update the build system configuration. Use ``pyproject.toml``
  for storing package metadata.

22.11.20
========
- Make use of exception notes introduced in Python 3.11.
  If an additional information about an error is available,
  it is added as an exception note if notes are supported,
  otherwise it is prepended to the error message.
- Add tests requirements to ``setup.py``.


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


Releases older than one year
============================

Only recent changes are listed here.
See the git repository for the full history.

- first stable release was 21.5.15
- first public release is dated February 2020

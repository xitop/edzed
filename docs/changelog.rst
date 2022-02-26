.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).


22.3.1
======

- Drop support for Python 3.7.
- Change to positional-only arguments
  in :meth:`SBlock.init_from_value` and :meth:`SBlock._restore_state`
  in order to make them mutually fully compatible.
- Implement keyword argument passing in :class:`InExecutor`
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


22.2.1
======

- add documentation for the :meth:`Circuit.abort`

There was no code change; not exported to the PyPi.

21.12.8
=======

- add a new entry point :func:`run`; main features:

  - runs supporting coroutines
  - handles ``SIGTERM`` signal delivery

- add short instruction text to examples
- add Python 3.10 to setup specifiers

edzed demo CLI changes:

- rewrite the command history
- add a ``adebug`` command (a = all)
- rename the ``debug`` command to ``bdebug`` (b = block),
  (the old name will be also accepted during a transitory period)
- fix the ``cdebug`` command (c = circuit)

21.10.27
========
- add an :class:`InitAsync` block
- add a :class:`NotIfInitialized` event filter
- accept unabbreviated mode names in :class:`OutputAsync`,
  e.g. ``mode='w'`` can be now written as ``mode='wait'``
  for better code readability
- remove the *desc* parameter and attribute in :class:`Block`;
  they were replaced by *comment* and deprecated in 21.3.16


.. note:: See the git repository for older releases.


21.5.15
=======
First production/stable release

2020.2.11
=========
First public release.

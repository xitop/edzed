.. currentmodule:: edzed

.. role:: strike
  :class: strike

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).


22.2.1
======

- add documentation for the :meth:`Circuit.abort`

There was no code change; not exported to the PyPi.

21.12.8
=======

- add an new entry point :func:`run`; main features:

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

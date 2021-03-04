.. currentmodule:: edzed

=========
Changelog
=========

Version numbers are based on the release date (Y.M.D).

21.3.6
======
- *on_error* must be explicitly set when creating :class:`OutputFunc` or :class:`OutputAsync`
  blocks (incompatible change); the changes are summarized :ref:`here<Error handling>`
- parameters specifying events to be sent (``on_xxx=...``) accept ``None``
- :class:`Event`\'s *efilter* parameter accepts ``None``
- :class:`ControlBlock`\'s event ``error`` was renamed to ``abort``
- simulator debug messages are controlled with :attr:`Circuit.debug`
- block debug messages are logged at the ``DEBUG`` level
- old block logging methods were replaced by :meth:`Block.log_msg` and its wrappers

21.2.24
=======
- :class:`SBlock` :ref:`initialization rules <Initialization>` were modified
- auxiliary event data in :class:`Repeat` were slightly changed
- the default :ref:`output<Output>` value of an FSM was changed

21.2.20
=======
- expiration of saved :ref:`persistent state<Persistent state add-on>` was implemented
- helper function :func:`utils.timeunits.time_period` was added
- an issue with SBlocks initialized by an event was fixed
- :class:`SBlock`\'s arguments *init_timeout* and *stop_timeout* may be now written
  also as strings
- :class:`SBlock` :ref:`initialization order <Initialization>` was modified
- :func:`CBlock._eval` was renamed to :func:`CBlock.calc_output` (incompatible change)
- :func:`FSM._eval` was renamed to :func:`FSM.calc_output` (incompatible change)

21.2.7
======

- fixed messages ``"init_timeout (or stop_timeout) not set, default is 10.000s"``
  being logged even if such timeouts were not applicable
- the format of :ref:`event data sent by FSM blocks<Generating FSM events>`
  was changed (incompatible change)

21.1.30
=======

- :attr:`FSM.sdata` was added
- :class:`Block` now accepts a *debug* argument
- Python version 3.9 was added to classifiers

20.9.10
=======

- :meth:`Circuit.finalize` and :attr:`Circuit.error` were added
- documentation: symbol references are printed without the ``edzed`` package name

20.9.5
======

- :ref:`Event filters`: (incompatible change) the meaning of the returned value
  was altered


.. note:: See the git repository for older releases.


2020.2.11
=========

First public release.

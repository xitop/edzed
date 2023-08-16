=====
Edzed
=====

Welcome to edzed's documentation. The intended audience are Python developers.
Edzed is an asyncio based Python library for building small automated systems, i.e. systems
that control outputs according to input values, system’s internal state, date and time.
It is free and open-source.

The package contains:

- classes for creating combinational and sequential blocks
- methods for building a circuit by connecting the blocks
- a simple event-driven zero-delay digital circuit simulator

Creating edzed applications
===========================

.. toctree::

  software
  intro

Building a circuit
------------------

.. toctree::

  blocks
  events
  cblocks
  sblocks
  filters
  utils
  FSM

Running a simulation
--------------------

.. toctree::

  simulation
  errors
  examination

Creating new block types
========================

For developers of edzed itself or edzed extensions only. Great 
applications can be written using just the built-in blocks.

.. toctree::

  new_cblocks
  new_sblocks


Appendices
==========

.. toctree::
  :maxdepth: 1

  license
  changelog
  notes

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

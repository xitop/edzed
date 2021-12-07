.. currentmodule:: edzed

======
Errors
======

Exceptions
==========

``edzed`` defines these exceptions:

.. exception:: EdzedError

  Base class for exceptions listed below.

.. exception:: EdzedCircuitError

  Raised for any error related to the circuit and its blocks
  where a standard exception like :exc:`ValueError` or :exc:`TypeError`
  is not fully appropriate.

.. exception:: EdzedInvalidState

  This exception is raised for calls that are made in a wrong situation,
  e.g. when trying to start a simulation when it is already running.

.. exception:: EdzedUnknownEvent

  This specific exception is raised when :meth:`SBlock.event` is called
  with an event type that the block does not accept.

Error checking in asyncio
=========================

.. note::

  This section is not specific to ``edzed``.

A non-trivial `asyncio <https://docs.python.org/3/library/asyncio.html>`_
application may need several long-running tasks. Let's call them *services*.
Even if the code was written in agreement with the
*"Errors should never pass silently"* guideline, tasks in asyncio
are *"fire and forget"*. When a task crashes, the rest of the program
continues to run. The application could become unresponsive or ill-behaving.

.. important::

  Make sure an unexpected asyncio task termination
  cannot happen unnoticed.

There are several options (and combinations):

- use wrappers around the services. When the code
  after a ``try / await service() / except`` block is reached,
  you know that the service coroutine has terminated.
  ``edzed`` follows this approach in some of its async sequential blocks
  using a helper :meth:`AddonAsync._create_monitored_task`.
- do not treat any task as a "background task". Organize
  your application in a way that spawning of new tasks and
  their awaiting forms a single code block.
  The :func:`run` function is based on this principle.
- customize the global event loop's error handler,
  see :meth:`loop.set_exception_handler` in asyncio.

And, of course, check the results of terminated tasks.


Detection of erroneous circuit activity
=======================================

The simulator aborts the simulation when it detects erroneous activity
described below. Both cases are similar, one is related to outputs
and one to events.

- Instability
    A circuit instability occurs when the circuit is unable to settle down.
    It happens when a change in an output value triggers output change in
    the directly connected blocks and then in the indirectly connected blocks
    and so on. When the change propagates through the whole circuit several
    times, the circuit is deemed unstable.

- Recursive events
    A sequential block handling an event can send one or more events to other
    blocks. The recipient blocks may respond by generating events too. This is allowed
    unless there is a loop resulting in an event being sent to the block which
    is not ready to handle it, because it did not finish the handling of the
    current event.

    .. important::

      While a block is handling an event, it will raise an exception when it receives an event.

      Because event delivery is synchronous, the only possible cause for this exception
      is the forbidden loop described above.

    Exception from the rule: An FSM may send one event to itself under specific circumstances
    described in :ref:`chained state transitions<Chained state transitions>`.

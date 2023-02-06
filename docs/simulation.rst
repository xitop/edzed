.. currentmodule:: edzed

.. role:: strike
  :class: strike

==================
Circuit simulation
==================

The simulator computes block outputs when any of the inputs changes,
dispatches events and detects errors.

The main object is a :class:`Circuit` instance representing the current circuit.

A new circuit is empty. Circuit blocks and their interconnections
must be created before the circuit simulation.

The simulation itself is executed by an asynchronous coroutine.
The circuit is operational while the coroutine is running.

When the simulation terminates, the final state is reached.
A restart is not possible.

Applications are supposed to build and simulate only one circuit.

.. class:: edzed.simulator.Circuit()

  The circuit class. It registers individual blocks as circuit members
  and can run a simulation when the circuit is completed.

  The Circuit class should not to be instantiated directly;
  always call :func:`get_circuit`.
  The class is not even exported to edzed's API (there is no :strike:`edzed.Circuit`).

.. function:: get_circuit() -> Circuit

  Return the current circuit. Create one if it does not exist.

.. seealso:: :func:`reset_circuit`


Pre-start preparations
======================

A circuit
---------

Of course, a valid circuit (i.e. set of interconnected blocks) is needed.

The completed circuit may be explicitly finalized.

.. method:: Circuit.finalize() -> None

  Finalize the current circuit and disallow any later modifications.

  Process and validate interconnection data (see :meth:`CBlock.connect`):

  - resolve temporary references by name
  - create :class:`Not` blocks for ``"_not_NAME"`` shortcuts

  and initialize related attributes:

  - :attr:`Block.oconnections`
  - :attr:`CBlock.iconnections`
  - :attr:`CBlock.inputs`

  This method is called automatically at the simulation start.
  An explicit call is only necessary if access to the interconnection
  data listed above is required before the simulation start.

  This action cannot be undone.

.. method:: Circuit.is_finalized() -> bool

   Return ``True`` only if :meth:`finalize` has been called
   successfully.


Storage for persistent state
----------------------------

Skip this step if this feature is not required.

.. method:: Circuit.set_persistent_data(persistent_dict: Optional[MutableMapping[str, Any]]) -> None

  Setup the persistent state data storage.

  The argument should be a dictionary-like object backed by
  a disk file or similar persistent storage. It may be also
  ``None`` to leave the feature disabled.

  The Python standard library offers the `shelve module <https://docs.python.org/3/library/shelve.html>`_
  and the corresponding documentation mentions another helpful
  `recipe <https://code.activestate.com/recipes/576642/>`_.

  The persistent data storage must be set before the simulation starts.

  The *persistent_dict* must be ready to use. If it needs to be closed
  after use, the application is responsible for that. The cleanup could
  be performed automatically with `atexit <https://docs.python.org/3/library/atexit.html>`_.


Starting a simulation
=====================

There are two equally valid entry points. Recommended is the higher-level :func:`edzed.run`,
but some applications might prefer the lower-level :meth:`Circuit.run_forever`.

.. function:: run(*coroutines: Coroutine, catch_sigterm: bool = True) -> None
  :async:

  The main entry point. Run the :meth:`Circuit.run_forever` (documented below)
  and all supporting *coroutines* as separate tasks. If any of them exits,
  cancel and await all remaining tasks.

  A supporting coroutine is any coroutine intended to run concurrently with
  the simulator, mainly a coroutine listening for external events or requests,
  monitoring the circuit or controlling the simulator. The :ref:`CLI demo tool`
  is an example of a supporting coroutine.

  Unless *catch_sigterm* is false, a signal handler that cancels the simulation
  upon ``SIGTERM`` delivery will be temporarily installed during the simulation.
  This allows for a graceful exit. Note that the :func:`run` will return normally
  in this case.

  Normally return ``None`` (in contrast to :meth:`Circuit.run_forever`), but raise
  an exception if any of the tasks exits due to an exception other than
  the :exc:`asyncio.CancelledError`. In detail, if the simulation task raises,
  re-raise the exception. If any of the supporting tasks raises, raise :exc:`RuntimeError`.


.. method:: Circuit.run_forever() -> NoReturn
  :async:

  Lower-level entry point. Run the circuit simulation in an infinite loop, i.e. until
  cancelled or until an exception is raised. Note that technically cancellation equals
  to a raised exception too.

  The asyncio task that runs ``run_forever`` is called a *simulation task*.

  When started, the coroutine follows these instructions:

  #. Finalize the circuit with :meth:`finalize`.
     No changes are possible after this point.

  #. Make the circuit ready to accept external events.
     :meth:`is_ready` can be used to check if this state was reached.

  #. Initialize all blocks. Asynchronous block initialization routines
     (if any) are invoked concurrently. After the initialization all
     blocks have a valid output, i.e any value except :const:`UNDEF`.
     If you need to synchronize with this stage, use :meth:`wait_init`.

  #. Run the circuit simulation in an infinite loop.

  #. If an exception (a cancellation or an error) is caught, do a cleanup
     and finally re-raise the exception. This means :meth:`run_forever` never
     exits normally. See also the next section about the simulation stop.

  .. important::

    When :meth:`run_forever` terminates, it cannot be invoked again.


.. method:: Circuit.is_ready() -> bool

  Return ``True`` only if the circuit is ready to accept external events.

  The ``is_ready()`` value changes from ``False`` to ``True`` immediately
  after the simulation start. At this moment the circuit is finalized,
  but the simulation can be still in the initializing phase.

  Because a started circuit is immediately ready,
  no special synchronization is required, but remember that
  ``asyncio.create_task()`` does not start the new task::

    circuit = edzed.get_circuit()
    asyncio.create_task(circuit.run_forever())
    # the task is created, but not started yet (the circuit is NOT ready yet)
    # asyncio.sleep suspends the current task, allowing other tasks to run
    await asyncio.sleep(0)
    # OK, the circuit can now receive events (is ready now)

  The ``is_ready()`` value reverts to ``False`` when the simulation stops.

.. method:: Circuit.wait_init() -> None
  :async:

  Wait until a running circuit is fully initialized.

  The simulation task must be started or at least created.

  :meth:`wait_init` returns when all blocks are initialized and
  the simulation is running. If this state is not reachable
  (e.g. the simulation task has finished already), :meth:`wait_init` raises
  an :exc:`EdzedInvalidState` error.


Stopping the simulation
=======================

A running simulation can be stopped only by cancellation of the simulation task, i.e.
the task that runs :meth:`Circuit.run_forever`.

1. Based on the circuit activity:

  Program the circuit to send a ``'shutdown'`` event to the
  :ref:`simulator control block<Simulator control block>` when a condition is met.

2. From the application code:

  It is assumed that the function wanting to stop the simulation is running inside
  a supporting coroutine started with :func:`run` as this is the intended way
  to run any code controlling the simulation. There are two options:

  - either await :meth:`Circuit.shutdown`

  - or simply terminate the own supporting task, :func:`run` will detect it.
    The simulation is cancelled when any of the supporting tasks terminates.

3. From another process:

  By default, sending a ``SIGTERM`` signal will stop the simulation
  with a proper cleanup, of course only if it is running.

  The corresponding signal handler is installed when :func:`run` is started.

----

.. method:: Circuit.shutdown() -> None
  :async:

  If the simulation task is running, cancel the task and wait until
  it finishes. The wait could take time up to the largest of all *stop_timeout*
  values (plus some small overhead).

  Return normally when the task was cancelled.
  Otherwise the exception that stopped the simulation is raised.

  It is an error to await :meth:`shutdown`:

  - if the simulation task was not started
  - from within the simulation task itself

.. attribute:: Circuit.error
  :type: Optional[BaseException]

  The exception that stopped the simulation or ``None`` if the simulation
  wasn't stopped yet. This is a read-only attribute.


Logging
=======

.. Note::

  `Python logging <https://docs.python.org/3/library/logging.html>`_
  is a complex topic. You may need a more
  sophisticated setup than the basic example shown here.

All logging is done to a logger named after the package,
i.e. ``'edzed'``.

If you don't do anything, Python will setup a handler printing messages with
level (severity) :const:`logging.WARNING` or higher to the standard output.
Messages with :const:`logging.DEBUG` and :const:`logging.INFO` levels won't
be printed be default. To enable them::

  import logging
  logging.basicConfig(level=logging.DEBUG)   # enable level DEBUG and higher (INFO, WARNING, ERROR, ...)


Simulator debug messages
------------------------

.. attribute:: Circuit.debug
  :type: bool
  :value: False

  Boolean flag, allow the simulator to log debugging messages::

    edzed.get_circuit().debug = True # or False

The circuit simulator's debug output is logged with the :const:`logging.DEBUG`
level. Don't forget to enable this level.


Circuit block debug messages
----------------------------

Debugging messages for individual blocks are enabled by setting the
corresponding flag :attr:`Block.debug`.

Block debugging messages are emitted with :const:`logging.DEBUG` level.
Don't forget to enable this level.

For a single block just do::

  blk.debug = True # or False

For multiple blocks there is a tool:

.. method:: Circuit.set_debug(value: bool, *args: str|Block|type[Block|Addon]) -> int

  Set the debug flag to given *value* (``True`` or ``False``) for selected blocks.

  Pass one or more arguments to make a selection:

  - block name
  - Unix-style wildcard with ``'*'``, ``'?'``, ``'[abc]'``
    to match multiple block names.
    For details refer to the `fnmatch module <https://docs.python.org/3/library/fnmatch.html>`_.
  - block object
  - block class (e.g. ``FSM``) to select all blocks of given type
    (the given class and its subclasses)

  Number of distinct blocks processed is returned.

Example: debug all blocks except Inputs::

   circuit = edzed.get_circuit()
   circuit.set_debug(True, '*')    # or: set_debug(True, edzed.Block)
   circuit.set_debug(False, edzed.Input)


Multiple circuits
=================

``edzed`` was deliberately designed to support only one active circuit at a time.

There cannot be multiple circuit simulations in parallel,
but it is possible to remove the current circuit and start over with
building of a new one. We use this feature in unit tests.

.. function:: reset_circuit() -> None

  Clear the circuit and create a new one.

  It is recommended to shut down the simulation first, because
  ``reset_circuit`` aborts a running simulation and in such case
  the simulation tasks should be awaited to ensure a proper cleanup
  as explained :ref:`in the previous section <Stopping the simulation>`.

  .. warning::

    A process restart is preferred over the circuit reset.
    A new process guarantees a clear state.

    A reset relies on the quality of cleanup routines. It cannot
    fully guarantee that the previous circuit has closed all files,
    cancelled all tasks, etc.

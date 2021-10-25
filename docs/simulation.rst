.. currentmodule:: edzed

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
  The class is not even exported to edzed's API (there is no :class:`edzed.Circuit`).

.. function:: get_circuit() -> Circuit

  Return the current circuit. Create one if it does not exist.

.. seealso::

  :func:`reset_circuit`


Pre-start preparations
======================

A circuit
---------

Of course, a valid circuit (i.e. set of interconnected blocks) is needed.
How to design one is beyond he scope of this document.

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

.. method:: Circuit.set_persistent_data(persistent_dict: Optional[Mapping[str, Any]]) -> None

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

.. method:: Circuit.run_forever()
  :async:

  Run the circuit simulation in an infinite loop, i.e. until cancelled or until
  an exception is raised. Note that technically cancellation equals to a raised
  exception too.

  The asyncio task that runs :meth:`run_forever` is called a *simulation task*.

  When started, the coroutine follows these instructions:

  #. Finalize the circuit with :meth:`finalize`.
     No changes are possible after this point.

  #. Make the circuit ready to accept external events.
     :meth:`is_ready` can be used to check if this state was reached.

  #. Initialize all blocks. Asynchronous block initialization routines
     (if any) are invoked in parallel. After the initialization all
     blocks have a valid output, i.e any value except :const:`UNDEF`.
     If you need to synchronize with this stage, use :meth:`wait_init`.

  #. Run the circuit simulation in an infinite loop.

  #. If an exception (a cancellation or an error) is caught, do a cleanup
     and finally re-raise the exception. This means :meth:`run_forever` never
     exits normally. See also the next section about the simulation stop.

  .. important::

    When :meth:`run_forever` terminates, it cannot be invoked again.

  .. seealso:: :ref:`CLI demo tool`

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

A running simulation can be stopped only by cancellation of the simulation task:

1. based on the circuit activity:

  Program the circuit to send a ``'shutdown'`` event to the
  :ref:`simulator control block<Simulator control block>` when a condition is met.

2. from the application code:

  To stop the simulation await :meth:`Circuit.shutdown`.

  .. method:: Circuit.shutdown() -> None
    :async:

    If the simulation task is still running, cancel the task and wait until
    it finishes. The wait could take time up to the largest of all *stop_timeout*
    values (plus some small overhead).

    Return normally when the task was cancelled.
    Otherwise the exception that stopped the simulation is raised.

    It is an error to await :meth:`shutdown`:

    - if the simulator task was not started
    - from within the simulator task itself

  Of course, you could cancel the simulation task directly like in
  this simplified example::

    # start
    circuit = edzed.get_circuit()
    simtask = asyncio.create_task(circuit.run_forever())

    ... some application code runs here ...

    # shutdown
    simtask.cancel()
    try:
        await simtask   # cleanup
    except asyncio.CancelledError:
        pass            # normal exit
    except Exception as err:
        print(f"simulation error {err}")

.. attribute:: Circuit.error

  The exception that stopped the simulation or ``None`` if the simulation
  wasn't stopped. This is a read-only attribute.


Multiple circuits
=================

``edzed`` was deliberately designed to support only one active circuit at a time.

There cannot be multiple circuit simulations in parallel,
but it is possible to remove the current circuit and start over with
building of a new one.

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

.. method:: Circuit.set_debug(value: bool, *args) -> int

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


Circuit monitoring
==================

Finding blocks
--------------

.. method:: Circuit.getblocks(btype: Optional[Block] = None) -> Iterator

  Return an iterator of all blocks or *btype* blocks only.

  Block type checking is implemented with ``isinstance``, so the result
  includes also derived types. For example ``circuit.getblocks(edzed.SBlock)``
  returns all sequential circuit blocks.

  If the result has to be stored, you may want to convert the returned
  iterator to a list or a set.

.. method:: Circuit.findblock(name: str) -> Block

  Get block by name. Raise a :exc:`KeyError` when not found.


Inspecting blocks
-----------------

For features common to all blocks refer to the base class :class:`Block`.


Inspecting SBlocks
^^^^^^^^^^^^^^^^^^

.. method:: SBlock.get_state() -> Any

  Return the :ref:`internal state<Internal state>`.
  Undefined before a successful block initialization.
  (see :meth:`Circuit.wait_init`)

  The format and semantics of returned data depends on the block type.

.. method:: Block.is_initialized() -> bool

  Return ``True`` only if the block has been initialized.

  This method simply checks if the output is not :const:`UNDEF`.

  .. note::

    this method is defined for all blocks, but the test
    is helpful for sequential blocks only

.. attribute:: SBlock.initdef

  Saved value of the *initdef* argument or :const:`UNDEF`,
  if the argument was not given. Only present if the block
  accepts this argument. See: :ref:`Base class arguments`.


Inspecting CBlocks
^^^^^^^^^^^^^^^^^^

.. attribute:: CBlock.iconnections
  :type: set

  A set of all blocks connected to inputs.
  Undefined before the circuit finalization.
  (see :meth:`Circuit.finalize`)

.. attribute:: CBlock.inputs
  :type: dict

  Block's input connections as a dict, where keys
  are input names and values are either single blocks or tuples
  of blocks for input groups. The structure directly corresponds
  to parameters given to :meth:`CBlock.connect`.

  The same data, but with block names instead of block objects,
  can be obtained with :meth:`Block.get_conf`; extract
  the ``'inputs'`` value from the result.

  Not defined before the circuit finalization.
  (see :meth:`Circuit.finalize`)

.. seealso:: :ref:`Input signatures`

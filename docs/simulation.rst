==================
Circuit simulation
==================

The simulator computes block outputs when any of the inputs changes,
dispatches events, and detects errors.

The main object is a ``Circuit`` instance representing the current circuit.

Applications are supposed to build and simulate only one circuit.

.. class:: Circuit()

  The circuit class. It registers individual blocks as circuit members
  and can run a simulation when the circuit is completed.

  The Circuit class should not to be instantiated directly;
  always call :func:`edzed.get_circuit`.
  The class is not even exported to edzed's API (there is no edzed.Circuit).

.. function:: edzed.get_circuit() -> Circuit

  Return the current circuit. Create one if it does not exist.

.. seealso::

  :func:`edzed.reset_circuit`


Pre-start preparations
======================

Preparation steps apart from having a completed circuit.

Storage for persistent state
----------------------------

Skip this step if this feature is not required.

.. method:: Circuit.set_persistent_data(persistent_dict: Optional[Mapping[str, Any]]) -> None

  Setup the persistent state data storage.

  The argument should be a dictionary-like object backed by
  a disk file or similar persistent storage. It can be also
  ``None`` to leave the feature disabled.

  Python standard library offers the `shelve module <https://docs.python.org/3/library/shelve.html>`_
  and the corresponding documentation mentions another helpful
  `recipe <https://code.activestate.com/recipes/576642/>`_.

  Persistent data storage must be set before the simulation starts.

  The *persistent_dict* must be ready to use. If it needs to be closed
  after use in some way, the application is responsible for that. It could
  automatize the cleanup with `atexit <https://docs.python.org/3/library/atexit.html>`_.


Starting a simulation
=====================

.. method:: Circuit.run_forever()

  :async:

  .. important::

    This is the main entry point.

  Run the circuit simulation in an infinite loop, i.e. until cancelled or until
  an exception is raised. Note that technically cancellation equals to a raised
  exception too.

  The asyncio task that runs :meth:`run_forever` is called a *simulation task*.

  When started, the coroutine follows these instructions:

  #. "Freeze" the circuit, i.e. disallow any modifications. No new
     blocks, no changes to interconnections are possible.

  #. Resolve block references by name.

  #. Make the circuit ready to accept external events.
     :meth:`is_ready` can be used to check if this state was reached.

  #. Initialize all blocks. Asynchronous block initialization routines
     (if any) are invoked in parallel. After the initialization all
     blocks have a valid output, i.e any value except :const:`edzed.UNDEF`.
     If you need to synchronize with this stage, use :meth:`wait_init`.

  #. Run the circuit simulation in an infinite loop.

  #. If an exception (a cancellation or an error) is caught, do a cleanup
     and finally re-raise the exception. This means :meth:`run_forever` never
     exits normally. See also the next section about the simulation stop.

  .. important::

    When :meth:`run_forever` terminates, it cannot be invoked again.

  .. seealso:: :ref:`CLI demo tool`

.. method:: Circuit.is_ready() -> bool

  Return ``True`` only if ready to accept external events.

  The simulation can be still in the initializing phase, because
  an error-free circuit is ready immediately after its start.
  No special synchronization is required, but remember that
  ``asyncio.create_task`` does not start the new task::

    circuit = edzed.get_circuit()
    asyncio.create_task(run_forever())
    # the task is created, but not started yet;
    # asyncio.sleep suspends the current task, allowing other tasks to run
    await asyncio.sleep(0)
    # OK, the circuit can now receive events

.. method:: Circuit.wait_init() -> None

  :async:

  Wait until a running circuit is fully initialized.

  The simulation task must be started or at least created.

  :meth:`wait_init()` returns when all blocks are initialized and
  the simulation is running. If this state is not reachable
  (e.g. the simulation task has finished already), :meth:`wait_init()` raises
  an :exc:`edzed.EdzedInvalidState` error.


Stopping the simulation
=======================

A running simulation can be stopped only by cancellation of the simulation task:

- from application code:

  - Cancel the simulation task, but do not exit the application immediately.
    Wait until the task terminates after finishing the cleanup.
    This could take time up to the largest of all *stop_timeout*
    values (plus some small overhead)::

      # This is a simplified example and has a drawback.
      # See the section: "Error checking in asyncio" in "Errors"

      # start
      circuit = edzed.get_circuit()
      simtask = asyncio.create_task(circuit.run_forever())

      ... some application code runs here ...

      # stop
      simtask.cancel()
      try:
          await simtask
      except asyncio.CancelledError:
          pass # OK
      except Exception as err:
          print(f"simulation error {err}")

  - A simpler alternative is to use :meth:`circuit.shutdown`.
    It cancels the simulation task and waits
    until it terminates just like the code above.

- based on the circuit activity:
    Program the circuit to send a ``'shutdown'`` event to a
    :ref:`control block<Simulator control block>`
    when a condition is met.

.. method:: Circuit.shutdown() -> None

  :async:

  If the simulation task is still running, stop the simulation by canceling
  the task and wait until it finishes. Return normally when the task was cancelled.
  Otherwise the exception that stopped the simulation is raised.

  It is an error to await :meth:`shutdown()`:

  - if the simulator task was not started
  - from within the simulator task itself


Logging
=======

All logging is done to a logger named after the package,
i.e. ``'edzed'``.

If you don't do anything, Python will setup a handler printing
messages with level (severity) :const:`logging.WARNING` or higher on the
screen.

.. Note::

  `Python logging <https://docs.python.org/3/library/logging.html>`_
  is a complex topic. You may need a more
  sophisticated setup than the basic examples shown here.


Simulator debug messages
------------------------

The circuit simulator's debug output is logged with the :const:`logging.DEBUG`
level. To allow logging of those messages, enable this level. For example::

  import logging
  logging.basicConfig(level=logging.DEBUG)   # enable level DEBUG and higher (INFO, WARNING, ERROR, ...)


Circuit block debug messages
----------------------------

.. important::

  The blocks emit debugging information with :const:`logging.INFO` severity, because
  the :const:`DEBUG` level is reserved to the simulator itself.

To allow logging of those messages, at least the :const:`INFO` level must be enabled. For example::

  import logging
  logging.basicConfig(level=logging.INFO)   # enable level INFO and higher (WARNING, ERROR, ...)

Block debugging messages must be enabled.

.. attribute:: edzed.Block.debug

  Boolean flag, allow debugging messages.

For a single block just do::

  blk.debug = True # or False

For multiple blocks we have this tool:

.. method:: Circuit.set_debug(value: bool, *args) -> int

  Set the debug flag to given *value* (``True`` or ``False``) for selected blocks.

  Pass one or more arguments to make a selection:

  - block name
  - Unix-style wildcard with ``'*'``, ``'?'``, ``'[abc]'``
    to match multiple block names.
    For details refer to the `fnmatch module <https://docs.python.org/3/library/fnmatch.html>`_.
  - block object
  - block class (e.g. ``edzed.FSM``) to select all blocks of given type
    (the given class and its subclasses)

  Number of blocks processed is returned.

Example: debug all blocks except Inputs::

   circuit = edzed.get_circuit()
   circuit.set_debug(True, '*')    # or: set_debug(True, edzed.Block)
   circuit.set_debug(False, edzed.Input)


Circuit monitoring
==================

Finding blocks
--------------

.. method:: Circuit.getblocks(btype: Optional[edzed.Block] = None)

  Return an iterator of all blocks or *btype* blocks only.

  Block type checking is implemented with ``isinstance``, so the result
  includes also derived types. For instance ``circuit.getblocks(edzed.SBlock)``
  returns all sequential circuit blocks.

  If the result has to be stored, you may want to convert the returned
  iterator to a :class:`list` or a :class:`set`.

.. method:: Circuit.findblock(name: str) -> edzed.Block

  Get block by name. Raise a :exc:`KeyError` when not found.


Inspecting blocks
-----------------

.. note::

  Values related to input and output connections are available only
  after the simulation start.

.. method:: edzed.Block.get_conf() -> dict

  Return a summary of static block information.

  Example output::

    {
      'class': 'Counter',
      'debug': False,
      'desc': '',
      'name': 'cnt1',
      'persistent': False,
      'type': 'sequential'
    }

  All items are self-explaining. Not applicable items are excluded,
  e.g. 'inputs' is shown for combinational blocks only.
  New items may be added in future releases.
  Note that *name* and *desc* can be accessed also as block attributes:

.. important::

  Do not modify any block attributes unless explicitly permitted.

.. attribute:: edzed.Block.circuit

  The :class:`Circuit` object the block belongs to. Usually there is
  only one circuit and this value is of little interest.

.. attribute:: edzed.Block.desc

  String, block's description. May be modified.

.. attribute:: edzed.Block.debug
  :noindex:

  Boolean, see :ref:`Circuit block debug messages`. May be modified.

.. attribute:: edzed.Block.name

  String, the assigned block's name.

.. attribute:: edzed.Block.oconnections

  Set of all blocks where the output is connected to.

.. attribute:: edzed.Block.output

  Block's output value, a read-only property.

  Each block has exactly one output value of any type.

  A special :const:`edzed.UNDEF` value is assigned to newly created blocks.
  It is an error, if :const:`edzed.UNDEF` value appears on block's output after
  the circuit initialization.

.. attribute:: edzed.Block.x_anyname
.. attribute:: edzed.Block.X_ANYNAME

  (with any arbitrary name) Reserved for application data, see: :class:`edzed.Block`

.. data:: edzed.UNDEF

  A constant representing undefined value. All other output values
  are valid, including ``None``.


Inspecting SBlocks
^^^^^^^^^^^^^^^^^^

.. method:: edzed.SBlock.get_state() -> Any

  Return the :ref:`internal state<Internal state>`.
  Only meaningful after a successful initialization.

  The format and semantics of returned data depends on the block type.

  Only sequential blocks have state.
  Combinational blocks do not implement this method.

.. attribute:: edzed.SBlock.initdef

  Saved value of the *initdef* argument or :const:`edzed.UNDEF`,
  if the argument was not given. Only present if the block
  accepts this argument. See: :ref:`Base class arguments`.


Inspecting CBlocks
^^^^^^^^^^^^^^^^^^

.. attribute:: edzed.SBlock.iconnections

  Set of all blocks connected to inputs.

.. attribute:: edzed.SBlock.input

  Block's input connections as a :class:dict:. Dict keys
  are input names, dict values are either single blocks or tuples
  of blocks for input groups. The structure directly corresponds
  to parameters given to :meth:`edzed.CBlock.connect`.

  The same data, but with block names, can be obtained with
  :meth:`Block.get_conf`, extract the ``'inputs'`` value
  from the result.

.. seealso:: :ref:`Input signatures`

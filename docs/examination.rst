.. currentmodule:: edzed


===================
Circuit examination
===================

Finding blocks
==============

.. method:: Circuit.getblocks(btype: Optional[type[Block|Addon]] = None) -> Iterator

  Return an iterator of all blocks or *btype* blocks only.

  Block type checking is implemented with ``isinstance``, so the result
  includes also derived types. For example ``circuit.getblocks(edzed.SBlock)``
  returns all sequential circuit blocks.

  If the result has to be stored, you may want to convert the returned
  iterator to a list or a set.

.. method:: Circuit.findblock(name: str) -> Block

  Get block by name. Raise a :exc:`KeyError` when not found.


Inspecting blocks
=================

This section summarizes attributes and methods providing various block
information. The application code should not modify any attributes
listed here.

.. attribute:: Block.oconnections
  :type: set[CBlock]

  Set of all blocks where the output is connected to. Undefined before
  the circuit finalization - see :meth:`Circuit.finalize`.

For other attributes common to all blocks refer to the base class :class:`Block`.

Inspecting SBlocks
------------------

.. method:: SBlock.get_state() -> Any

  Return the :ref:`internal state<Internal state>`.
  Undefined before a successful block initialization - see
  :meth:`Block.is_initialized` below and :meth:`Circuit.wait_init`

  The format and semantics of returned data depends on the block type.

.. method:: Block.is_initialized() -> bool

  Return ``True`` only if the block has been initialized.

  This method simply checks if the output is not :const:`UNDEF`
  relying on the fact that sequential block's output is determined
  by its internal state.

  .. note::

    This method is defined for all blocks, but the test
    is helpful for sequential blocks only.


Inspecting CBlocks
------------------

.. attribute:: CBlock.iconnections
  :type: set[Block]

  A set of all blocks connected to inputs. Undefined before the circuit
  finalization - see :meth:`Circuit.finalize`.

.. attribute:: CBlock.inputs
  :type: dict[str, Block|Const|tuple[Block|Const, ...]]

  Block's input connections as a dict, where keys
  are input names and values are:

  - either a single :class:`Block` or a :class:`Const`,
  - or tuples of blocks or Consts for input groups.

  The structure directly corresponds
  to parameters given to :meth:`CBlock.connect`.

  The same data, but with block names instead of block objects,
  can be obtained with :meth:`Block.get_conf`; extract
  the ``'inputs'`` value from the result.

  The contents is undefined before the circuit finalization - see
  :meth:`Circuit.finalize`.

.. seealso:: :ref:`Input signatures`


Version information
===================

.. attribute:: __version__
  :type: str

  ``edzed`` version as a string, e.g. "22.11.28"

  .. versionadded:: 22.11.28

.. attribute:: __version_info__
  :type: tuple[int]

  ``edzed`` version as a tuple of three numbers, e.g. ``(22, 11, 28)``.
  The version numbers are derived from the release date: year-2000, month, day.

  .. versionadded:: 22.11.28

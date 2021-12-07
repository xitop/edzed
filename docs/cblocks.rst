.. currentmodule:: edzed

============================
List of combinational blocks
============================

This section lists combinational blocks offered by the ``edzed`` library.

Only block specific parameters are listed in the signatures. In detail:

- the mandatory positional argument *name* is documented in the base class :class:`Block`

- common optional keyword arguments *on_output*, *debug*, *comment* and *x_NAME*
  are shown only as ``**block_kwargs``, they are documented in the base class :class:`Block`

----

.. class:: FuncBlock(name, *, func, unpack: bool = True, **block_kwargs)

  Create a circuit block from a regular Python function *func*.

  .. note::

    This is the only combinational block required, because for every
    possible functionality a corresponding custom function can be written.
    All other combinational blocks exist just for convenience.

  Inputs as defined by :meth:`CBlock.connect`'s positional
  and keyword arguments will be passed to the function as its respective
  positional and keyword arguments. The return value of *func*
  becomes the block's output.

  When *unpack* is ``False``, all positional argument will be passed
  as a single tuple. This allows to directly call many useful
  functions expecting an iterable like :func:`all` and :func:`any`
  (see :func:`And` and :func:`Or` helpers below), :func:`sum`, etc.
  In Python, it represents the difference between ``func(*args)`` when
  unpack is ``True`` (default) and ``func(args)`` when *unpack* is ``False``.

.. class:: Not(name, **block_kwargs)

  Logical NOT (Inverter). This block has exactly one unnamed input.

.. class:: And(name, **block_kwargs)

  Logical AND with arbitrary number of unnamed inputs.
  The output is ``True`` only if all inputs are true.

  ``And`` is a subclass of the :class:`FuncBlock` with fixed ``func=all``.

.. class:: Or(name, **block_kwargs)

  Logical OR with arbitrary number of unnamed inputs.
  The output is ``True`` only if at least one input is true.

  ``Or`` is a subclass of the :class:`FuncBlock`  with fixed ``func=any``.

.. class:: Compare(name, *, low, high, **block_kwargs)

  A comparator with hysteresis.

  This block has one unnamed input where a numeric value is expected.
  Internally there is a second hidden input connected to the output.
  Arguably, such feedback introduces some sort of state, but for practical purposes
  this is a combinational block.

  The output is ``True`` when the input reaches the *high* threshold (``value >= high``)
  and is ``False`` when the input value drops below the *low* threshold (``value < low``).

  When started with an input value in the zone between *low* and *high*, the output is set
  to ``True`` if the input value is closer to *high* than to *low*
  and ``False`` in the opposite case.


.. class:: Override(name, *, null_value=None, **block_kwargs)

  Either pass input to output unchanged or override it with a value.

  A typical use-case is an on/auto/off switch.

  This block has two named inputs. Usage::

    edzed.Override(NAME).connect(input=block1, override=block2)

  - pass mode (output = value from block ``input``):
      when ``override`` is equal to *null_value*.
  - override mode (output = value from block ``override``):
      when ``override`` differs from *null_value*.

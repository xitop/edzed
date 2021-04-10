.. currentmodule:: edzed

============================
List of combinational blocks
============================

This section lists combinational blocks offered by the ``edzed`` library.

Only block specific properties are documented here. For common features
refer to the :ref:`previous chapter <Common features>`.


.. class:: FuncBlock(*args, func, unpack: bool = True, **kwargs)

  Create a circuit block from a regular Python function *func*.

  .. note::

    This is the only combinational block required, because for every
    possible functionality a corresponding custom function can be written.
    All other combinational blocks exist just for convenience.

  Inputs as defined by :meth:`CBlock.connect`'s positional
  and keyword arguments will be passed to the function as its respective
  positional and keyword arguments. The return value of *func*
  is the block's output.

  When *unpack* is ``False``, all positional argument will be passed as
  a single tuple. This allows to directly call many useful
  functions expecting an iterable like :func:`all` (logical AND),
  :func:`any` (logical OR), :func:`sum`, etc.


.. class:: Invert(*args, **kwargs)

  Boolean negation (logical NOT). This block has one unnamed input.


.. class:: Compare(*args, low, high, **kwargs)

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


.. class:: Override(*args, null_value=None, **kwargs)

  Either pass input to output unchanged or override it with a value.

  A typical use-case is an on/auto/off switch.

  This block has two named inputs. Usage::

    edzed.Override(NAME).connect(input=<block1>, override=<block2>)

  - pass mode (output = value from block ``input``):
      when ``override`` is equal to *null_value*.
  - override mode (output = value from block ``override``):
      when ``override`` differs from *null_value*.

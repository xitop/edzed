.. currentmodule:: edzed

Creating combinational blocks
=============================

Feel free to skip this chapter. As noted elsewhere, the :class:`FuncBlock` is an universal
combinational block and there is very little reason to write a new one.

Directions
----------

Directions for creating a new CBlock:

#. subclass from :class:`CBlock`
#. define :meth:`CBlock.calc_output`
#. optional: define :meth:`CBlock.start` and :meth:`CBlock.stop`

----

.. method:: CBlock.calc_output() -> Any
  :abstractmethod:

  Compute and return the output value. This is supposed to be a pure function
  with inputs retrieved from the :attr:`CBlock._in` described below.

.. attribute:: CBlock._in

  An object providing access to input values.

  An input value can be retrieved using the input name as a key ``self._in['myinput']``
  or as an attribute ``self._in.myinput``.

  The result is a single value or a tuple of values, if the input is a group.

.. method:: CBlock.start() -> None

  Pre-simulation hook.

  :meth:`start` is called when the circuit simulation is about to start.

  By definition CBlocks do not require any preparations.
  :meth:`start` typically just checks the :ref:`input signature <Input signatures>`.

  .. important::

    When using :meth:`start`, always call the ``super().start()``.

.. method:: CBlock.stop() -> None

  Post-simulation hook.

  :meth:`stop` is called when the circuit simulation has finished.

  By definition CBlocks do not require cleanup, so :meth:`stop`
  is usually not used. A possible use-case might be processing
  of some gathered statistics data.

  Note that if an error occurs during circuit initialization,
  :meth:`stop` may be called even when :meth:`start` hasn't been called.

  An exception in :meth:`stop` will be logged, but otherwise ignored.

  .. important::

    When using :meth:`stop`, always call the ``super().stop()``


Input signatures
----------------

An input signature is a :class:`dict` with the following structure:

- key: the input name (string)
    The reserved group name ``'_'`` represents the group of unnamed inputs, if any.

- value: ``None`` or integer:

  - ``None``, if the input is a single input
  - the number of inputs in a group, if the input is a group

.. method:: CBlock.input_signature() -> dict

  Return the input signature. The data is available after
  connecting the inputs with :meth:`CBlock.connect`.

  An :exc:`EdzedInvalidState` is raised when called before
  connecting the inputs.

.. method:: CBlock.check_signature(esig: Mapping) -> dict

  Compare the expected signature *esig* with the actual one.

  For a successful result items in the *esig* and
  items from :meth:`CBlock.input_signature` must match.

  If no problems are detected, the input signature data is returned
  for eventual further analysis.

  If any mismatches are found, a :exc:`ValueError` with a description
  of all differences (missing items, etc.) is raised. :meth:`check_signature`
  tries to be really helpful in this respect, e.g. it provides suggestions
  for probably mistyped names.

  In order to support variable input group sizes, the expected
  size can be given also as a range of valid values using
  a sequence of two values ``[min, max]`` where ``max`` may be ``None``
  for no maximum. ``min`` can be also ``None`` for no minimum, but
  zero - the lowest possible input count - has the same effect.

  Examples of *esig* items::

    'name': None    # a single input (not a group)
    'name': 1       # a group with one input (not a single input)
    'ingroup': 4            # exactly 4 inputs
    'ingroup': [2, None]    # 2 or more inputs
    'ingroup': [0, 4]       # 4 or less
    'ingroup': [None, None] # input count doesn't matter


Example (Invert)
----------------

:class:`Invert` source::

  class Invert(edzed.CBlock):
      def calc_output(self):
          return not self._in['_'][0]

      def start(self):
          super().start()
          self.check_signature({'_': 1})

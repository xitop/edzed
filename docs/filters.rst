.. currentmodule:: edzed

=====================
List of event filters
=====================

List of :ref:`event filters<Event filters>`.

.. class:: Edge(rise=False, fall=False, u_rise=None, u_fall=False)

  Event filter for logical values.

  This filter was designed to work with ``on_output`` events.
  It requires items ``'previous'`` and ``'value'`` to be present
  in the event data.

  An ``Edge()`` filter compares logical levels (i.e. boolean values)
  of previous and current values and passes through only explicitly
  allowed combinations. These changes are often called the rising
  or falling edge in logical circuits, hence the name.

  :param bool rise: allow ``False`` -> ``True``
  :param bool fall: allow ``True`` -> ``False``
  :param bool,None u_rise: allow :const:`UNDEF` -> ``True``,
    the default argument ``None`` means that *u_rise* is same as *rise*
  :param bool u_fall: allow :const:`UNDEF` -> ``False``

  Note: :const:`UNDEF` has ``False`` boolean value. That's why *rise* includes
  :const:`UNDEF` -> ``True``. If this is not desired, use ``rise=True, u_rise=False``
  to filter it out.

.. function:: not_from_undef

  Filter out the initial transition from :const:`UNDEF` to the first real value.

  This filter was designed to work with ``on_output`` events.
  It checks the item ``'previous'`` in the event data.


.. class:: Delta(delta)

  Event filter for numeric values. If filters out insignificant value changes.

  It checks the ``'value'`` item of the event data.

  A ``Delta()`` filter compares the last accepted data value
  (not the previous value!) with the current value.
  If the absolute difference is smaller than *delta*, it filters out the event.


.. class:: DataEdit

  This class provides a set of simple data modifiers:

  .. classmethod:: add(key1=value1, key2=value2, ...)

    Add data items, existing values for the same key will be overwritten.

  .. classmethod:: default(key1=value1, key2=value2, ...)

    Add data items, but only if such key is not present already.

  .. classmethod:: copy(srckey, dstkey)

    Copy the value associated with the *srckey* (must exist) to *dstkey*:
    ``data[dstkey] = data[srckey]``

  .. classmethod:: delete(key1, key2, ...)

    Delete all items with given keys. Ignore missing keys.

  .. classmethod:: permit(key1, key2, ...)

    Delete all items *except* the given keys.

  .. classmethod:: modify(key, func)

    Modify an event data value using the *func*.

    The *key* must be present in the event data.
    The corresponding value is replaced by the return value
    of the function *func*: ``data[key] = func(data[key])``.

    As a special case, if the function returns the :const:`DataEdit.REJECT`
    constant, the event will be rejected.

    Examples::

      # convert a numeric value to a readable text
      table = {0: "red", 1: "green", 2: "blue"}
      efilter=edzed.DataEdit.modify('color', table.__getitem__)

      # enforce an upper limit of 100.0
      efilter=edzed.DataEdit.modify('value', lambda v: min(v, 100.0))

----

.. note::

  Pay attention to correct usage. Classes and classmethods *instantiate* a filter,
  so typical usage might look like this::

    edzed.Event(..., efilter=edzed.Edge(rise=True))
    edzed.Event(..., efilter=edzed.DataEdit.copy('value', 't_out'))

  But functions *are* filters, use them without parenthesis::

    edzed.Event(..., efilter=edzed.not_from_undef)

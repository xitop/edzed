.. currentmodule:: edzed

======
Events
======

Events play a key role in sequential blocks' operation.

An event is a message addressed to its destination block. It has
a :ref:`type<Event types>` (usually a string) and can carry arbitrary
:ref:`data<Event data format>` in the form of ``'name':<value>`` pairs.
The purpose of *data* is to describe the event.

:ref:`Internal events` are defined in the circuit. Every :class:`Event`
instance defines a relation to the destination block. This instance is used
by a source block to send events. Each individual send operation carries
its own data corresponding to the current event.

:ref:`External events` come into play when the circuit simulation is running.
As briefly described :ref:`here<Connecting inputs>`, a supporting
coroutine acting as an interface between an external system and the circuit
is responsible for forwarding external events to the circuit.
A relation to a destination block is defined by an :class:`ExtEvent` instance
and the interface sends individual events by calling its :meth:`ExtEvent.send`
method.


Event types
===========

A simple name (string) is the normal way to identify an event type.
External events are limited to named event types.

For example the event setting a new input or output value is usually
named ``'put'`` and the value is passed as the data item ``'value'``.

Special internal events
-----------------------

Occasionally a string is not suitable to fully identify more complex
internal events. For those few cases we use event type objects
instead of names.

.. class:: EventType

  The base class for all special internal events.

There is only one such event type for general use.
It's the conditional event simplifying the block-to-block event delivery:

.. class:: EventCond(etrue: str|EventType|None, efalse: str|EventType|None)

  A conditional event type, roughly equivalent to::

    etype = etrue if value else efalse

  where the ``value`` is taken from the event data item ``'value'``.
  Missing ``value`` is evaluated as ``False``, i.e. ``efalse`` is selected.
  ``None`` as *etrue* or *efalse* means no event in that case.


Event data format
=================

The event data form a Python dict, i.e. they consist of ``'name': <value>`` pairs.
The keys (names) must be strings and valid Python identifiers, because the data
items are passed to functions as keyword arguments. Best practice is to use
only ASCII letters ``a-z``, ``A-Z``, digits ``0-9`` and the ``_`` (underscore).


External events
===============

The following class is intended for use in an interface coroutine
running as a supporting task.

.. class:: ExtEvent(dest: str|SBlock, etype: str = 'put', source: str = '_ext_')

  Create an object with external event settings, i.e. with
  the :ref:`type<Event types>` *etype*, the destination block *dest* and
  the default *source* name.

  The *dest* argument may be a sequential block object or its name.

  .. method:: send(value=edzed.UNDEF, **data) -> Any

    Ensure a source name is present in the data and send this event.
    Return the event handler's exit value.

    If a *value* is given, it will be added to the event data as ``data['value']``.
    This is just a simple convenience feature; these two lines are fully equivalent::

      ext_event.send(VALUE, ...)
      ext_event.send(..., value=VALUE, ...)


    A ``'source':'NAME'`` key:value item must be present
    in the event data. If it is not explicitly given as::
    
      ext_event.send(..., source='NAME', ...)

    then a ``'source':'DEFAULT-SOURCE-NAME'`` data item will be inserted.

    .. important::
      A special prefix ``'_ext_'`` will be prepended to the source
      name unless already present. It is a mark of an external origin. Note that
      an internal event (i.e. sent from a circuit block) cannot have such prefix
      in its ``'source'`` data item, because block names starting with an
      underscore are reserved.

    An :exc:`EdzedInvalidState` error will be raised if the circuit is not ready
    to process events. Normally this means it is shutting down. Other reasons
    are ruled out if ``send()`` is called from a supporting task as recommended.
    Supporting tasks are not started when the circuit is not yet ready
    and get cancelled, when the circuit shuts down completely.

    This function invokes :meth:`SBlock.event()` Please read the warning
    in its documentation.

  .. attribute:: dest
    :type: SBlock

    The saved destination block object, even if it was specified by name. Read-only.

    A recipe how to deny access to blocks not acting as inputs::

      class ExtEventAuth(edzed.ExtEvent):
          """
          Allow external access only to blocks
          defined with `x_input=True` keyword argument.
          """
          def __init__(self, *args, **kwargs):
              super().__init__(*args, **kwargs)
              if not getattr(self.dest, 'x_input', False):
                  raise ValueError(
                      f"Block {self.dest.name} is not accepting external events")

  .. attribute:: etype
    :type: str

    The saved event type string. Read-only.

.. versionadded:: 23.8.25


Internal events
===============

Configuring events to be sent
-----------------------------

Every block (even a combinational one) can generate events on its output change.
These are the most common events and are defined with an *on_output* argument.
:ref:`Output events` are covered in the next section.

Several sequential blocks included in the ``edzed`` libraty can generate events
also on certain internal state changes.

By convention all parameters instructing a block to send events in certain
situations have names starting with an ``"on_"`` prefix and they accept:

- ``None`` meaning no event; an empty list or tuple has the same effect, or
-  a single :class:`Event` object, or
-  multiple (zero or more) :class:`Event` objects given as a sequence (tuple, list, ...)
   of single events.

Hence, the type annotation is: ``None | Event | Sequence[Event]``.

.. versionchanged:: 23.2.14

  Using an iterator to specify multiple events is deprecated.
  Use a tuple or a list instead.

The :class:`Event` instance sets the destination and the event type. New data
is added each time the event is sent.

For example, this code instructs the ``block1`` to send a ``put`` event
to ``block2`` each time when its output value changes. This creates a logical
link from ``block1`` to ``block2``::

  edzed.Input('block1', initdef=0, on_output=edzed.Event(block2, 'put'))

When the output changes say from ``23`` to ``27``, the source ``block1`` executes
following code in order to deliver the event::

  # fixed destination (block2) and type ('put')
  block2.event(
    'put',
    # current data for this event
    previous=23, value=27, source='block1', trigger='output')

When the output later changes again, the event will be delivered with different
values for ``'previous'`` and ``'value'`` items.


Output events
-------------

There are two ways of specifying output events. The most common option *on_output*
is supported by all blocks. The specialized *on_every_output* is available to
sequential blocks only.

- events defined with the *on_output* parameter:

  These events are sent when the output value of the source block changes.

- events defined with the *on_every_output* parameter:

  Similar to *on_output*, but events are triggered each time the output is set,
  even if the new value is the same as the previous one.
  This is useful if the destination block should not miss a value (e.g. a measurement)
  just because it happens to be the same as the previous one.

In both cases the generated events are sent with these data items:

- ``'previous'``: previous value (:const:`UNDEF` on first change after initialization)
- ``'value'``: current output value
- ``'source'``: sender's block name (string, added automatically)
- ``'trigger'``: ``'output'`` (corresponds with ``'on_output'``)

Event objects
-------------

.. class:: Event(dest: str|SBlock, etype: str|EventType = 'put', efilter=None, repeat=None, count=None)

  Create an object with event settings. Mandatory settings are
  the :ref:`type<Event types>` *etype* and the destination block *dest*.

  A source block uses this ``Event`` object to send a new event each time some trigger
  condition is satisfied. Every such event is then a combination of fixed settings
  from the ``Event`` object and variable data specific to the particular event.

  The *dest* argument may be a sequential block object or its name. The named block
  does not have to exist yet. Names will be looked up when the circuit starts.

  :ref:`Event filters` are functions (*callables* to be exact) documented below.
  The *efilter* argument may be:

  - ``None`` meaning no filters (an empty list or tuple has the same effect), or
  - a single function, or
  - a tuple, list or other sequence of functions.

  If a repeat interval is given with the *repeat* parameter, a :class:`Repeat` block
  is automatically created to repeat the event. This::

      edzed.Event(dest, etype, repeat=INTERVAL, count=COUNT)  # count is optional

  is equivalent to::

      edzed.Event(
        edzed.Repeat(
          None,
          comment="<auto-generated comment>",
          dest, etype, interval=INTERVAL, count=COUNT),
        etype)

  The *count* argument is valid only with the *repeat* argument.

  .. method:: abort() -> Event
    :classmethod:

    A shortcut for ``edzed.Event('_ctrl', 'abort')``.

    Specify an event addressed to circuit's :class:`ControlBlock`
    with an instruction to abort the simulation due to an error.

  .. method:: shutdown() -> Event
    :classmethod:

    A shortcut for ``edzed.Event('_ctrl', 'shutdown')``

    Specify an event addressed to circuit's :class:`ControlBlock`
    with an instruction to shut down the simulation.

  .. attribute:: dest
    :type: SBlock

    The saved destination block object, even if it was specified by name. Read-only.

    .. warning::
      Names get resolved to objects during the circuit finalization.
      An access before the finalization raises the :exc:`EdzedInvalidState` error
      if the destination block was given by name.

  .. attribute:: etype
    :type: str|EventType

    The saved event type. Read-only.
 
Event filters
-------------

Event filters serve two purposes. As the name suggests, they can filter out
an event, i.e. cancel its delivery. The second use is to modify the filter data.

An event filter function is called with the event data as a single dictionary
as its sole argument.

- If it returns a :class:`dict` (precisely a :class:`MutableMapping`), the event is
  accepted and the returned dict becomes the new event data.
  The :ref:`data format<Event data format>` should not be violated.
  A non-string key will cause a :exc:`TypeError`.

- If the function returns anything else than a dict instance,
  the event will be accepted or rejected depending on the boolean value
  of the returned value (true = accept, false (e.g. ``False`` or ``None``) = reject).

Event filters may modify the event data in-place.

Multiple filters are called in their definition order like a *pipeline*.

Event filters are usually very simple, often an "one-liner" or a ``lambda``
is all it takes.

.. seealso:: :ref:`List of event filters`

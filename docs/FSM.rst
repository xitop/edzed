.. currentmodule:: edzed

=====================
Finite-State Machines
=====================

A Finite-State Machine (**FSM**) is a special kind of sequential blocks.
Due to its versatility and also its complexity it deserves a separate chapter.

*A basic understanding of the Finite-State Machine concept is helpful.*

With some simplification, a Finite-State Machine is defined by:

- set of possible states, one of them being the initial state
- set of events it can process; events trigger transitions from one state to another
- a control table called a transition table

An FSM block implements several additional features:

- persistent state
- timed events
- event conditions
- entry and exit actions
- generated events

.. note::

  Every sequential block (SBlock) has its internal state and can process events.
  An FSM also defines states and events. Their relationship is:

  - FSM state is a part of SBlock's internal state.
  - all events are delivered using the :meth:`SBlock.event` method as in
    any other sequential block. Usually all events are processed by the FSM code,
    i.e. they are FSM events, but please note that it is possible to add non-FSM
    events to be processed by the underlying SBlock and bypassing the FSM.
    See :meth:`SBlock._event_ETYPE`.

  In this chapter by 'state' and 'event' we usually mean an FSM state
  and an FSM event respectively.

FSM example
===========

Let's start with a simple example::

  class Turnstile(edzed.FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  t1 = Turnstile('t1', comment="example turnstile #1")
  t2 = Turnstile('t2', comment="example turnstile #2")

We have defined a new FSM and created two circuit blocks.

The :class:`Turnstile` has two states: 'locked' and 'unlocked',
the first one is the initial state by default.

It accepts two events: 'coin' and 'push'.

When the event 'coin' occurs in the 'locked' state, the FSM
makes a transition to the 'unlocked' state.

When the event 'push' occurs in the 'unlocked' state, the FSM
makes a transition to the 'locked' state.

There are no other state transitions defined. For example, when the
turnstile is 'unlocked', the 'coin' event will have no effect.
We may say that an event is not accepted, not allowed, or even rejected
in certain state, but it's a normal FSM operation - not an error.


Creating FSMs types
===================

A new FSM is created by subclassing the base class.
Instances of the subclasses will be circuit blocks.

.. class:: FSM

  Base class for creating FSMs.

  Subclasses are supposed to define class attributes:

  - :obj:`FSM.STATES`
  - :obj:`FSM.EVENTS`
  - :obj:`FSM.TIMERS`

  All three contain an empty list/table by default.

  A subclass may also define:

  - :ref:`event conditions<Event conditions>`
  - :ref:`state entry and exit actions<State entry and exit actions>`


States, events, transitions
---------------------------

An FSM has a current state. A transition from the current state
to next state is triggered by a received event. The next state
is determined by a transition table:

    (state, event) --> next state

All states and regular events are represented by a name (string).
Avoid any special characters in names, because function names are
derived from them. States and events form two separate namespaces,
but using the same name for both is discouraged.

The :meth:`FSM.event` method returns ``True`` for accepted FSM events
and ``False`` for rejected FSM events.

.. note::

  We use the term "list of items" in general sense that includes Python's
  :class:`list`, :class:`tuple` and similar.

.. attribute:: FSM.STATES
  :type: sequence (list, tuple) of strings

  Class attribute.

  A list of valid states. Timed states from :obj:`FSM.TIMERS` are appended
  automatically, but may be listed here, because duplicates
  do not matter. The very first item in the resulting list is the
  default initial state.

.. attribute:: FSM.EVENTS
  :type: sequence (list, tuple) of triples

  Class attribute.

  Events and rules, i.e. the transition table.
  The set of all valid events is comprised from the first table column.

  Data format:

    table with 3 columns, i.e. a list of rows ``[event, states, next_state]``

  where the *states* value defines in which states will the *event*
  trigger a transition to the *next_state*.

  *states* must be one of:

  - list of states (strings)

    If there is only one state in the list,
    it may be written directly as a string. These two table
    rows are equivalent::

      ('push', ['unlocked'], 'locked'),     # standard notation (a list with 1 item)
      ('push', 'unlocked', 'locked'),       # simplified notation

  - ``None`` as a special value for all states

    An entry with explicitly listed states has a precedence over
    an entry with ``None``.

  ``None`` as *next_state* makes a transition explicitly disallowed.

  Examples::

    ["ev1", None, "state2"],    # default rule for "ev1" and all states except
                                # more specific rules for state2 and state3 below
    ["ev1", ["state2"], "state3"],  # rule for state2 -> state3
    ["ev1", ["state3"], None],      # ev1 is ignored in state3

  The transition table must be deterministic. Only one next state may be
  defined for any combination of event and state.

.. attribute:: FSM.TIMERS
  :type: dict

  Class attribute.

  Specification of optional timers attached to selected states.
  A state with a timer is called "timed state".
  Apart from the timer are timed states not different from other states
  and they automatically belong to the list of states :obj:`FSM.STATES`.

  Data format:

    dict of ``{timed_state: (default_duration, timed_event)}``

  A timer is set when the *timed_state* is entered. When the timer
  expires, the *timed_event* is generated. If the state is exited
  before the timer expiration, the timer is cancelled. This means
  that a transition from a timed state to the same state restarts
  the timer. If this is undesirable, disallow the transition.

  If the *timed_event* gets rejected, the block will remain
  in *timed_state* without a timer.

  See also: :ref:`Goto special event`.

  If the duration is 0.0, the *timed_event* is generated immediately.

  If the duration is :const:`INF_TIME` (infinite time to expiration),
  the timer won't be set at all.

  Instances can modify the default duration with ``t_STATE=value``
  keyword argument.

  The duration can be dynamically overridden with a ``'duration': value``
  data item passed with the event responsible for entering
  the timed state. This value has the highest precedence.

  The timer duration may be given as:
    - number of seconds (int, float), negative values are replaced with 0.0
    - a :ref:`string with time units<Time intervals with units>`
    - :const:`INF_TIME`
    - ``None``, i.e. the duration is not set here
      and must be obtained from other source

.. data:: INF_TIME

  Equals to ``float('+Inf')`` constant. This is a timer duration that
  disables a timer so it never expires.


Goto special event
^^^^^^^^^^^^^^^^^^

.. class:: Goto(state)

  A ``Goto('state')`` event causes a direct and unconditional transition
  to the given state. The transition table lookup is bypassed.

  Its primary purpose is to simplify the definition of timed states.

  A timed state ends with a timed event. In most cases all we need
  is a transition to another state. For example::

    # without Goto
    class Hertz1(edzed.FSM):
        EVENTS = [
            ['goto_on',  None, 'on'],
            ['goto_off', None, 'off']
        ]
        TIMERS = {
          'on': (0.5, 'goto_off'),
          'off': (0.5, 'goto_on'),
        }

  With ``Goto`` we can write the same FSM as::

    class Hertz1(edzed.FSM):
        TIMERS = {
            'on': (0.5, edzed.Goto('off'),
            'off': (0.5, edzed.Goto('on'),
        }

.. warning::

  We have shown that using the ``Goto`` special event is similar to adding an
  entry to the transition table. This makes it a part of the FSM design
  that other blocks should not interfere with. That's why:

  - ``Goto`` events should be generated internally,
    i.e. by FSM's own timers or entry actions.
  - Events sent to other blocks should be regular events.


Event conditions
----------------

Event conditions are optional functions which decide if a regular
event (i.e. not :ref:`Goto<Goto special event>`) will be accepted or rejected (ignored).

For every ``EVENT`` the corresponding function is named

- ``cond_EVENT``
    condition for accepting event ``EVENT``

and may exist as:

- a method defined in the class, and/or
- an external callback defined in the instance with ``cond_EVENT=function`` keyword argument

``cond_EVENT`` is called without arguments. :ref:`Access to event data` is
provided through a context variable.

``cond_EVENT`` should return a value. If it evaluates to boolean true,
the ``EVENT`` will be processed. If it evaluates to boolean false,
the ``EVENT`` will be ignored. When both a method and a function
are defined, both must return true value to accept the event.

Another use of the ``cond_EVENT`` method (but not the external function)
is that it may save the event data for later use.

Example::

    # using the Turnstile class from prior example

    enable = edzed.Input('inp_enable', comment="enable the turnstile", schema=bool, initdef=True)
    Turnstile('t', cond_coin=lambda: enable.output)


State entry and exit actions
----------------------------

Optional functions acting as entry and exit actions have the names:

- ``enter_STATE``
    entry action for state ``STATE``

- ``exit_STATE``
    exit action for state ``STATE``

They are called when a ``STATE`` is entered and exited respectively.

The actions may be defined as:

- methods in the class, and/or
- external callbacks defined in the instance with a keyword argument

The functions are called without arguments. :ref:`Access to event data` is
provided through a context variable.
Note that event data for ``enter_STATE`` and ``exit_STATE`` are not the same,
but belonging to two distinct events.


Access to event data
--------------------

.. data:: fsm_event_data

  Read-only access to the current event data dict is provided through the
  :data:`fsm_event_data`
  `context variable <https://docs.python.org/3/library/contextvars.html>`_.

  You don't have to be familiar with the context variables, just use this line::

    data = edzed.fsm_event_data.get()


Chained state transitions
-------------------------

``enter_STATE`` may call ``self.event()`` to schedule an immediate
transition to the next state. Only one such call is permitted,
in order to prevent any ambiguities. ``cond_EVENT`` and ``exit_STATE``
must not call ``self.event()``, neither directly nor indirectly.

When an FSM was in S1 state, just entered S2 and the ``enter_S2``
function calls ``self.event()`` to request a transition to S3, the
intermediate S2 state calls its ``exit_S2`` function (if any) immediately
after returning from ``enter_S2`` and then S3 state will be entered.

Notice that:

- the output won't be affected by S2
- no S2 related events (``on_enter_S2``, ``on_exit_S2`` and ``on_output`` for S2) will be sent

The reason why S2 will refrain from manifesting itself is that
in an idealized circuit, S2 was valid for zero time. From an
external view the S1 -> S2 -> S3 transition that took place
looks like a straightforward S1 -> S3 transition.

For example the code shown in the :ref:`next section<Additional internal state data>`
makes use of the chained state transition feature.
Look for the transition ``prepare_afterrun -> afterrun``.


Additional internal state data
------------------------------

.. attribute:: FSM.sdata
  :type: dict

  In some cases the internal state consists of more values than just the current
  FSM state and the timer state. This additional data should be stored here
  as key=value pairs.

  .. important:: All keys must be strings.

  Because the :attr:`FSM.sdata` dict is by definition a part of the internal state,
  it is automatically saved and restored when the persistent state is turned on.

In the following example, the output is ``True`` between the ``start`` and ``stop``
events and also during the following after-run period. The after-run duration is
calculated as a percentage of the regular run duration. The :attr:`FSM.sdata` is used
to hold the timestamp necessary for the calculation::

  class AfterRun(edzed.FSM):
      STATES = ['off', 'on', 'prepare_afterrun', 'afterrun']
      EVENTS = [
          ['start', ['off'], 'on'],
          ['stop', ['on'], 'prepare_afterrun'],
      ]
      TIMERS = {
          'afterrun': (None, edzed.Goto('off'))
      }

      def enter_on(self):
          self.sdata['started'] = time.time()

      def enter_prepare_afterrun(self):
          duration = (time.time() - self.sdata.pop('started')) * (self.x_percentage / 100.0)
          self.event(edzed.Goto('afterrun'), duration=duration)

      def calc_output(self):
          return self.state != 'off'


  AfterRun('afterrun', x_percentage=50)


Output
======

The output value is calculated in the :meth:`FSM.calc_output` method which is called
during a state transition after ``enter_STATE`` action and before ``on_enter_STATE``
and ``on_output`` events:

.. method:: FSM.calc_output

  Return the block's output value computed from the internal state data.

  Return :const:`UNDEF` to leave the output unchanged.

  The default implementation returns the current FSM state (string).

  Many FSMs communicate with events only. If you need an output,
  redefine this method.


Example (Timer)
===============

:class:`Timer` source::

  class Timer(edzed.FSM):
      STATES = ('off', 'on')
      TIMERS = {
          'on': (fsm.INF_TIME, 'stop'),
          'off': (fsm.INF_TIME, 'start'),
          }
      EVENTS = (
          ('start', None, 'on'),
          ('stop', None, 'off'),
          ('toggle', 'on', 'off'),
          ('toggle', 'off', 'on'),
          )

      def __init__(self, *args, restartable=True, **kwargs):
          super().__init__(*args, **kwargs)
          self._restartable = bool(restartable)

      def cond_start(self):
          return self._restartable or self._state != 'on'

      def cond_stop(self):
          return self._restartable or self._state != 'off'

      def calc_output(self):
          return self._state == 'on'


Creating FSMs blocks
====================

FSM parameters
--------------

Summary of parameters accepted as keyword arguments by classes derived
from the :class:`FSM` class.

``'STATE'`` and ``'EVENT'`` are placeholders to be substituted by real
state and event names.

- ``t_STATE=duration``
    see: :obj:`FSM.TIMERS`

- ``cond_EVENT=function``
    see: :ref:`Event conditions`

- ``enter_STATE=function``
- ``exit_STATE=function``
    see: :ref:`State entry and exit actions`

- ``on_enter_STATE=events``
- ``on_exit_STATE=events``
- ``on_notrans=events``
    see: :ref:`Generating FSM events`

- ``persistent=boolean``
    make the internal state persistent

- ``initdef=STATE``
    initial state, default is the first state listed in :obj:`FSM.STATES`.


Generating FSM events
---------------------

FSM instances may define :ref:`events<Events>` to be sent to other blocks.

The corresponding keyword arguments are:

- ``on_enter_STATE`` and ``on_exit_STATE`` .
    These events are generated when a state ``STATE`` is entered and exited
    respectively. Exception: all events are suppressed for intermediate states,
    see :ref:`chained state transitions`.

    Events are sent with these data items:

    - ``'source'``: sender's block name
    - ``'trigger'``: either ``'enter'`` or ``'exit'``
    - ``'state'``: the FSM state just entered or exited
    - ``'sdata'``: a shallow copy of :attr:`FSM.sdata` with private data items removed
      (private data are items with keys starting with an underscore).
    - ``'value'``: the output value

- ``on_notrans``

    This event is sent when an event is not accepted. i.e. there
    is no transition defined for it in the current state.

    Events are sent with these data items:

    - ``'source'``: sender's block name
    - ``'trigger'``: always ``'notrans'``
    - ``'state'``: the current FSM state
    - ``'event'``: the not accepted event

Other event data items may be added in the future.


Initialization rules
====================

During initialization, i.e. when the very first state is entered:

- ``exit_STATE`` is not executed, because there is no ``STATE`` to exit.
- ``cond_EVENT`` is not executed, because the first state needs
  to be entered unconditionally.
- ``enter_STATE`` and ``on_enter_STATE`` are executed except when
  initializing from saved (persistent) state. Initialization
  from persistent state is considered a restoration of a state that was
  already entered in the past. This behavior is in-line with the main
  purpose of state persistence which is to allow for seamless continuation
  after a restart.

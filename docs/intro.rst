============
Introduction
============

``edzed`` is a Python asyncio based library for building automated systems,
i.e. systems that control outputs according to input values,
system’s internal state, date and time.

The automated system in ``edzed`` is called a circuit, because it is built by
interconnecting provided basic blocks, almost like an electronic circuit.
``edzed`` was indeed developed on principles of a circuit simulation for an
idealized digital circuit.


.. important::
  Designing control circuits for ``edzed`` requires some experience with
  logical circuits. Unfortunately this topic is beyond he scope of this document.

The ``edzed`` code in an application is naturally divided into two main parts:

- assemble a circuit from individual blocks
- run the simulation task and optional supporting tasks

Being a library means there is no function out of the box.
In order to create an usable system, the developer needs to:

- create a circuit
- connect edzed inputs with data sources
- connect edzed outputs with controlled devices


Connecting with the outside world
=================================

Connecting outputs
------------------

The developer should provide a custom function (may be asynchronous) for each type of
controlled output device. The circuit's output block for that device will invoke the
function each time it receives a new value.

For simple testing and learning often a simple ``print`` statement will do. This is
what we use in our examples.

Connecting inputs
-----------------

In general, there are two data flow models called *pull* and *push*.

1. *Pull* - The input block actively polls for the input data. For example it reads
   data from a sensor in some intervals. The developer should provide a custom function
   (may be asynchronous) for each type of input device connected this way.

2. *Push* - The input block reacts to incoming events or requests. This is the most common case
   and it requires a supporting asynchronous task acting as an interface between
   one or more external systems and the circuit. The application developer should
   provide an async coroutine that will be run together with the circuit simulation.
   This supporting task usually consists of a loop that:

  - listens for an incoming event or request, for instance on a network socket
    or on the command line like the included :ref:`CLI demo tool`, etc.,
  - performs checks and preprocessing as required by the particular application
  - if the event is accepted, forwards it to the circuit
    and returns the reply (a result value or an error message)

  The supporting task may also handle monitoring or supervising of the circuit, like retrieving
  the internal state, turning debugging on/off, updating time schedules, shutting down, etc.
  Multiple supporting tasks may exist, if necessary.

  
Examples
--------

**"Hello, world!"**

The examples below show I/O techniques mentioned in the previous section.
In order to produce simple working examples, we have to mock input data
sources and use print statements instead of real outputs.

The source codes can be found in the
`examples directory <https://github.com/xitop/edzed/tree/master/examples>`_
on github. Of course, you can also cut and paste the code from this web page
to a file.

Run with: ``python3 examplefile.py``, press the ``ctrl-C`` key to terminate.

Don't worry if you don't understand all the details, ``edzed`` comes
with a comprehensive documentation.

Example 1: no inputs
++++++++++++++++++++

No block in this example reads external input data. The activity is entirely based on date
and time. No special input handling code is required for this case, of course.

Simply print "tick/tock" (the clock sound) in 1 second pace::

  import asyncio
  import edzed

  edzed.Timer(
      'clk', comment="clock generator",
      t_period=1.0, on_output=edzed.Event('out'))

  def output_print(value):
      if value:
          print('..tock')
      else:
          print('tick..', end='', flush=True)

  edzed.OutputFunc(
      'out', func=output_print, on_error=None)

  if __name__ == '__main__':
      print('Press ctrl-C to stop\n')
      asyncio.run(edzed.run())


Example 2: polling a sensor
+++++++++++++++++++++++++++

In this thermostat example a readout from a sensor is made in regular intervals,
i.e. the data is pulled into the circuit::

  import asyncio
  import random
  import edzed

  def input_temperature():
      """Fake room thermometer (Celsius scale)."""
      t = random.uniform(20.0, 28.0)
      print(f"T={t:.1f}")
      return t

  def output_heater(hot):
      if hot:
          print(" T >= 24 °C, heater off")
      else:
          print(" T < 22 °C, heater on")

  edzed.ValuePoll(
      'thermometer',
      func=input_temperature, interval=1.5)

  edzed.Compare(
      'thermostat',
      low=22.0, high=24.0, on_output=edzed.Event('heater')
      ).connect('thermometer')

  edzed.OutputFunc(
      'heater',
      func=output_heater, on_error=None)

  if __name__ == '__main__':
      print('Press ctrl-C to stop\n')
      asyncio.run(edzed.run())

Example 3: with a supporting task
+++++++++++++++++++++++++++++++++

In the final example, an external system pushes its data to the circuit.
The circuit itself is not shown. A basic skeleton of a supporting task
could look like this::

  # warning: pseudo-code!
  async def my_interface():
      conn = control_connection   # e.g. a network socket
      circuit = edzed.get_circuit()
      while True:
          inp = await conn.read_request()
          try:
              cmd = parse(inp)
              if is_event(cmd):
                  # pass an external event to the circuit
                  event = edzed.ExtEvent(cmd.block, cmd.event)
                  result = event.send('control_connection', **cmd.data)
              elif is_query(cmd):
                  # query a circuit block (debugging, monitoring, ...)
                  blk = circuit.findblock(cmd.block)
                  # get the requested information using functions like
                  # blk.get_state(), blk.get_conf(), blk.output, etc.
                  result = ...
              elif is_control_command(cmd)
                  # control the circuit using functions like
                  # circuit.set_debug(), circuit.shutdown(), etc.
                  result = ...
              else:
                  raise ValueError("Incorrect input")
          except Exception as exc:
              await conn.reply_with_error(exc)
          else:
              await conn.reply_with_result(result)

The application consists of the simulator and the supporting task.
Both must be started with::

  if __name__ == '__main__':
      asyncio.run(edzed.run(my_interface()))

.. module:: edzed.demo

CLI demo tool
=============

A simple interactive command line demo tool is provided in the package.
Input values can be entered from keyboard, state changes are printed to the screen.
It allows you to test ``edzed`` to some extent without writing own applications.

To use this tool, import ``edzed.demo`` and run the simulation with :func:`cli_repl`.

.. warning::

  Use the demo tool only for testing at the command line and nothing else.
  The code contains ``eval <user-input>``. Such code is dangerous
  if the input is coming from a malicious user.

.. function:: cli_repl(setup_logging: bool = True)
  :async:

  Command line utility for interacting with a circuit. Use it as a supporting
  coroutine in :func:`edzed.run`, see the examples below.
  (REPL stands for: read-evaluate-print loop)

  Unless *setup_logging* is false, logging is configured with
  ``logging.basicConfig(level=logging.DEBUG)``
  to display messages of all levels including ``DEBUG``.

----

Let's test :ref:`this turnstile <FSM Example>`. It allows one person
to pass by pushing it, but only if it was unlocked with a coin.
It does not allow to pass twice nor to pay twice::

  import asyncio
  import edzed
  from edzed.demo import cli_repl

  class Turnstile(edzed.FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  Turnstile('ts', comment="example turnstile")

  if __name__ == '__main__':
      print("""\
  To send a 'push' or 'coin' event to the turnstile 'ts',
  use the e[vent] command:
      e ts push
      e ts coin
  """)
      asyncio.run(edzed.run(cli_repl()))

Below is a sample output. We will send some events, observe the responses:

- :meth:`event` responds with ``True`` to accepted events and ``False`` to rejected events
- if an event is accepted, the state changes between ``'locked'`` and ``'unlocked'``;
  ignore the ``None`` and ``{}`` in the state for now.
- the block's output is always ``False``, you may ignore it too

::

  $ python3 turnstile.py

  --- edzed 1> help
  Control commands:
      h[elp] or ?                 -- show this help
      exit
      eval <python_expression>
  Circuit evaluation commands:
    Debug messages:
      a[debug] 1|0                -- all blocks' debug messages on|off
      b[debug] <blockname> 1|0    -- block's debug messages on|off
      c[debug] 1|0                -- circuit simulator's debug messages on|off
    Events:
      e[vent] <blockname> <type> [{'name':value, ...}]
                                  -- send event
      p[ut] <blockname> <value>   -- send 'put' event
    Info:
      l[ist]                      -- list all blocks
      i[nfo] <blockname>          -- print block's properties
      s[how] <blockname>          -- print current state and output
  Command history:
      !?                          -- print history
      !N                          -- repeat command N (integer)
      !-N                         -- repeat command current minus N
      !!                          -- repeat last command (same as !-1)

  --- edzed 2> e ts push
  event() returned: False
  output: False
  state: ('locked', None, {})
  --- edzed 3> e ts coin
  event() returned: True
  output: False
  state: ('unlocked', None, {})
  --- edzed 4> e ts push
  event() returned: True
  output: False
  state: ('locked', None, {})
  --- edzed 5> e ts coin
  event() returned: True
  output: False
  state: ('unlocked', None, {})
  --- edzed 6> e ts coin
  event() returned: False
  output: False
  state: ('unlocked', None, {})
  --- edzed 7> e ts push
  event() returned: True
  output: False
  state: ('locked', None, {})
  --- edzed 8>

----

The final example shows the same turnstile enhanced with two counters. Let's
briefly explain how it works. The turnstile FSM is instructed to generate
these events:

- ``on_enter_unlocked=Event('cnt2', 'inc')``

  i.e. when the ``'unlocked'`` state is entered, send an ``Event`` named ``'inc'``
  (for increment) to the block ``cnt2``.

  In the definition of the Counter ``cnt2`` we see, that it sends
  another ``Event`` to an unnamed ``OutputFunc`` block on each output value
  change (``on_output``). The event name is omitted, it defaults to ``'put'``.
  This output block prints the number of coins paid to unlock, that is
  what the ``cnt2`` block counts.

- ``on_notrans=Event('cnt1', 'inc', efilter=push_locked_filter)``

  i.e. when no transition is defined for an event with respect to the current
  state, send an increment ``Event`` to the block ``cnt1`` through an event
  filter.

  The ``cnt1`` Counter prints the attempts to push a locked turnstile,
  but that is not the only no-transition event that can happen (the other
  one is trying to pay a coin to an already unlocked turnstile). We
  need to check, whether the event satisfy a condition. The event filter
  function ``push_locked_filter`` is responsible for that. It analyzes the
  data carried with the event and returns a yes or no verdict whether
  the event is allowed to be delivered.

We recommend to run this example with block debug messages turned on
(command ``adebug 1`` or just ``a 1``).

::

  import asyncio
  import edzed
  from edzed.demo import cli_repl

  class Turnstile(edzed.FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  def p_locked(cnt):
      print(f"[ attempts to push a locked turnstile: {cnt} ]")

  edzed.Counter(
      'cnt1',
      on_output=edzed.Event(edzed.OutputFunc(None, func=p_locked, on_error=None)))

  def p_coins(cnt):
      print(f"[ coins paid: {cnt} ]")

  edzed.Counter(
      'cnt2',
      on_output=edzed.Event(edzed.OutputFunc(None, func=p_coins, on_error=None)))

  def push_locked_filter(data):
      return data['event'] == 'push' and data['state'] == 'locked'

  Turnstile(
      'ts', comment="example turnstile",
      on_notrans=edzed.Event('cnt1', 'inc', efilter=push_locked_filter),
      on_enter_unlocked=edzed.Event('cnt2', 'inc'),
  )

  if __name__ == '__main__':
      print("""\
  To send a 'push' or 'coin' event to the turnstile 'ts',
  use the e[vent] command:
      e ts push
      e ts coin
  """)
      asyncio.run(edzed.run(cli_repl()))

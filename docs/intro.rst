============
Introduction
============

``edzed`` is a Python asyncio-based library for building automated systems,
i.e. systems that control outputs according to system's internal state, time and
input values.

The automated system in ``edzed`` is called a circuit, because it is built by
interconnecting provided basic blocks, almost like an electronic circuit.
``edzed`` was indeed developed on principles of a circuit simulation for an
idealized digital circuit.

Being a library means there is no function out of the box.
In order to create an usable system, the developer needs to
integrate ``edzed`` into an application.
The main part of the work is to create I/O interfaces:

- link edzed inputs with data sources
- link edzed outputs with controlled devices

The ``edzed`` code in an application is naturally divided
into two main parts:

- assemble a circuit from individual blocks
- run the simulation task


Examples
========

**"Hello, world!"**

In order to produce simple working examples, we have to mock input data
sources and use print statements instead of real outputs.

The source codes can be found in the github repository,
look into the ``examples`` directory. Of course, you can
also cut and paste the code from this web page to a file.

Run with: ``python3 examplefile.py``, press the ``ctrl-C`` key to terminate.

Don't worry if you don't understand all details, ``edzed`` comes
with a comprehensive documentation.

----

Simply print "tick .. tock"::

  import asyncio
  import edzed

  edzed.Timer('clk', comment="clock generator", t_on=0.5, t_off=0.5, on_output=edzed.Event('out'))
  edzed.OutputFunc('out', func=lambda value: print('..tock' if value else 'tick..'))

  if __name__ == '__main__':
      print('Press ctrl-C to stop')
      circuit = edzed.get_circuit()
      asyncio.run(circuit.run_forever())

A thermostat example::

  import asyncio
  import random
  import edzed

  def get_temperature():
      """Fake room thermometer (Celsius scale)."""
      t = random.uniform(20.0, 28.0)
      print(f" T={t:.1f}")
      return t

  edzed.ValuePoll(
      'thermometer',
      func=get_temperature, interval=1)
  edzed.Compare(
      'thermostat',
      low=22.0, high=24.0, on_output=edzed.Event('heater')
      ).connect('thermometer')
  edzed.OutputFunc(
      'heater',
      func=lambda hot: print(f"Heater {'off' if hot else 'on'}"),
      on_error=None
      )

  if __name__ == '__main__':
      print('Press ctrl-C to stop')
      circuit = edzed.get_circuit()
      asyncio.run(circuit.run_forever())


.. module:: edzed.demo

CLI demo tool
=============

A simple interactive command line demo tool is provided in the package.
Input values can be entered from keyboard, state changes are printed to the screen.
It allows you to test ``edzed`` to some extent without writing own applications.

To use this tool, import ``edzed.demo`` and run the :func:`edzed.demo.run_demo`
coroutine instead of the regular simulator :func:`edzed.run_forever`.

.. warning::

  Use the demo tool only for testing at the command line and nothing else.
  The code contains: ``eval <user input>``. Such code is dangerous
  if the input is coming from a malicious user.

----

Let's test :ref:`this turnstile <FSM Example>`. It allows one person
to pass by pushing it, but only if it was unlocked with a coin.
It does not allow to pass twice nor to pay twice::

  import asyncio
  from edzed import FSM, demo

  class Turnstile(FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  Turnstile('ts', comment="example turnstile")

  if __name__ == '__main__':
      asyncio.run(demo.run_demo())

Below is a sample output. We will send some events, observe the responses:

- :meth:`event` responds with ``True`` to accepted events and ``False`` to rejected events
- if an event is accepted, the state changes between ``'locked'`` and ``'unlocked'``;
  ignore the ``None`` and ``{}`` in the state for now.
- the block's output is always ``False``, you may ignore it too

::

  $ python3 turnstile.py

  Type 'help' to get a summary of available commands.
  --- edzed 0> help
  Control commands:
      h[elp] or ?                 -- show this help
      exit
      eval <python_expression>
  Circuit evaluation commands:
      c[debug] 1|0                -- circuit simulator's debug messages on|off
      d[ebug] <blockname> 1|0     -- block's debug messages on|off
      e[vent] <blockname> <type> [{'name':value, ...}]
                                  -- send event
      i[nfo] <blockname>          -- print block's properties
      l[ist]                      -- list all blocks
      p[ut] <blockname> <value>   -- send 'put' event
      s[how] <blockname>          -- print current state and output
  Command history:
      !!                          -- repeat last command
      !0 to !9                    -- repeat command N
      !?                          -- print history

  --- edzed 1> e ts push
  event() returned: False
  output: False
  state: ('locked', None, {})
  --- edzed 2> e ts coin
  event() returned: True
  output: False
  state: ('unlocked', None, {})
  --- edzed 3> e ts push
  event() returned: True
  output: False
  state: ('locked', None, {})
  --- edzed 4> e ts coin
  event() returned: True
  output: False
  state: ('unlocked', None, {})
  --- edzed 5> e ts coin
  event() returned: False
  output: False
  state: ('unlocked', None, {})
  --- edzed 6> e ts push
  event() returned: True
  output: False
  state: ('locked', None, {})
  --- edzed 7>

The final example shows the same turnstile enhanced with two counters::

  import asyncio
  from edzed import FSM, Counter, Event, OutputFunc, demo

  class Turnstile(FSM):
      STATES = ['locked', 'unlocked']
      EVENTS = [
          ['coin', ['locked'], 'unlocked'],
          ['push', ['unlocked'], 'locked'],
      ]

  def push_locked_filter(data):
      return data['state'] == 'locked' and data['event'] == 'push'

  def p_coins(cnt):
      print(f"[ coins paid: {cnt} ]")

  def p_locked(cnt):
      print(f"[ attempts to push a locked turnstile: {cnt} ]")

  Counter('cnt1', on_output=Event(OutputFunc(None, func=p_locked, on_error=None)))
  Counter('cnt2', on_output=Event(OutputFunc(None, func=p_coins, on_error=None)))

  Turnstile(
      'ts', comment="example turnstile",
      on_notrans=Event('cnt1', 'inc', efilter=push_locked_filter),
      on_enter_unlocked=Event('cnt2', 'inc'),
  )

  if __name__ == '__main__':
      asyncio.run(demo.run_demo())

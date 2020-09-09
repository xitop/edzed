.. currentmodule:: edzed

==================
List of FSM blocks
==================

.. class:: Timer(*args, restartable=True, **kwargs)

  A timer (:ref:`source <Example (Timer)>`).

  The output is ``False`` in state ``'off'`` for time duration *t_off*,
  then ``True`` in state ``'on'`` for duration *t_on*,
  and then the cycle repeats.

  By default both durations are infinite (timer disabled), i.e. the
  block is bistable. If one duration is set, the block is monostable.
  If both durations are set, the block is astable.

  Arguments:

  - *restartable*
      Boolean, if ``True`` (default), a ``'start'`` event
      occurring while in the ``'on'`` state restarts the timer
      to measure the ``'t_on'`` time from the beginning. If not
      restartable, the timer will continue to measure the
      time and ignore the event. The same holds for the ``'stop'``
      event in the ``'off'`` state.

  Standard :ref:`FSM arguments`:

  - *t_on*
      ``'on'`` state timer duration
  - *t_off*
      ``'off'`` state timer duration
  - *initdef*
      Set the initial state. Default is ``'off'``.
      Use ``initdef='on'`` to tart in the ``'on'`` state.
  - *persistent*
      Enable persistent state.

  Events:

  - ``'start'``
      Go to the ``'on'`` state. See also: *restartable*.
  - ``'stop'``
      Go to the ``'off'`` state. See also: *restartable*.
  - ``'toggle'``
      Go from ``'on'`` to ``'off'`` or vice versa.

  A conditional event :class:`EventCond`\ ``('start', 'stop')``
  is often used for ``Timer`` control.

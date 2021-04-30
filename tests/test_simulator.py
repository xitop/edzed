"""
Tests requiring asyncio and event loop.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

import asyncio
import time

import pytest

import edzed

from .utils import *


pytest_plugins = ('pytest_asyncio',)
pytestmark = pytest.mark.asyncio


async def test_empty_circuit(circuit):
    """An empty circuit is useless."""
    with pytest.raises(edzed.EdzedCircuitError, match="is empty"):
        await circuit.run_forever()


async def test_shutdown(circuit):
    """Test shutdown."""
    Noop('block')
    simtask = asyncio.create_task(circuit.run_forever())
    # await asyncio.sleep(0) after create_task is recommended,
    # but shutdown can handle the ommision
    await circuit.shutdown()
    assert simtask.done()
    await circuit.shutdown()    # will not complain


async def test_shutdown_exception(circuit):
    """Shutdown raises the exception that stopped the simulation."""
    Noop('block').connect('no_such_source')     # will fail
    simtask = asyncio.create_task(circuit.run_forever())
    with pytest.raises(Exception, match="Cannot connect"):
        await simtask
    with pytest.raises(Exception, match="Cannot connect"):
        await circuit.shutdown()


async def test_start_stop(circuit):
    """Test normal start and stop, the is_ready() test."""
    Noop('block')
    # before start
    assert not circuit.is_ready()
    assert circuit._simtask is None
    # after start
    simtask = asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    assert circuit._simtask == simtask
    assert circuit.is_ready()
    # after stop
    await circuit.shutdown()
    assert not circuit.is_ready()
    assert circuit._simtask == simtask
    assert simtask.cancelled()


async def test_wait_init(circuit):
    """Test wait_init function."""
    class ExtInput(edzed.AddonAsync, edzed.Input):
        async def init_async(self):
            await asyncio.sleep(0.09)
            self.set_output('response')

    inp = ExtInput('ext')
    logger = TimeLogger('logger')

    simtask = asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    assert inp.output is edzed.UNDEF
    logger.put('before')
    await circuit.wait_init()
    logger.put('after')
    assert inp.output == 'response'
    await circuit.shutdown()
    logger.compare([(0, 'before'), (90, 'after')])


async def test_wait_init_invalid_state(circuit):
    """Test wait_init error checking."""
    Noop('block')
    with pytest.raises(edzed.EdzedInvalidState):
        await circuit.wait_init()   # not started yet
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    await circuit.wait_init()       # OK until shutdown
    await circuit.shutdown()
    with pytest.raises(edzed.EdzedInvalidState):
        await circuit.wait_init()   # finished already


async def test_no_new_block(circuit):
    """No new blocks can be added after the simulation start."""
    Noop('block')
    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    with pytest.raises(edzed.EdzedInvalidState):
        Noop('new!')    # sorry, too late
    await circuit.shutdown()


async def test_instability_1(circuit):
    """Test an instable circuit."""
    edzed.Not('A').connect(
        edzed.Not('B').connect(
            edzed.Not('C').connect('A')
            )
        )

    simtask = asyncio.create_task(circuit.run_forever())
    with pytest.raises(edzed.EdzedCircuitError, match="instability"):
        await asyncio.wait_for(simtask, timeout=1.0)


async def test_instability_2(circuit):
    """Test a stable circuit that becomes instable."""
    ctrl = edzed.Input('ctrl', initdef=False)
    edzed.FuncBlock('xor', func=lambda a, b: bool(a) != bool(b)).connect(ctrl, 'xor')
    simtask = asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    assert ctrl.output is not edzed.UNDEF
    # so far so good, but now create an instability
    ctrl.put(True)
    with pytest.raises(edzed.EdzedCircuitError, match="instability"):
        await asyncio.wait_for(simtask, timeout=1.0)


async def test_control_block_stop(circuit):
    logger = TimeLogger('logger', mstop=True)
    timelimit(0.04, error=False)
    try:
        await asyncio.wait_for(asyncio.create_task(circuit.run_forever()), timeout=1.0)
    except asyncio.CancelledError:
        pass
    logger.compare([(40, '--stop--')])


async def test_control_block_error(circuit):
    timelimit(0.06, error=True)
    logger = TimeLogger('logger', mstop=True)
    with pytest.raises(edzed.EdzedCircuitError, match="time limit"):
        await asyncio.wait_for(asyncio.create_task(circuit.run_forever()), timeout=1.0)
    logger.compare([(60, '--stop--')])


async def test_abort_before_start(circuit):
    """Verify that abort prevents the start."""
    Noop('block')
    circuit.abort(RuntimeError('unit test'))
    simtask = asyncio.create_task(circuit.run_forever())
    try:
        await asyncio.wait_for(simtask, timeout=1.0)
    except RuntimeError:
        pass


async def no_shutdown_before_start(circuit):
    """Verify that shutdown cannot be too early (i.e no race)."""
    Noop('block')
    with pytest.raises(edzed.EdzedInvalidState):
        await circuit.shutdown()


async def test_check_not_finalized(event_loop, circuit):
    """Test check_not_finalized() internal function."""
    Noop('block')
    circuit.check_not_finalized()
    simtask = asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    with pytest.raises(edzed.EdzedInvalidState):
        circuit.check_not_finalized()
    await circuit.shutdown()
    with pytest.raises(edzed.EdzedInvalidState):
        circuit.check_not_finalized()


async def test_no_simulator_restart(circuit):
    """It is not possible to start over a finished simulation."""
    Noop('block')
    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    await circuit.shutdown()
    with pytest.raises(edzed.EdzedInvalidState, match="Cannot restart"):
        # cannot restart
        await circuit.run_forever()


async def test_no_multiple_simulations(circuit):
    """It is not possible to run the simulation more then once."""
    Noop('block')
    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0)
    with pytest.raises(edzed.EdzedInvalidState, match="already running"):
        await circuit.run_forever()
    await circuit.shutdown()


async def test_persistent_data_timestamp(circuit):
    """Persistent data are timestamped on shutdown."""
    Noop('block')
    pd = {}
    circuit.set_persistent_data(pd)
    asyncio.create_task(circuit.run_forever())
    await asyncio.sleep(0.1)
    t1 = time.time()
    await circuit.shutdown()
    t2 = time.time()

    TS = 'edzed-stop-time'
    assert pd.keys() == {TS}
    assert t1 <= pd[TS] <= t2


async def test_initialization_order(circuit):
    """Test the initialization order."""
    class Test(edzed.AddonPersistence, edzed.AddonAsync, edzed.SBlock):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.inits = []

        async def init_async(self):
            await asyncio.sleep(0)
            self.inits.append('A')  # Async

        def _restore_state(self, state):
            self.inits.append('P')  # Persistent
            if state == 'ok':
                self.set_output('out')

        def init_regular(self):
            self.inits.append('R')  # Regular
            if hasattr(self, 'x_regular'):
                self.set_output('out')

        def init_from_value(self, value):
            self.inits.append('D')  # Default
            self.set_output('out')

    t1 = Test('block1', persistent=True, initdef='default')
    t2 = Test('block2', initdef='default')
    t3 = Test('block3', initdef='default', init_timeout=0.0)
    t4 = Test('block4', persistent=True, initdef='default', x_regular='xr')
    circuit.set_persistent_data({t1.key: 1, t2.key: 2})
    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    await circuit.shutdown()

    assert t1.inits == ['P', 'A', 'R', 'D'] # all init functions
    assert t2.inits == ['A', 'R', 'D']      # P not enabled
    assert t3.inits == ['R', 'D']           # P not enabled, A disabled by zero timeout
    assert t4.inits == ['A', 'R']           # no P data saved, R succeeds -> no D


async def test_init_event(circuit):
    """Test the initialization by an event."""
    class EventOnly(edzed.SBlock):
        """Can be initialized only by an event."""
        def _event_start(self, **data):
            self.set_output(data['value'] + '!')

    ev = EventOnly('ev')
    edzed.Input('inp', initdef='IV', on_output=edzed.Event(ev, 'start'))

    asyncio.create_task(circuit.run_forever())
    await circuit.wait_init()
    await circuit.shutdown()
    assert ev.output == 'IV!'


async def test_nostart_nostop(circuit):
    """Verify that stop is called only if start was called."""
    class StartStop(edzed.CBlock):
        def start(self):
            if len(started) == CNT - 10:
                raise RuntimeError("failed start")
            started.add(self.name)
            super().start()

        def stop(self):
            stopped.add(self.name)
            super().stop()

        def calc_output(self):
            return None

    CNT = 50
    started = set()
    stopped = set()
    for i in range(CNT):
        StartStop(None)

    with pytest.raises(RuntimeError):
        await circuit.run_forever()

    assert len(started) == CNT - 10
    assert started == stopped


async def test_nostart_nopersistent(circuit):
    """Persistent data are not touched if the start fails."""
    class NoStart(edzed.CBlock):
        def start(self):
            raise RuntimeError("failed start")

        def calc_output(self):
            return None

    NoStart('nostart')
    inp1 = edzed.Input('input1', persistent=True)
    edzed.Input('input2', persistent=True, initdef=0)
    pd = {inp1.key: 33}
    circuit.set_persistent_data(pd)
    with pytest.raises(RuntimeError):
        await circuit.run_forever()
    assert pd == {inp1.key: 33}

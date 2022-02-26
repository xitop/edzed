"""
Test the OutputAsync block.
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


async def output_async(
        circuit, *,
        log,
        t1=0.1, t2=0.0,
        test_error=False, mstop=True, on_error=None, **kwargs):

    async def wait120(arg):
        logger.put(f'start {arg}')
        if test_error:
            # pylint: disable=pointless-statement
            1/0     # BOOM!
        await asyncio.sleep(0.12)
        logger.put(f'stop {arg}')
        return f'ok {arg}'

    inp = edzed.Input('inp', initdef='i1', on_output=edzed.Event('echo'))
    logger = TimeLogger('logger', mstop=mstop)
    edzed.OutputAsync('echo', coro=wait120, on_error=on_error, **kwargs)

    async def tester():     # will be cancelled on simulation error
        await asyncio.sleep(t1)
        inp.put('i2')
        if t2 > 0.0:
            await asyncio.sleep(t2)
        inp.put('i3')
        await asyncio.sleep(0.05)

    try:
        await edzed.run(tester())
        logger.put("END")
    finally:
        logger.compare(log)


async def test_cmode(circuit):
    LOG = [
        (0, 'start i1'),
        (100, 'cancel i1'), # i3 cancels i1
        (100, 'cancel i2'), # i3 cancels i2
        (100, 'start i3'),
        (150, '--stop--'),
        (220, 'stop i3'),   # wait for i3
        (220, 'END')
        ]
    await output_async(
        circuit,
        mode='c',
        log=LOG,
        on_cancel=edzed.Event(
            'logger',
            efilter=lambda data: {'value': f"cancel {data['put']['value']}"}),
        )


async def test_wmode(circuit):
    LOG = [
        (0, 'start i1'),
        # 100, i2 and i3 were put into the queue
        (120, 'stop i1'),
        (120, 'start i2'),
        (150, '--stop--'),
        (240, 'stop i2'),
        (240, 'start i3'),
        (360, 'stop i3'),
        (360, 'END')
        ]
    await output_async(circuit, mode='w', log=LOG)


async def test_smode(circuit):
    LOG = [
        (0, 'start i1'),
        (40, 'start i2'),
        (80, 'start i3'),
        (120, 'stop i1'),
        (130, '--stop--'),
        (160, 'stop i2'),
        (200, 'stop i3'),
        (200, 'END')
        ]
    await output_async(circuit, mode='s', t1=0.04, t2=0.04, log=LOG)


async def test_stop_timeout(circuit):
    LOG = [
        (0, 'start i1'),
        (100, 'start i3'),
        (150, '--stop--'),
        (190, 'END')        # timeout waiting for i3
        ]
    await output_async(circuit, mode='c', stop_timeout=0.04, log=LOG)


async def test_cmode_wmode_output(circuit):
    """Test the output value in cancel and wait modes."""
    async def otest(blk):
        assert blk.output == 1  # active
        await asyncio.sleep(0.05)


    ctest = edzed.OutputAsync('ctest', mode='cancel', coro=otest, on_error=None)
    wtest = edzed.OutputAsync('wtest', mode='wait', coro=otest, on_error=None)

    async def tester():
        await circuit.wait_init()
        for blk in (ctest, wtest):
            assert blk.output == 0  # idle
            blk.put(blk)
            assert blk.output == 0
            blk.put(blk)
            blk.put(blk)
            blk.put(blk)
            assert blk.output == 0

    await edzed.run(tester())


async def test_smode_output(circuit):
    """Test the output value in start mode."""
    LOG = [
        (0, '0 start 1'),
        (50, '1 start 2'),
        (100, '2 start 3'),
        (140, '0 stop 3'),
        (150, '--stop--'),
        (190, '1 stop 2'),
        (240, '2 stop 1'),
        (240, 'END'),
    ]

    async def otest(n):
        logger.put(f"{n} start {stest.output}")
        await asyncio.sleep(0.14)
        logger.put(f"{n} stop {stest.output}")

    logger = TimeLogger('logger', mstop=True)
    stest = edzed.OutputAsync('stest', mode='start', coro=otest, on_error=None)

    async def tester():
        await circuit.wait_init()
        assert stest.output == 0
        for i in range(3):
            stest.put(i)
            await asyncio.sleep(0.05)

    await edzed.run(tester())
    logger.put('END')
    assert stest.output == 0
    logger.compare(LOG)


async def test_smode_stop_timeout(circuit):
    """Test the output value in start mode."""
    LOG = [
        (0, '0 start 1'),
        (50, '1 start 2'),
        (100, '2 start 3'),
        (150, '--stop--'),
        (180, '0 stop 3'),
        # 1 and 2 cancelled due to timeout
        (200, 'END'),
    ]

    async def otest(n):
        logger.put(f"{n} start {stest.output}")
        await asyncio.sleep(0.18)
        logger.put(f"{n} stop {stest.output}")

    logger = TimeLogger('logger', mstop=True)
    stest = edzed.OutputAsync('stest', mode='s', coro=otest, on_error=None, stop_timeout=0.05)

    async def tester():
        await circuit.wait_init()
        assert stest.output == 0
        for i in range(3):
            stest.put(i)
            await asyncio.sleep(0.05)

    await edzed.run(tester())
    assert stest.output == 0
    logger.put('END')

    logger.compare(LOG)


async def test_cmode_guard_time(circuit):
    LOG = [
        (0, 'start i1'),
        # 100, i3 cancels i1 (and discards i2), guard time begins
        (150, '--stop--'),
        (170, 'start i3'),  # i3 came before stop, it will be run
        (290, 'stop i3'),
        (360, 'END')
        ]
    await output_async(circuit, mode='c', guard_time=0.07, log=LOG)


async def test_wmode_guard_time(circuit):
    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (150, '--stop--'),
        (190, 'start i2'),  # 70 ms after last stop
        (310, 'stop i2'),
        (380, 'start i3'),  # 70 ms after last stop,
        (500, 'stop i3'),
        (570, 'END')
        ]
    await output_async(circuit, mode='w', guard_time=0.07, log=LOG)


async def test_guard_time_after_error(circuit):
    """Guard time sleep is performed also after an error."""
    LOG = [
        (0, 'start i1'),
        (0, 'division by zero'),
        # 100, i3 was put into queue, but guard_time ends at t=130
        (130, 'start i3'),
        (130, 'division by zero'),
        (150, '--stop--'),
        (260, 'END')
        ]
    await output_async(
        circuit, mode='c', test_error=True, guard_time=0.13, log=LOG,
        on_error=edzed.Event('logger', efilter=lambda data: {'value': str(data['error'])}))


async def test_guard_time_too_long(circuit):
    with pytest.raises(ValueError, match="exceed"):
        edzed.OutputAsync(
            'not_OK',
            mode='c', coro=asyncio.sleep, guard_time=1.5, stop_timeout=1.0, on_error=None)


async def test_on_success(circuit):
    def check_trigger(data):
        assert data['trigger'] == 'success'
        v = data['value']
        if v.startswith('ok'):
            assert v.endswith(data['put']['value'])
        return True

    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (120, 'ok i1'),     # on_success - coroutine return value
        (120, 'start i2'),
        (150, '--stop--'),
        (240, 'stop i2'),
        (240, 'ok i2'),
        (240, 'start i3'),
        (360, 'stop i3'),
        (360, 'ok i3'),    # on_success
        (360, 'END')
        ]
    await output_async(
        circuit, mode='w',
        on_success=edzed.Event('logger', efilter=check_trigger),
        log=LOG)


async def test_on_error_ignore(circuit):
    LOG = [
        (0, 'start i1'),
        # (0, ??), <== error ignored
        (100, 'start i3'),
        # (100, ??), <== error ignored
        (150, '--stop--'),
        (150, 'END')
        ]
    await output_async(circuit, mode='c', test_error=True, log=LOG)


async def test_on_error_abort(circuit):
    LOG = [
        (0, 'start i1'),
        (0, '--stop--'),
        ]
    with pytest.raises(
            edzed.EdzedCircuitError, match="error reported by 'echo': ZeroDivisionError"):
        await output_async(
            circuit, mode='c', test_error=True, on_error=edzed.Event.abort(), log=LOG)


async def test_on_error_custom(circuit):
    """on_error=... overrides the default error handling."""
    def check_trigger(data):
        assert data['trigger'] == 'error'
        assert isinstance(data['error'], ZeroDivisionError)
        assert data['put']['value'] in {'i1', 'i3'}
        return True

    LOG = [
        (0, 'start i1'),
        (0, 'division by zero'),
        (100, 'start i3'),
        (100, 'division by zero'),
        (150, '--stop--'),
        (150, 'END')
        ]
    await output_async(
        circuit, mode='c', test_error=True, log=LOG,
        on_error=edzed.Event('logger', efilter=(
            check_trigger,
            lambda data: {'value': str(data['error'])}
            )
        ))


async def test_cmode_stop(circuit):
    """Test the stop data in cancel mode."""
    LOG = [
        (0, 'start i1'),
        (120, 'stop i1'),
        (150, 'start i3'),
        (200, '--stop--'),
        (200, 'start CLEANUP'),
        (320, 'stop CLEANUP'),
        (320, 'END')
        ]
    VLOG = [
        (120, 'ok i1'),
        (320, 'ok CLEANUP'),
        ]

    vlog = TimeLogger('vlog')
    await output_async(
        circuit, mode='c', stop_data={'value': 'CLEANUP'}, t1=0.15, log=LOG,
        on_success=edzed.Event('vlog'))
    vlog.compare(VLOG)


async def test_smode_stop(circuit):
    """Test the stop data in start mode."""
    LOG = [
        (0, 'start i1'),
        (40, 'start i2'),
        (80, 'start i3'),
        (120, 'stop i1'),
        (130, '--stop--'),
        (160, 'stop i2'),
        (200, 'stop i3'),
        # stop data is always processed last
        (200, 'start CLEANUP'),
        (320, 'stop CLEANUP'),
        (320, 'END')
        ]
    VLOG = [
        (120, 'ok i1'),
        (160, 'ok i2'),
        (200, 'ok i3'),
        (320, 'ok CLEANUP'),
        ]

    vlog = TimeLogger('vlog')
    await output_async(
        circuit, mode='s', stop_data={'value': 'CLEANUP'}, t1=0.04, t2=0.04, log=LOG,
        on_success=edzed.Event('vlog'))
    vlog.compare(VLOG)


async def test_executor(circuit):
    """Test execution of blocking output functions in threads."""
    THREADS = 8
    # add 1 ms for large overhead (10->11)
    LOG = [(11 + 20*i, i) for i in range(THREADS)] + [(210, '--stop--')]

    def blocking(v):
        time.sleep(0.01 + 0.015*v)
        return v

    log = TimeLogger('log', mstop=True)
    blocks = [
        edzed.OutputAsync(
            str(i), mode='c', coro=edzed.InExecutor(blocking),
            on_success=edzed.Event(log), on_error=edzed.Event.abort())
        for i in range(THREADS)]

    async def tester():
        await circuit.wait_init()
        for i, blk in enumerate(blocks):
            blk.put(i)
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.17)

    await edzed.run(tester())
    log.compare(LOG)


async def test_executor_args(circuit):
    """Test argument passing."""
    def blocking(a, b, *, c=0):
        time.sleep(0.04)
        return 100*a + 10*b + c

    LOG = [(40, 123), (60, 120), (80, 789), (100, 780)]

    log = TimeLogger('log')
    out1 = edzed.OutputAsync(
        "out1", mode='wait', coro=edzed.InExecutor(blocking),
        f_args=('a', 'b'), f_kwargs=('c'),
        on_success=edzed.Event(log), on_error=edzed.Event.abort())
    out2 = edzed.OutputAsync(
        "out2", mode='wait', coro=edzed.InExecutor(blocking),
        f_args=('a', 'b'),  # no kwargs
        on_success=edzed.Event(log), on_error=edzed.Event.abort())


    async def tester():
        await circuit.wait_init()
        out1.put(None, a=1, b=2, c=3)
        out1.put(None, a=7, b=8, c=9)
        await asyncio.sleep(0.02)
        out2.put(None, a=1, b=2, c=3)
        out2.put(None, a=7, b=8, c=9)

    await edzed.run(tester())
    log.compare(LOG)

"""
Helpers for unit tests.
"""

import asyncio
import itertools
import sys
import time

import pytest

import edzed

P3_12 = sys.version_info >= (3, 12)

class Noop(edzed.CBlock):
    """
    A block for testing which accepts any inputs.
    """

    def calc_output(self):
        return None


class EventMemory(edzed.SBlock):
    """Accept any event. Output the last event for testing."""

    def _event(self, etype, data):
        self.set_output((etype, data))

    def init_regular(self):
        self.set_output(None)


_FILL = object()
_AFMT = ("timestamps: {} is way {} expected {}\n"
         + "(please repeat; timing tests may produce a false negative under high load!)")

def compare_logs(tlog, slog, delta_abs=10, delta_rel=0.15):
    """
    Compare the tlog with an expected standard slog.

    The allowed negative difference is only 1/10 of the allowed positive
    difference, because due to CPU load and overhead the tlog is
    expected to lag behind the slog, and not to outrun it.

    delta_abs is in milliseconds (10 = +10/-2 ms difference allowed),
    delta_rel is a ratio (0.15 = +15/-3 % difference allowed),
    the timestamp values must pass the combined delta.

    Timestamp 0.0 (expected value) is not checked at all,
    because most false negatives were caused by startup
    delays.
    """
    for (tts, tmsg), (sts, smsg) in itertools.zip_longest(tlog, slog, fillvalue=(_FILL, None)):
        assert tts is not _FILL, f"Missing: {(sts, smsg)}"
        assert sts is not _FILL, f"Extra: {(tts, tmsg)}"
        assert tmsg == smsg, f"data: {(tts, tmsg)} does not match {(sts, smsg)}"
        if sts is None or sts == 0:
            continue
        assert (tts - delta_abs)/sts <= 1.0 + delta_rel, _AFMT.format(tts, "above", sts)
        assert (tts + delta_abs/10)/sts >= 1.0 - delta_rel/10, _AFMT.format(tts, "below", sts)


def _default_select(data):
    return data.get('value')

# inheriting from AddonAsync in order to get the stop mark
# timestamp right (shutdown async before sync rule)
class TimeLogger(edzed.AddonAsync, edzed.SBlock):
    """
    Maintain a log with relative timestamps in milliseconds since start.

    Usage: - logger.log('log entry'), or
           - send a 'log' event with value='log entry'
    """

    def __init__(self, *args, mstart=False, mstop=False, select=_default_select, **kwargs):
        self._ts = None
        self.tlog = []
        self._select = select
        self._mstart = mstart
        self._mstop = mstop
        super().__init__(*args, stop_timeout=0.1, **kwargs)

    def _append(self, data):
        self.tlog.append((int(1000 * (time.monotonic() - self._ts) + 0.5), data))

    def _event(self, etype, data):
        if etype != 'log':
            return NotImplemented
        self._append(self._select(data))
        return None

    def log(self, value, **data):
        data['value'] = value
        data['source'] = 'n/a'
        return self.event('log', **data)

    def start(self):
        super().start()
        self.set_output(False)
        self._ts = time.monotonic()
        if self._mstart:
            self._append('--start--')

    def stop(self):
        if self._mstop:
            self._append('--stop--')
        super().stop()

    async def stop_async(self):
        pass

    def compare(self, slog, **kwargs):
        """Compare the log with an expected standard."""
        compare_logs(self.tlog, slog, **kwargs)


def timelimit(limit, error):
    """Create a timer stopping the circuit after some time limit."""
    edzed.Timer(
        'test_utils_timelimit',
        t_off=limit,
        on_output=edzed.Event(
            '_ctrl',    # automatic edzed.ControlBlock('_ctrl')
            'abort' if error else 'shutdown',
            efilter=(
                edzed.Edge(rise=True),
                lambda data: {**data, 'error': 'time limit exceeded'}
                # shutdown event type will ignore the 'error' item
                )
            )
        )


class _FakeSimTask:
    """
    A fake asyncio task that can be cancelled (and nothing else).

    The usage of _FakeSimTask in init() below prevents these warnings:
      - coroutine ... was never awaited
      - Task was destroyed but it is pending!
    """
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def cancelled(self):
        return self._cancelled

    done = cancelled


def init(circ):
    """
    Initialize circuit for testing without requiring asyncio.

    Circuits with asyncio based blocks should be tested
    with the regular simulator.
    """
    # pylint: disable=protected-access
    # code from Circuit.run_forever()
    circ._simtask = _FakeSimTask()
    circ.sblock_queue = asyncio.Queue()
    circ._check_persistent_data()
    circ._resolver.resolve()
    circ.finalize()
    for blk in circ.getblocks():
        blk.start()
    # code from Circuit._init_sblocks_sync()
    for blk in circ.getblocks(edzed.SBlock):
        if not blk.is_initialized():
            circ.init_sblock(blk, full=True)
            if not blk.is_initialized():
                raise edzed.EdzedCircuitError(f"{blk}: not initialized")


@pytest.fixture(name='circuit')
def fixture_circuit():
    """Return a new empty circuit."""
    edzed.reset_circuit()
    return edzed.get_circuit()


@pytest.fixture(scope="module", params=[False, True], autouse=P3_12)
async def fixture_task_factories(request):
    """Run tests twice: with eager tasks off and on."""
    factory = asyncio.eager_task_factory if request.param else None
    asyncio.get_running_loop().set_task_factory(factory)

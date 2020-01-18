"""
Helpers for unit tests.
"""

# pylint: disable=missing-docstring, no-self-use, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable

import asyncio
import itertools
import time

import pytest

import edzed


__all__ = [
    'Noop', 'EventMemory', 'TimeLogger',
    'compare_logs', 'timelimit', 'init', 'circuit']


class Noop(edzed.CBlock):
    """
    A block for testing which accepts any inputs.
    """

    def _eval(self):
        return None


class EventMemory(edzed.SBlock):
    """Accept any event. Output the last event for testing."""

    def _event(self, etype, data):
        self.set_output((etype, data))

    def init_regular(self):
        self.set_output(None)


_FILL = object()

def compare_logs(tlog, slog, delta_abs=10, delta_rel=0.1):
    """
    Compare the tlog with an expected standard slog.

    The allowed negative difference is only 1/5 of the allowed positive
    difference, because due to CPU load and overhead the tlog is
    expected to lag behind the slog, not outrun it.

    delta_abs is in milliseconds (10 = +10/-2 ms difference allowed),
    delta_rel is a ratio (0.1 = +10/-2 % difference allowed),
    the timestamp values must pass at least one delta test.
    """
    for (tts, tmsg), (sts, smsg) in itertools.zip_longest(tlog, slog, fillvalue=(_FILL, None)):
        assert tts is not _FILL, f"Missing: {(sts, smsg)}"
        assert sts is not _FILL, f"Extra: {(tts, tmsg)}"
        assert tmsg == smsg, f"data: {(tts, tmsg)} does not match {(sts, smsg)}"
        if sts is None:
            continue    # no value to compare with
        if -delta_abs/5 <= (tts - sts) <= delta_abs:
            continue    # absolute difference OK
        if sts != 0 and -delta_rel/5 <= (tts/sts - 1.0) <= delta_rel:
            continue    # relative difference OK
        assert False, f"timestamps: {tts} is not approx. {sts} " \
            "(timing tests may produce a false negative under high load!)"


DEFAULT_SELECT = lambda data: data.get('value')
class TimeLogger(edzed.SBlock):
    """
    Maintain a log with relative timestamps in milliseconds since start.

    Usage: logger.put('log entry')
    """

    def __init__(self, *args, mstart=False, mstop=False, select=DEFAULT_SELECT, **kwargs):
        self._ts = None
        self.tlog = []
        self._select = select
        self._mstart = mstart
        self._mstop = mstop
        super().__init__(*args, **kwargs)

    def _append(self, data):
        self.tlog.append((int(1000 * (time.monotonic() - self._ts) + 0.5), data))

    def _event(self, etype, data):
        if etype != 'put':
            return NotImplemented
        self._append(self._select(data))
        return None

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
            'error' if error else 'shutdown',
            efilter=(
                edzed.Edge(rise=True),
                lambda data: {**data, 'error': 'time limit exceeded'}
                # shutdown event type will ignore the 'error' item
                )
            )
        )


def init(circ):
    """
    Initialize circuit for testing without requiring asyncio.

    Circuits with asyncio based blocks should be tested
    with the regular simulator.
    """
    # code from Circuit.run_forever()
    circ._simtask = asyncio.get_event_loop().create_task(asyncio.sleep(999))    # fake simtask
    circ.sblock_queue = asyncio.Queue()
    circ._resolve_events()
    circ._init_connections()
    for blk in circ.getblocks():
        blk.start()
    # code from Circuit._init_sblocks_sync()
    for blk in circ.getblocks(edzed.SBlock):
        if not blk.is_initialized():
            circ.init_sblock(blk)
            if not blk.is_initialized():
                raise edzed.EdzedError(f"{blk}: not initialized")


@pytest.fixture
def circuit():
    """Return a new empty circuit."""
    edzed.reset_circuit()
    return edzed.get_circuit()

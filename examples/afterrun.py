import asyncio
import logging
import time

import edzed
from edzed.demo import cli_repl

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


AfterRun('ar', x_percentage=50, debug=True)

if __name__ == '__main__':
    print("""\
An after-run FSM demo.

1. start with sending the event 'start'
   to the block named 'ar':
      e ar start
   the output goes from False to True
2. wait few seconds (runtime T)
3. stop with: e ar stop
   the output remains True
4. observe that after 50% of time T
   the output automatically returns to False
""")
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(edzed.run(cli_repl()))

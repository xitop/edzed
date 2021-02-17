import asyncio
import time

import edzed, edzed.demo

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


ar = AfterRun('ar', x_percentage=50, debug=True)

if __name__ == '__main__':
    print('Press ctrl-C to stop\n')
    asyncio.run(edzed.demo.run_demo())

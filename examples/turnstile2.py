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

Counter('cnt1', on_output=Event(OutputFunc(None, func=p_locked)))
Counter('cnt2', on_output=Event(OutputFunc(None, func=p_coins)))

Turnstile(
    'ts', desc="example turnstile",
    on_notrans=Event('cnt1', 'inc', efilter=push_locked_filter),
    on_enter_unlocked=Event('cnt2', 'inc'),
)

if __name__ == '__main__':
    asyncio.run(demo.run_demo())

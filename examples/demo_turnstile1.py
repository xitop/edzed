import asyncio
from edzed import FSM, demo

class Turnstile(FSM):
    STATES = ['locked', 'unlocked']
    EVENTS = [
        ['coin', ['locked'], 'unlocked'],
        ['push', ['unlocked'], 'locked'],
    ]

Turnstile('ts', desc="example turnstile")

if __name__ == '__main__':
    asyncio.run(demo.run_demo())

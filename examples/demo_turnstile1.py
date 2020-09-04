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
    print("Documentation: https://edzed.readthedocs.io/en/latest/intro.html#cli-demo-tool\n")
    asyncio.run(demo.run_demo())

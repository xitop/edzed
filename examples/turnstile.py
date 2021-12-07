import asyncio
import logging
import edzed
from edzed.demo import cli_repl

class Turnstile(edzed.FSM):
    STATES = ['locked', 'unlocked']
    EVENTS = [
        ['coin', ['locked'], 'unlocked'],
        ['push', ['unlocked'], 'locked'],
    ]

Turnstile('ts', comment="example turnstile")

if __name__ == '__main__':
    print("""\
https://edzed.readthedocs.io/en/latest/intro.html#cli-demo-tool

To send a 'push' or 'coin' event to the turnstile 'ts',
use the e[vent] command:
    e ts push
    e ts coin
""")
    asyncio.run(edzed.run(cli_repl()))

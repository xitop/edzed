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

def p_locked(cnt):
    print(f"[ attempts to push a locked turnstile: {cnt} ]")

edzed.Counter(
    'cnt1',
    on_output=edzed.Event(edzed.OutputFunc(None, func=p_locked, on_error=None)))

def p_coins(cnt):
    print(f"[ coins paid: {cnt} ]")

edzed.Counter(
    'cnt2',
    on_output=edzed.Event(edzed.OutputFunc(None, func=p_coins, on_error=None)))

def push_locked_filter(data):
    return data['event'] == 'push' and data['state'] == 'locked'

Turnstile(
    'ts', comment="example turnstile",
    on_notrans=edzed.Event('cnt1', 'inc', efilter=push_locked_filter),
    on_enter_unlocked=edzed.Event('cnt2', 'inc'),
)

if __name__ == '__main__':
    print("""\
https://edzed.readthedocs.io/en/latest/intro.html#cli-demo-tool

To send a 'push' or 'coin' event to the turnstile 'ts',
use the e[vent] command:
    e ts push
    e ts coin
""")
    asyncio.run(edzed.run(cli_repl()))

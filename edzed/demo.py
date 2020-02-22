"""
A simple interactive utility for learning and evaluating edzed.

WARNING: Do not use for anything else. Contains "eval <user input>".

Usage:
    1. append following lines to a python file with an edzed
    circuit definition (e.g. circuit1.py):
    --- begin ---
    if __name__ == '__main__':
        import asyncio  # if not imported at the top
        import edzed.demo
        asyncio.run(edzed.demo.run_demo())
    --- end ---
    2. run the demo:
        python3 circuit1.py

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

import ast
import asyncio
from dataclasses import dataclass
import logging
import sys
from typing import Callable

from . simulator import get_circuit

if sys.platform == 'win32':
    # Python 3.7 only, ProactorEventLoop is the default on 3.8+
    asyncio.set_event_loop(asyncio.ProactorEventLoop())


__all__ = ['run_demo']

LIMIT = 4096

HELP = """\
Control commands:
    h[elp] or ?                 -- show this help
    exit
    eval <python_expression>
Circuit evaluation commands:
    c[debug] 1|0                -- circuit simulator's debug messages on|off
    d[ebug] <blockname> 1|0     -- block's debug messages on|off
    e[vent] <blockname> <type> [{'name':value, ...}]
                                -- send event
    i[nfo] <blockname>          -- print block's properties
    l[ist]                      -- list all blocks
    p[ut] <blockname> <value>   -- send 'put' event
    s[how] <blockname>          -- print current state and output
Command history:
    !!                          -- repeat last command
    !0 to !9                    -- repeat command N
    !?                          -- print history
"""

def _cmd_cdebug(value):
    if value == '0':
        logging.getLogger().setLevel(logging.INFO)
        print("circuit simulator debug off")
        return
    if value == '1':
        logging.getLogger().setLevel(logging.DEBUG)
        print("circuit simulator debug on")
        return
    raise ValueError("Argument must be 0 (debug off) or 1 (debug on)")


def _cmd_debug(blk, value):
    if value == '0':
        blk.debug = False
        print(f"{blk}: debug off")
        return
    if value == '1':
        print(f"{blk}: debug on")
        blk.debug = True
        return
    raise ValueError("Argument must be 0 (debug off) or 1 (debug on)")


def _cmd_eval(expr):
    result = eval(expr)         # pylint: disable=eval-used
    print(f"result: {result}")


def _cmd_event(blk, etype, data=None):
    data = {} if data is None else ast.literal_eval(data)
    retval = blk.event(etype, **data)
    print(f"event() returned: {retval}")
    _cmd_show(blk)


def _cmd_help():
    print(HELP)


def _cmd_info(blk):
    for name, value in sorted(blk.get_conf().items()):
        print(f"{name}: {value}")


def _cmd_list():
    circuit = get_circuit()
    for name, btype in sorted((blk.name, type(blk).__name__) for blk in circuit.getblocks()):
        print(f"{name}   ({btype})")


def _cmd_put(blk, value):
    retval = blk.put(ast.literal_eval(value))
    print(f"put() returned: {retval}")
    _cmd_show(blk)


def _cmd_show(blk):
    output = blk.output
    state = blk.get_state()
    if state == output:
        print(f"output and state: {output!r}")
    else:
        print(f"output: {output!r}")
        print(f"state: {state!r}")


def _complete(cmd):
    if cmd == '?':
        return 'help'
    for fullcmd in _PARSE:
        # no abbreviation for eval
        if fullcmd.startswith(cmd) and not 'eval' == fullcmd != cmd:
            return fullcmd
    raise ValueError(f"Unknown command: {cmd}, try: help")


@dataclass(frozen=True)
class CmdInfo:
    func: Callable
    blk: bool = True    # first arg is block name
    args: int = 0       # number of mandatory arguments (excl. the block name if blk is set)
    optargs: int = 0    # number of optional arguments

_PARSE = {
    'cdebug': CmdInfo(func=_cmd_cdebug, blk=False, args=1),
    'debug': CmdInfo(func=_cmd_debug, args=1),
    'eval': CmdInfo(func=_cmd_eval, blk=False, args=1),
    'event': CmdInfo(func=_cmd_event, args=1, optargs=1),
    # exit is handled in the loop
    'help': CmdInfo(func=_cmd_help, blk=False),
    'info': CmdInfo(func=_cmd_info),
    'list': CmdInfo(func=_cmd_list, blk=False),
    'put': CmdInfo(func=_cmd_put, args=1),
    'show': CmdInfo(func=_cmd_show),
}


async def repl():
    """REPL = read, evaluate, print loop."""
    loop = asyncio.get_event_loop()
    rstream = asyncio.StreamReader(limit=LIMIT, loop=loop)
    protocol = asyncio.StreamReaderProtocol(rstream, loop=loop)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    # assuming stdout is not blocking to keep this demo simple

    history = [None] * 10
    circuit = get_circuit()
    idx = 0
    print("Type 'help' to get a summary of available commands.")
    while True:
        await asyncio.sleep(0)
        print(f'--- edzed {idx}> ', end='', flush=True)
        line = (await rstream.readline()).decode()
        if not line:
            print('received EOF')
            break
        line = line.strip()
        if not line:
            continue
        cmd, *args = line.split(None, 1)
        if cmd == 'exit':
            # arguments ignored
            break
        try:
            if len(cmd) == 2 and cmd[0] == '!' and cmd[1] in "0123456789?!":
                # history
                if args:
                    raise TypeError(f"{cmd} command takes no arguments")
                hcmd = cmd[1]
                prev = (idx - 1) % 10
                if hcmd == '?':
                    for i, hist in enumerate(history):
                        if hist is not None:
                            print(f"{'!' if i == prev else ' '}{i}> {hist[0]}")
                else:
                    # !0-!9 or !!
                    hist = history[int(hcmd) if '0' <= hcmd <= '9' else prev]
                    if hist is None:
                        raise LookupError("history: command not found")
                    cmd, func, args = hist
                    print(f"--- edzed history> {cmd}")
                    func(*args)
            else:
                cmd = _complete(cmd)
                cmdinfo = _PARSE[cmd]
                minargs = cmdinfo.args + (1 if cmdinfo.blk else 0)
                maxargs = minargs + cmdinfo.optargs
                if args != []:
                    args = args[0].split(None, maxargs - 1)
                if not minargs <= len(args) <= maxargs:
                    if minargs == maxargs:
                        raise TypeError(f"{cmd} command takes {minargs} argument(s)")
                    raise TypeError(f"{cmd} command takes {minargs} to {maxargs} arguments")
                if cmdinfo.blk:
                    args[0] = circuit.findblock(args[0])
                cmdinfo.func(*args)
                history[idx] = (line, cmdinfo.func, args)
                idx = (idx + 1) % 10
        except Exception as err:
            print(f"ERROR: {err}")


async def run_demo():
    """Run a circuit simulation and an edzed REPL."""
    logging.basicConfig(level=logging.INFO)
    tsim = asyncio.create_task(get_circuit().run_forever())
    trepl = asyncio.create_task(repl())
    await asyncio.wait([tsim, trepl], return_when=asyncio.FIRST_COMPLETED)
    for task in (tsim, trepl):
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as err:
            print(f"Error: {err!r}")

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
        asyncio.run(edzed.run(edzed.demo.cli_repl())
    --- end ---
    2. run the demo:
        python3 circuit1.py

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

from __future__ import annotations

import ast
import asyncio
import collections
from collections.abc import Callable
from dataclasses import dataclass
import logging
import signal
import sys
from typing import Any, Optional

from . import simulator
from . import block


__all__ = ['cli_repl', 'run_demo']

LIMIT = 4096    # StreamReader buffer limit
HISTSIZE = 20   # history list size

HELP = """\
Control commands:
    h[elp] or ?                 -- show this help
    exit
    eval <python_expression>
Circuit evaluation commands:
  Debug messages:
    a[debug] 1|0                -- all blocks' debug messages on|off
    b[debug] <blockname> 1|0    -- block's debug messages on|off
    c[debug] 1|0                -- circuit simulator's debug messages on|off
  Events:
    e[vent] <blockname> <type> [{'name':value, ...}]
                                -- send event with optional data
    p[ut] <blockname> <value>   -- send 'put' event
  Info:
    l[ist]                      -- list all blocks
    i[nfo] <blockname>          -- print block's properties
    s[how] <blockname>          -- print current state and output
Command history:
    !?                          -- print history
    !N                          -- repeat command N (integer)
    !-N                         -- repeat command current minus N
    !!                          -- repeat last command (same as !-1)
"""

def _check_01(value: str) -> bool:
    if value == '0':
        return False
    if value == '1':
        return True
    raise ValueError("Argument must be 0 (debug off) or 1 (debug on)")


def _cmd_adebug(value: str) -> None:
    bvalue = _check_01(value)
    circuit = simulator.get_circuit()
    circuit.set_debug(bvalue, *circuit.getblocks())
    print(f"all blocks: debug {'on' if bvalue else 'off'}")


def _cmd_bdebug(blk: block.Block, value: str) -> None:
    bvalue = _check_01(value)
    blk.debug = bvalue
    print(f"{blk}: debug {'on' if bvalue else 'off'}")


def _cmd_cdebug(value: str) -> None:
    bvalue = _check_01(value)
    circuit = simulator.get_circuit()
    circuit.debug = bvalue
    print(f"circuit simulator: debug {'on' if bvalue else 'off'}")


def _cmd_eval(expr: str) -> None:
    result = eval(expr)         # pylint: disable=eval-used
    print(f"result: {result}")


def _cmd_event(blk: block.SBlock, etype: str, data: Optional[str] = None) -> None:
    datadict = {} if data is None else ast.literal_eval(data)
    if not isinstance(datadict, dict):
        raise TypeError(
            f"Invalid event data: {datadict!r}. "
            "Expected is a dict literal: {{'name':value, ...}}")
    retval = blk.event(etype, **datadict)
    print(f"event() returned: {retval}")
    _cmd_show(blk)


def _cmd_help() -> None:
    print(HELP)


def _cmd_info(blk: block.Block) -> None:
    for name, value in sorted(blk.get_conf().items()):
        print(f"{name}: {value}")


def _cmd_list() -> None:
    circuit = simulator.get_circuit()
    for name, btype in sorted((blk.name, type(blk).__name__) for blk in circuit.getblocks()):
        print(f"{name}   ({btype})")


def _cmd_put(blk: block.SBlock, value: Any) -> None:
    retval = blk.put(ast.literal_eval(value))
    print(f"put() returned: {retval}")
    _cmd_show(blk)


def _cmd_show(blk) -> None:
    output = blk.output
    state = blk.get_state()
    if state == output:
        print(f"output and state: {output!r}")
    else:
        print(f"output: {output!r}")
        print(f"state: {state!r}")


def _complete(cmd: str) -> str:
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
    'adebug': CmdInfo(func=_cmd_adebug, blk=False, args=1),
    'bdebug': CmdInfo(func=_cmd_bdebug, args=1),
    'cdebug': CmdInfo(func=_cmd_cdebug, blk=False, args=1),
    'eval': CmdInfo(func=_cmd_eval, blk=False, args=1),
    'event': CmdInfo(func=_cmd_event, args=1, optargs=1),
    # exit is handled in the loop
    'help': CmdInfo(func=_cmd_help, blk=False),
    'info': CmdInfo(func=_cmd_info),
    'list': CmdInfo(func=_cmd_list, blk=False),
    'put': CmdInfo(func=_cmd_put, args=1),
    'show': CmdInfo(func=_cmd_show),
}

_HFORMAT = " cmd {:2d}> {}"

async def _cli_repl() -> None:
    """
    Edzed demo CLI REPL.

    CLI = command line interface; REPL = read-evaluate-print loop.
    """
    loop = asyncio.get_running_loop()
    rstream = asyncio.StreamReader(limit=LIMIT, loop=loop)
    protocol = asyncio.StreamReaderProtocol(rstream, loop=loop)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    history: collections.deque[tuple[str, Callable, list]] = collections.deque(maxlen=HISTSIZE)
    cmdnum = 1
    circuit = simulator.get_circuit()
    print("Type 'help' to get a summary of available commands.")
    print("Type 'a 1' to enable debug messages in all blocks.")
    while True:
        await asyncio.sleep(0)
        print(f'--- edzed {cmdnum}> ', end='', flush=True)
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
            if cmd and cmd[0] == '!':
                # history
                if args:
                    raise TypeError("history: syntax error")
                cmd = cmd[1:]
                hlen = len(history)
                if cmd == '?':
                    for hnum, line_func_args in enumerate(history, start=cmdnum-hlen):
                        print(_HFORMAT.format(hnum, line_func_args[0]))
                    continue
                if cmd == '!':
                    hnum = -1
                else:
                    try:
                        hnum = int(cmd)
                    except ValueError:
                        raise ValueError("history !N: invalid command number N") from None
                if hnum < 0:
                    hnum += cmdnum
                if not 1 <= hnum < cmdnum:
                    raise LookupError(f"history: command {hnum} does not exist")
                idx = hnum + hlen - cmdnum
                # beware: no IndexError for small negative indices
                if not 0 <= idx < hlen:
                    raise LookupError(f"history: command {hnum} not in memory")
                line, func, args = history[hnum + hlen - cmdnum]
                print(_HFORMAT.format(hnum, line))
            else:
                # command
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
                func = cmdinfo.func
            # execute
            func(*args)
            history.append((line, func, args))
            cmdnum += 1
        except Exception as err:
            print(f"ERROR: {err}")


async def cli_repl(setup_logging: bool = True) -> None:
    """
    A wrapper preparing the run environment for _cli_repl().

    Set up:
    - SIGINT handler for better UX.
    - logging configuration that displays debug messages

    Refer to _cli_repl().
    """
    if setup_logging:
        logging.basicConfig(level=logging.DEBUG)

    task = asyncio.current_task()
    def sigint_handler(_signum, _frame):
        # using the _threadsafe variant because we need also to wake up the event loop
        call_soon = asyncio.get_running_loop().call_soon_threadsafe
        call_soon(print, " -- Interrupt signal received, exiting the edzed demo")
        call_soon(task.cancel)
        # NOT calling the Python's default interrupt handler
    saved_sigint_handler = signal.signal(signal.SIGINT, sigint_handler)
    try:
        await _cli_repl()
    finally:
        # revert to the original state, because we broke the SIGINT handlers chain
        signal.signal(signal.SIGINT, saved_sigint_handler)

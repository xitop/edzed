"""
asyncio.shield improved.
"""

import asyncio
from typing import Any, Awaitable


async def shield_cancel(aw: Awaitable) -> Any:
    """
    Shield from cancellation while aw is awaited.

    Pending CancelledError is raised when aw is finished.

    Make the shielded code and its execution time as short as possible.

    NEVER EVER SUPPRESS TASK CANCELLATION COMPLETELY!
    """
    task = asyncio.ensure_future(aw)
    cancel_exc = None
    while True:
        try:
            retval = await asyncio.shield(task)
        except asyncio.CancelledError as err:
            if task.done():
                # cancelled from within aw
                raise
            cancel_exc = err
        else:
            break
    if cancel_exc:
        raise cancel_exc
    return retval

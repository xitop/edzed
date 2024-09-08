"""
Find reference cycles caused be an exception stored in a local variable

** EXPERIMENTAL FEATURE **

"""

import collections
import gc
import types
import warnings
import pprint

def _test_cycle(cycle_object, quiet):
    """Print a reference cycle if it exists."""
    seen = set()
    queue = collections.deque()
    queue.append([cycle_object])
    # pylint: disable-next=too-many-nested-blocks
    while queue:
        chain = queue.popleft()
        obj = chain[0]
        seen.add(id(obj))
        for ref in gc.get_referents(obj):
            if isinstance(ref, (str, type)):
                continue
            newchain = [ref] + chain
            if id(ref) in seen:
                if not quiet:
                    warnings.warn(
                        f"Found a cycle with {cycle_object!r}. "
                        "Run the pytest with '-s' to see details.")
                    print("Found a cycle:")
                    print("-----")
                    for i, link in enumerate(newchain):
                        print(f"{i}: {link!r}")
                        if isinstance(link, types.FrameType):
                            print("locals:")
                            pprint.pprint(link.f_locals)
                    print("-----")
                return True
            queue.append(newchain)
    return False


def gc_exceptions(quiet=False):
    """Find exceptions referenced only by a stack frame."""
    # source: https://stackoverflow.com/a/74672755/5378816
    exceptions = [
        obj for obj in gc.get_objects(generation=0) if isinstance(obj, Exception)
        ]
    exceptions2 = [
        exc for exc in exceptions
        if len(gc.get_referrers(exc)) == 2 and all(
            isinstance(ref, types.FrameType) or ref is exceptions
            for ref in gc.get_referrers(exc))
        ]
    return any(_test_cycle(exc, quiet) for exc in exceptions2)

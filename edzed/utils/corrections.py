"""
Select suggestions from given possibilities to correct
a supposedly mistyped string.
"""

from difflib import SequenceMatcher
import operator

LIMIT = 0.6

def suggest_corrections(badname, goodnames):
    """
    Find suggestions in goodnames for a supposedly mistyped badname.

    Return a list.
    """
    if not goodnames:
        return []
    badname_lower = badname.lower()
    suggestions = (
        (name, SequenceMatcher(None, a=badname_lower, b=name.lower(), autojunk=False).ratio())
        for name in goodnames
        )
    suggestions = [(name, ratio) for name, ratio in suggestions if ratio >= LIMIT]
    if not suggestions:
        return []
    suggestions.sort(key=operator.itemgetter(1), reverse=True)
    return [name for name, _ in suggestions]    # strip ratios

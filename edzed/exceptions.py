"""
Exceptions.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

__all__ = ['EdzedError', 'EdzedInvalidState']

class EdzedError(Exception):
    """Critical error."""

class EdzedInvalidState(EdzedError):
    """Invalid state error."""

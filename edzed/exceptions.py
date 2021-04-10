"""
Exceptions.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

__all__ = ['EdzedError', 'EdzedCircuitError', 'EdzedInvalidState', 'EdzedUnknownEvent']

class EdzedError(Exception):
    """Base class for Edzed exceptions."""

class EdzedCircuitError(EdzedError):
    """Critical error."""

class EdzedInvalidState(EdzedError):
    """Invalid state error."""

class EdzedUnknownEvent(EdzedError):
    """Event type not supported."""

__all__ = ['EdzedError', 'EdzedInvalidState']

class EdzedError(Exception):
    """Critical error."""

class EdzedInvalidState(EdzedError):
    """Invalid state error."""

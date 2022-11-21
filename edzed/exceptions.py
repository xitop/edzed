"""
Exceptions.

- - - - - -
Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

_exception_notes = hasattr(BaseException, 'add_note')

__all__ = [
    'add_note',
    'EdzedError', 'EdzedCircuitError', 'EdzedInvalidState', 'EdzedUnknownEvent']

class EdzedError(Exception):
    """Base class for Edzed exceptions."""

class EdzedCircuitError(EdzedError):
    """Critical error."""

class EdzedInvalidState(EdzedError):
    """Invalid state error."""

class EdzedUnknownEvent(EdzedError):
    """Event type not supported."""

def add_note(exc: BaseException, note:str) -> None:
    """Add a note to an exception."""
    if _exception_notes:
        # supported natively in Python >= 3.11
        exc.add_note(note)
    elif exc.args and isinstance(exc.args[0], str):
        # fallback: prepend the note to the error message
        exc.args = (f"[{note}] {exc.args[0]}", *exc.args[1:])

import gc

import pytest

from .utils_gc import gc_exceptions

@pytest.fixture(scope='module', autouse=True)
def _teardown():
    gc.disable()    # do not interfere with timing tests
    yield None
    gc_exceptions()
    gc.enable()
    gc.collect()

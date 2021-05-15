import gc

import pytest

@pytest.fixture(scope='module', autouse=True)
def _teardown():
    gc.disable()    # do not interfere with timing tests
    yield None
    gc.enable()
    gc.collect()

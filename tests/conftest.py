import asyncio

import pytest

@pytest.fixture(scope='module', autouse=True)
def _teardown():
    yield None
    # prevent ResourceWarning (in devel mode)
    asyncio.get_event_loop().close()

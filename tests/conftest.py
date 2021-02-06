import asyncio

import pytest

@pytest.fixture(scope='module', autouse=True)
def clear_files_teardown():
    yield None
    # prevent ResourceWarning (in devel mode)
    asyncio.get_event_loop().close()

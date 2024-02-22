"""
Tests that does not fit elsewhere.
"""

import warnings

import edzed

def test_version():
    version = edzed.__version__
    version_info = edzed.__version_info__
    assert isinstance(version, str)
    assert isinstance(version_info, tuple)
    if 'NEXT' in version:
        warnings.warn("version not set")
        return
    y, m, d = version_info
    assert y >= 22 and 1 <= m <= 12 and 1 <= d <= 31

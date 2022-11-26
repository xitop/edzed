"""
Tests that does not fit elsewhere.
"""

# pylint: disable=missing-docstring, protected-access
# pylint: disable=invalid-name, redefined-outer-name, unused-argument, unused-variable
# pylint: disable=wildcard-import, unused-wildcard-import

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

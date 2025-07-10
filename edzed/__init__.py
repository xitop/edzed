"""
A library for building small automated systems.

The edzed package contains:
 - classes for creating combinational and sequential blocks
 - methods for building a circuit by connecting the blocks
 - a simple event-driven zero-delay digital circuit simulator

- - - - - -
Copyright (c) 2019-2025 Vlado Potisk <edzed@poti.sk>.

Released under the MIT License.

Docs: https://edzed.readthedocs.io/en/latest/
Home: https://github.com/xitop/edzed/
"""

__version_info__ = (25, 7, 10)
__version__ = '.'.join(str(n) for n in __version_info__)

from . import exceptions, block, addons, fsm, simulator, blocklib  # mypy, pylint
from .addons import *
from .block import *
from .exceptions import *
from .fsm import *
from .simulator import *
# .demo is not imported to edzed
from .blocklib.cblocks import *
from .blocklib.filters import *
from .blocklib.fsms import *
from .blocklib.sblocks1 import *
from .blocklib.sblocks2 import *
from .blocklib.timedate import *

__all__ = [
    '__version__',
    '__version_info__',
    *addons.__all__,
    *block.__all__,
    *exceptions.__all__,
    *fsm.__all__,
    *simulator.__all__,
    *blocklib.cblocks.__all__,
    *blocklib.filters.__all__,
    *blocklib.fsms.__all__,
    *blocklib.sblocks1.__all__,
    *blocklib.sblocks2.__all__,
    *blocklib.timedate.__all__,
    ]

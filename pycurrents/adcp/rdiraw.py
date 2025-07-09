"""
This module is obsolete, having been refactored into 3 new modules.  As part of
the refactoring, octopusraw became raw_simrad.
"""

import warnings

from .raw_base import *  # noqa: F403
from .raw_rdi import *  # noqa: F403
from .raw_multi import *  # noqa: F403


warnings.warn(
    """
The rdiraw module is deprecated as of 2025-01-01.  Imports should be switched
to one or more of raw_base, raw_rdi, raw_simrad, or raw_multi.  For example,
Multiread is now in raw_multi.""",
    DeprecationWarning,
)

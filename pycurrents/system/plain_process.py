"""
Utility for running a process when one wants to ensure that
no more than one instance is running.

This is linux-specific because of its use of the "ps" command.
It might work on a Mac, but this would have to be checked.

Note: this was developed for UHDAS.
"""
import logging

from pycurrents.system._single_function import _SingleFunction
from pycurrents.system.checker import Checker

# Standard logging
_log = logging.getLogger(__name__)


class SingleFunction(_SingleFunction, Checker):
    pass

#!/usr/bin/env python
"""
Convert files like uhdas_cfg.py and proc_cfg.py to toml.
"""
from argparse import ArgumentParser

from pycurrents.adcp.uhdas_cfg_api import simple_py_to_toml

parser = ArgumentParser(description=__doc__)
parser.add_argument(
    "pyfiles", nargs="+", metavar="PYFILE", help=("Python data file to be converted")
)
args = parser.parse_args()
for fname in args.pyfiles:
    simple_py_to_toml(fname)

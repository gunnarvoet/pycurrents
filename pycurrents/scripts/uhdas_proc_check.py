#!/usr/bin/env python
from argparse import ArgumentParser
import os
import sys
from pycurrents.adcp.uhdasconfig import ProcConfigChecker


usage = "Mine, Check and Assess UHDAS processing configuration"
arglist = sys.argv[1:]
parser = ArgumentParser(usage=usage)
parser.add_argument(
    "-u", "--uhdasdir", dest="uhdasdir", default=os.getcwd(),
    help="Path to UHDAS directory structure. "
         "Default value: ./")

parser.add_argument(
    "-s",  "--shipkey", dest="shipkey", default=None,
    help="Ship abbreviation. "
         "If not provided, the code will attempt to guess it")

options = parser.parse_args(args=arglist)

checker = ProcConfigChecker(
    uhdas_dir=options.uhdasdir, ship_key=options.shipkey)
print(checker)

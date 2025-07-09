#!/usr/bin/env python

"""
Modify binfiles to change the yearbase for decimal day columns.

This is useful when multiple UHDAS legs were started for a given
cruise, and they span a year boundary.  In this case the rbin files
and the *.raw.log.bin files contain decimal day columns with yearbase
values that differ, depending on the year when the leg was started.

Run this as a script with no arguments to see the help text.

"""

import numpy as np

from pycurrents.file.binfile_n import binfile_n
from pycurrents.codas import to_day

import os
import sys
from optparse import OptionParser
from pycurrents.system.pathops import make_filelist

def adjust(inbin, outbin, inyear, outyear, fields):
    delta = to_day(inyear, outyear, 1)
    bf = binfile_n(inbin)
    dat = bf.records
    for field in fields:
        dat[field] -= delta
    out = binfile_n(outbin, mode="w",
                            name=bf.name,
                            columns=bf.columns)
    outdat = dat.view(dtype=bf.dtype, type=np.ndarray)
    outdat.shape = (outdat.size // bf.ncolumns, bf.ncolumns)
    out.write(outdat)
    out.close()
    bf.close()

#####################################################


usage = """bf_change_year.py <options> <args>

    Change yearbase for selected decimal day columns in binfiles.

    Example for raw adcp *.log.bin files:

bf_change_year.py -o raw_new/os38 --from=2011 --to=2012\
 --fields=unix_dday:instrument_dday raw/os38/*.log.bin

    Example for gyro rbin files:

bf_change_year.py -o rbin_new/gyro --from=2011 --to=2012\
 --fields=u_dday rbin/gyro/*.rbin

    Example for posmv rbin files (both gps and pvm together):

bf_change_year.py -o rbin_new/posmv --from=2011 --to=2012\
 --fields=u_dday:dday rbin/posmv/*.rbin

Note: we do *not* want to change monotonic dday fields.

        args can be a binfile path, set of paths, or glob expression
        options are not optional!  All options listed below are required.
"""

def main():

    parser = OptionParser(usage=usage)
    parser.add_option("-o", "--outpath", action="store", dest="outpath",
                      help="output directory")
    parser.add_option("--from", type="int", dest="inyear",
                      help="yearbase for input")
    parser.add_option("--to", type="int", dest="outyear",
                      help="yearbase for output")
    parser.add_option("--fields", type="string", dest="fields",
                      help="colon-delimited list of column names")

    options, args = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(-1)

    try:
        os.makedirs(options.outpath)
    except OSError:
        pass

    files = make_filelist(args)
    fields = options.fields.split(":")

    for fpath in files:
        fname = os.path.split(fpath)[-1]
        outfpath = os.path.join(options.outpath, fname)
        adjust(fpath, outfpath, options.inyear, options.outyear, fields)

if __name__ == "__main__":
    main()



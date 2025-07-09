#!/usr/bin/env python

"""
Extract a range of profiles from a raw adcp file, and write
it to a new file.  Tested on EC, WH, OS, BB (does not work on NB)

Sometimes a sequence of LADCP casts is made without stopping and
restarting the instrument, so a single file needs to be split.
This script allows one to do that by extracting a range of
pings and writing them to a new file.::

    cut_raw_adcp.py wh wh0.dat 0 1000 wh0a.dat
    cut_raw_adcp.py wh wh0.dat 1000 -1 wh0b.dat

or for shipboard ADCP data::
    cut_raw_adcp.py os os0.dat -10 -1 osa.dat

Python-style indexing is used to specify ping ranges to be
extracted.

"""

import sys

from pycurrents.adcp.raw_multi import extract_raw

def usage():
    print("Usage: cut_raw_adcp.py INST sourcefile i0 i1 destfile")
    print(__doc__)
    sys.exit()

if __name__ == '__main__':

    if len(sys.argv) != 6:
        print("FAILED: requires 5 arguments:")
        usage()

    inst, infile, i0, i1, outfile = sys.argv[1:]

    if inst not in ('wh', 'os', 'pn', 'bb', 'ec'):
        print("FAILED: inst %s not supported" %(inst))
        usage()

    try:
        i0 = int(i0)
        i1 = int(i1)
        if i0>=i1:
            print("First index must be less than second index.")
            print("Not extracting any profiles")
            usage()
    except:
        print("FAILED to convert indices to integer: ", i0, i1)
        usage()

    print("Extracting ping range %d to %d" % (i0, i1))

    data=extract_raw(infile, inst, i0, i1, outfile=outfile)

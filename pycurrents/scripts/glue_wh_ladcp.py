#!/usr/bin/env python

"""
Some WH300 instruments, such as the new one used in 2009 on the
CLIVAR P6 line, occasionally break a profile in two because of
a system hang followed by a watchdog wakeup.

This script glues together such profiles into a single file so
it can be processed with the LDEO software.

For N files to be concatenated, it takes N+1 command line arguments:
the filenames to be concatenated followed by the destination.  It will
not proceed if the destination already exists; this is a safety
feature.

"""

import sys
import os

from pycurrents.adcp.raw_multi import rawfile


if len(sys.argv) < 4:
    print("Usage: glue_wh_ladcp.py file1 file2 ... filen concatenated_file")
    sys.exit(0)

fnlist = sys.argv[1:-1]
fncat = sys.argv[-1]

if os.path.exists(fncat):
    print("Destination file %s already exists; delete it, or choose another" % fncat)
    sys.exit(0)

nblist = []
for fn in fnlist:
    print(fn)
    rf1 = rawfile(fn, 'wh', trim=True)
    nb1 = rf1.nprofs * rf1.header.nbytes
    rf1.close()
    nblist.append(nb1)

rfcat = open(fncat, 'wb')
for fn, nb in zip(fnlist, nblist):
    rfcat.write(open(fn).read(nb))
rfcat.close()



#!/usr/bin/env python

'''
check validity of NB150 data files; print number of ensembles

This does not appear to be used anywhere in our code or instructions, but
might still be useful.  (2020-12-26)
'''

import sys
import struct
import array
from functools import reduce


def nbraw_ngood(sourcefile):
    igood = 0
    while 1:
        a = array.array('B')
        try:
            a.fromfile(sourcefile, 2)
            nbytes = struct.unpack('>H', a.tostring())[0]
            a.fromfile(sourcefile, nbytes)
            cs_read = a[-1] + a[-2] * 256
            cs = reduce(lambda x, y: x + y, a[:-2]) % 65536
            #print nbytes, cs, cs_read
            if cs == cs_read:
                igood = igood + 1
            else:
                break
        except EOFError:
            break
    return igood


if __name__ == '__main__':

    for file in sys.argv[1:]:
        print(file, end=' ')
        sourcefile = open(file)
        igood = nbraw_ngood(sourcefile)
        print(igood)
        sourcefile.close()

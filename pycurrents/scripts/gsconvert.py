#! /usr/bin/env python

''' Convert postscript files to image files using ghostscript.

    Usage: gsconvert.py infile outfile

    Both arguments are required; the extension must match
    the type of file.  In particular, the extension of
    "outfile" must be one of 'jpg', 'png', 'pgm', 'pnm',
    or 'ppm', yielding conversion to one of these types.

    The module may also be imported:

    from pycurrents.plot.gsconvert import gsconvert
    gsconvert(infilename, outfilename, [margin])

    The bounding box of the postscript file is used to
    calculate the size of the image file, and the amount by
    which the image must be shifted on the page to eliminate
    all but a small margin.

    For a much more flexible conversion utility, see
    convertps.py.

'''

import sys

from pycurrents.plot.gsconvert import gsconvert


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit()
    gsconvert(sys.argv[1], sys.argv[2])

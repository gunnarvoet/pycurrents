#!/usr/bin/env python
'''
convert one or more image(s) to a different size (eg. make a thumbnail)
'''
import os
import argparse
import logging

from pycurrents.plot.mpltools import png_thumbnail


parser = argparse.ArgumentParser(
    description="Make a thumbnail for one or more png files."
                 "By default, the filename will have a 'T' appended before the extension."
                 )

parser.add_argument('-w', '--width',
                    type=int,
                    default=300,
                    help='width of thumbnail in pixels (default: 300)')

parser.add_argument('-o', '--outdir',
                    default=None,
                    help='place thumbnail here instead of at the source')

parser.add_argument('-t', '--tname',
                    default='T',
                    help='suffix to basename used to identify it as a thumbnail')

parser.add_argument('--loglevel', metavar='LEVEL',
                     default='warning',
                     choices=['warning', 'info', 'debug'],
                     help='logging module root logger level (default: warning)')

parser.add_argument('filenames', metavar='FILENAME', nargs='+',
                    help='original png file')

opts = parser.parse_args()

_log = logging.getLogger()
_log.setLevel(getattr(logging, opts.loglevel.upper()))

handler = logging.StreamHandler()
_log.addHandler(handler)

width = int(opts.width)
for fname in opts.filenames:
    if os.path.exists(fname) or os.path.exists(fname+".png") :
        try:
            png_thumbnail(fname, width= width, outdir=opts.outdir, tname=opts.tname)
        except Exception as e:
            _log.exception(f'could not make thumbnail for file {fname}:\n{e}')
    else:
        _log.warning('filename %s does not exist' % (fname))

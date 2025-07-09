#! /usr/bin/env python

''' Replace the existing BoundingBox line in a ps or eps
    file with one determined by ghostscript. The file name is not
    changed; the replacement file will land in the current
    directory or an an optionally specified directory,
    possibly overwriting the input file.
    If an optional suffix is specified, it will be added to
    the output file name before the extension.

    Usage: fixbbox.py [options] file [file...]

    options:

        -m --margin           points to add (default 0)
        -d --directory        output directory
        -s --suffix           output file suffix

   This program is particularly useful for plots made using
   m_map, for the original bounding boxes are too large.

   2004/03/30 EF

'''

import sys
import os
import os.path
import re
import getopt

bb_pat = re.compile('%%BoundingBox:\s*(\d+)\s*(\d+)\s*(\d+)\s*(\d+)')

def convert(infilename, outfilename, margin):

    gs_cmd = 'gs -q -sDEVICE=bbox %s' % infilename
    print(gs_cmd)
    (p_in, p_out, p_err) = os.popen3(gs_cmd)
    p_in.close()
    ps = p_err.read()
    print(ps)
    bbox_str = bb_pat.search(ps).groups()
    (llx, lly, urx, ury) = list(map(int, bbox_str))
    if margin:
        llx -= margin
        lly -= margin
        urx += margin
        ury += margin
    newbbox = "%%%%BoundingBox: %d %d %d %d\n" % (llx, lly, urx, ury)
    with open(infilename) as newreadf:
        pslines = newreadf.readlines()
    for i, line in enumerate(pslines):
        if bb_pat.match(line):
            pslines[i] = newbbox
            break
    with open(outfilename, 'w') as file:
        file.writelines(pslines)


if __name__ == '__main__':

    shortopts = "m:d:s:"
    longopts = ["margin=", "directory=", "suffix="]
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
        if not args:
            raise getopt
    except getopt.GetoptError:
        print(__doc__)
        sys.exit(2)

    margin = 0
    directory = './'
    suffix = ''
    for o, a in opts:
        if o in ("-d", "--directory"):
            directory = a
        if o in ("-m", "--margin"):
            margin = int(a)
        if o in ("-s", "--suffix"):
            suffix = a



    if not os.path.isdir(directory):
        print("Output directory %s does not exist yet." % directory)
        os.makedirs(directory)
        print("Created output directory: %s" % directory)

    for infilename in args:
        dir, name = os.path.split(infilename)
        if suffix:
            namebase, ext = os.path.splitext(name)
            name = namebase + suffix + ext
        outfilename = os.path.join(directory, name)
        convert(infilename, outfilename, margin)

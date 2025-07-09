#! /usr/bin/env python

''' Convert postscript or pdf files to image files using ghostscript
    and the netpbm package.

    Usage: convertps.py [options] file [file...]

    Input filenames will be assumed to refer to postscript
    files or encapsulated postscript.
    (Add later: support for .ps.gz.)

    options:

        -t --type             output type: jpg, png, or gif
                                 default is png
        -a --antialias        antialias graphics; text is antialiased
                                 in any case.

        -d --directory        output directory
                                 default is current working directory
        -o --outbase          output file name base if different from
                                 input name (only works on the first
                                 file converted)

        -m --margin           pixels to add to postscript bounding box
                                 default is 6
                                 Postscript only at present.

        -p --pixels_per_inch  pixels per inch (like -r option to gs)
                                 default is 72
        -g --gs_options       string for additional options for gs

        -n --netpbm_options   string for additional options for netpbm

        -r --rotate           cw        rotate 90 degrees cw
                              ccw                         ccw
                              180              180 degrees

        -b --bounding_box     calculate bounding box instead of using
                                 the one in the file; this is useful
                                 when an image is extracted from a pdf
                                 file with Acroread, for example,
                                 because the image is centered on
                                 a full-size page in the ps file.
                                 Not used for pdf at present.

        -v --verbose          print all external commands

    The bounding box of the postscript file is used to
    calculate the size of the image file, and the amount by
    which the image must be shifted on the page to eliminate
    all but a small margin.  If a bounding box is not found
    in the file, it is calculated.  Note, however, that the
    positioning of the image in the output file may still
    end up wrong if the postscript file includes
    "initgraphics", which cancels our attempt to position
    the image.  GRADS gxps does this; use gxeps instead,
    which also makes a much more compact file.

    No bbox or margin calculation or correction is done with pdf.
    I don't know how to modify this information in a pdf file, and
    don't want to make an intermediate ps file to do so.

    To make the image smaller on the screen, specify fewer than
    72 pixels per inch; to make it larger, specify more.

    If the requested output directory does not exist, it will
    be created.

    2004/03/17 EF
      Added antialiasing; text antialiasing is always on, graphics
      is turned on with the -a option.  It makes the file much bigger,
      but quite a bit nicer looking.  It also slows the conversion.

    2004/07/02 EF
      Fixed bug: now it works even if an eps file lacks a "showpage"
      command.  Also, changed so that the input postscript file is
      read only once.

    2005/10/04 EF
      Added -b option; added image interpolation to antialiasing
      option.

    2005/11/09 EF
      Added pnmquant for gif files; this needs to be improved
      so that it is only done when necessary.  We might also want
      an option of specifying a single mapfile for all plots in
      a series.

'''

import sys
import os
import os.path
import getopt

from pycurrents.plot.convertps import convert, netpbm_dict, rotate_opts
from pycurrents.plot.convertps import _print
import pycurrents.plot.convertps  # so we can assign to _verbose

if __name__ == '__main__':

    shortopts = "t:d:m:g:n:p:r:o:abv"
    longopts = ["type=", "directory=", "margin=",
                "gs_options=", "netpbm_options=",
                "pixels_per_inch=",
                "rotate=","outbase=", "antialias",
                "bounding_box", "verbose"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
        if not args:
            raise getopt
    except getopt.GetoptError:
        print(__doc__)
        sys.exit(2)

    type = 'png'
    directory = './'
    margin = 6
    gs_options = ''
    netpbm_options = ''
    pixels_per_inch = 72
    rotate = None
    outbase = ''
    antialias_graphics = False
    bounding_box = False
    # _verbose is module-level
    for o, a in opts:
        if o in ("-t", "--type"):
            if a in list(netpbm_dict.keys()):
                type = a
            else:
                print('\nInput argument error: "-t" arg is incorrect\n')
                print(__doc__)
                sys.exit(-1)

        if o in ("-d", "--directory"):
            directory = a
        if o in ("-m", "--margin"):
            margin = int(a)
        if o in ("-g", "--gs_options"):
            gs_options = a
        if o in ("-n", "--netpbm_options"):
            netpbm_options = a
        if o in ("-p", "--pixels_per_inch"):
            try:
                pixels_per_inch = int(a)
            except:
                print('\nInput argument error: "-p" arg should be an integer\n')
                print(__doc__)
                sys.exit(-1)
        if o in ("-r", "--rotate"):
            if a in list(rotate_opts.keys()):
                rotate = a
            else:
                print('\nInput argument error: "-r" arg is incorrect\n')
                print(__doc__)
                sys.exit(-1)
        if o in ("-o", "--outbase"):
            outbase = a
        if o in ("-a", "--antialias"):
            antialias_graphics = True
        if o in ("-b", "--bounding_box"):
            bounding_box = True
        if o in ("-v", "--verbose"):
            pycurrents.plot.convertps._verbose = True




    if not os.path.isdir(directory):
        print("Output directory %s does not exist yet." % directory)
        os.makedirs(directory)
        print("Created output directory: %s" % directory)

    filesconverted = 0
    for infilename in args:
        try:
            dir, name = os.path.split(infilename)
            if (filesconverted == 0) and (outbase != ''):
                outbase, outext = os.path.splitext(outbase)
                outfilename = os.path.join(directory, outbase + '.' + type)
            else:
                namebase, ext = os.path.splitext(name)
                outfilename = os.path.join(directory, namebase + '.' + type)

            _print("\nConverting %s to %s" % (infilename, outfilename))
            convert(infilename, outfilename, type,
                    gs_options, netpbm_options,
                    margin, pixels_per_inch,
                    rotate, antialias_graphics,
                    bounding_box)
            filesconverted = filesconverted + 1
        except:
            print("Could not convert %s" % infilename)

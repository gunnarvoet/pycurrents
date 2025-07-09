'''
routines to convert postscript or pdf files to image files using ghostscript
'''


import os
import re
import tempfile
import shutil


_verbose = False

def _print(arg):
    if _verbose:
        print(arg)

class convert_Error(Exception):
    pass


#The following two dictionaries are put here so we can check
# our input arguments in the script.
rotate_opts = {'cw' : '-cw', 'ccw' : '-ccw', '180': '-rotate180'}

netpbm_dict = {'gif' : 'ppmtogif',
               'png' : 'pnmtopng',
               'jpg' : 'pnmtojpeg'}


bb_pat = re.compile('%%BoundingBox:\s*(-{0,1}\d+)\s*(\d+)\s*(\d+)\s*(\d+)')
# (minus sign above is needed for files from Illustrator)


def gs(infilename, outfilename, out_format, gs_options = '', margin = 6,
       ppi = 72, antialias_graphics = False, bounding_box = False):

    # Translations from short name to device; device names not
    # in the dictionary will be used without translation.
    gsdev_dict = {'jpg' : 'jpeg',
                  'pnm' : 'pnmraw',
                  'png256' : 'png256'}

    # EPS files may or may not end in a "showpage"; it could be
    # hidden by a redefinition, so we can't just search for it.
    # Fortunately, having a double "showpage" doesn't hurt, so
    # we will simply add one to every eps file (identified via
    # its extension).  (If there is no "showpage", gs will not
    # produce any output.)
    base, ext = os.path.splitext(infilename)
    with open(infilename) as newreadf:
        ps = newreadf.read()
    if ext[-3:].lower() == 'eps':
        ps += '\nshowpage\n'

    gs_shift = ''
    gs_geometry = ''

    if ext[-2:].lower() == 'ps':
        bbox_str = ''
        try:
            bbox_str = bb_pat.search(ps).groups()
        except:
            print('''convertps.py:
                      This file lacks a bounding box; we will calculate it,
                      but the postscript file may have other problems such
                      an "initgraphics" statement that will wreck our
                      attempt to position the image.
                  ''')
        if bounding_box or bbox_str == '':
            gs_cmd = 'gs -q -sDEVICE=bbox -'
            _print(gs_cmd)
            (p_in, p_out, p_err) = os.popen3(gs_cmd)
            p_in.write(ps)
            p_in.close()
            p_out.close()
            gs_out = p_err.read()
            _print(gs_out)
            bbox_str = bb_pat.search(gs_out).groups()

        (llx, lly, urx, ury) = [int(num) for num in bbox_str]

        width = urx - llx + 2 * margin
        height = ury - lly + 2 * margin
        shiftleft = llx - margin
        shiftdown = lly - margin

        if ppi != 72:
            sc = ppi/72.0
            width = int(width * sc)
            height = int(height * sc)

        gs_shift = '%d neg %d neg translate\n' % (shiftleft, shiftdown)
        _print("prepending shift to ps file: %s" % gs_shift.rstrip())
        gs_geometry = '-g%dx%d' % (width, height)


    gs_out = '-sOutputFile=' + outfilename
    try:
        dev = gsdev_dict[out_format]
    except KeyError:
        dev = out_format
    gs_dev = '-sDEVICE=' + dev
    gs_aa = '-dTextAlphaBits=4'
    if antialias_graphics:
        gs_aa = gs_aa + ' -dGraphicsAlphaBits=4 -dDOINTERPOLATE'
    gs_cmd = ' '.join(['gs', '-q', gs_dev, gs_aa, gs_out,
                               '-r%d' % ppi,
                               gs_options, gs_geometry, '-'])
    _print(gs_cmd)
    os.popen(gs_cmd, 'w').write(gs_shift + ps)

def netpbm(infilename, outfilename, out_format, np_options = ''):

    cmd = ' '.join([netpbm_dict[out_format], np_options, infilename, '>',
                      outfilename])
    _print(cmd)
    os.system(cmd)

def pnm_rotate(fn, rotate):
    if not rotate:
        return
    o = rotate_opts[rotate]
    newfn = tempfile.mktemp()
    cmd = ' '.join(['pnmflip', o, fn, '>', newfn])
    _print(cmd)
    os.system(cmd)
    shutil.copyfile(newfn, fn)
    os.remove(newfn)

def pnmquant(fn, N=256):
    '''Limit the number of colors; like netpbm pnmquant program
    '''
    mapfn = tempfile.mktemp()
    newfn = tempfile.mktemp()
    cmd = ' '.join(['pnmcolormap', str(N), fn, '>', mapfn])
    _print(cmd)
    os.system(cmd)
    cmd = ' '.join(['pnmremap', '-fs', '-mapfile', mapfn, fn, '>', newfn])
    _print(cmd)
    os.system(cmd)
    shutil.copyfile(newfn, fn)
    os.remove(newfn)
    os.remove(mapfn)


def convert(infilename, outfilename, outformat,
            gs_options = '', np_options = '',
            margin = 6, pixels_per_inch = 72,
            rotate = None, antialias_graphics = False,
            bounding_box = False):
    tmpfilename = tempfile.mktemp()
    gs(infilename, tmpfilename, 'pnm', gs_options, margin,
       pixels_per_inch, antialias_graphics, bounding_box)
    pnm_rotate(tmpfilename, rotate)
    if outformat == 'gif':
        pnmquant(tmpfilename)
    netpbm(tmpfilename, outfilename, outformat, np_options)
    os.remove(tmpfilename)

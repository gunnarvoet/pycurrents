'''
Convert postscript files to image files using ghostscript.

'''
import os
import re


class gsconvert_Error(Exception):
    pass

def gsconvert(infilename, outfilename, margin = 6):

    (infileroot, infileext) = os.path.splitext(infilename)
    (outfileroot, outfileext) = os.path.splitext(outfilename)
    gshelp = os.popen('gs --help').read()

    gsdev_mo = re.search('Available devices:(.*)Search path', gshelp, re.S)
    gsdev_str = gsdev_mo.group(1)
    gsdev_list = gsdev_str.split()

    gsdev_dict = {'jpg' : 'jpeg',
                  'png' : 'png16m',
                  'pgm' : 'pgmraw',
                  'pnm' : 'pnmraw',
                  'ppm' : 'ppmraw'}

    gsdev = gsdev_dict[outfileext[1:]]
    print(gsdev)

    if gsdev not in gsdev_list:
        print('gs lacks device ', gsdev)
        raise gsconvert_Error

    bb_pat = re.compile('%%BoundingBox:\s*(\d+)\s*(\d+)\s*(\d+)\s*(\d+)')
    with open(infilename) as newreadf:
        ps = newreadf.read()
    bbox_str = bb_pat.search(ps).groups()
    (llx, lly, urx, ury) = list(map(int, bbox_str))

    width = urx - llx + 2 * margin
    height = ury - lly + 2 * margin
    shiftleft = llx - margin
    shiftdown = lly - margin

    gs_shift = '%d neg %d neg translate\n' % (shiftleft, shiftdown)
    print(gs_shift)
    gs_geometry = '-g%dx%d' % (width, height)
    gs_out = '-sOutputFile=' + outfilename
    gs_dev = '-sDEVICE=' + gsdev
    # The following seem to have no effect with the png etc files.
    #gs_other = '-dNOINTERPOLATE'
    #gs_other = '-dDOINTERPOLATE'
    gs_other = ''
    gs_cmd = ' '.join(('gs', '-q', gs_dev, gs_out,
                               gs_other, gs_geometry, '-', infilename))
    print(gs_cmd)
    os.popen(gs_cmd, 'w').write(gs_shift)

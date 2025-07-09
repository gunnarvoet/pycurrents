#!/usr/bin/env python
'''
link_uhdaslegs.py
------------------

link directories (cruise legs) to one cruise location for processing
    i.e. link each file in raw/*/*, rbin/*/*

linux and OSX only
You must generate gbins from scratch

'''

import os
import argparse
import glob
import time

usage = '\n'.join(["Examples:",
                     "   with one source directory at a time:",
                     "       link_uhdaslegs.py  w0605_legs/w0605a w0605",
                     "       link_uhdaslegs.py  w0605_legs/w0605b w0605",
                     "       link_uhdaslegs.py  w0605_legs/w0605c w0605",
                     "",
                     "   or with a glob expression (notice the single quotes):",
                     "       link_uhdaslegs.py 'w605_legs/w0605*' w0605"
                     "",
                     ])

parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="assemble UHDAS cruise segments using symbolic links",
    epilog=usage)

parser.add_argument('--fullpath',
                    action='store_true',
                    help='use full path names (otherwise uses relative) ')
parser.add_argument('-v', '--verbose',
                    action='store_true',
                    help='verbose: print everything being linked')
parser.add_argument('cruise_segment',
                    help='source directory (cruise segment), or glob expression')
parser.add_argument('merged_dir',
                    help='location to link raw and rbin data')


opts = parser.parse_args()
if opts.fullpath:
    usepath = os.path.abspath
else:
    usepath = os.path.relpath

fromdirs = glob.glob(opts.cruise_segment)
todir   = opts.merged_dir
startdir = os.getcwd()


def make_link(fromname, todir):
    fp = os.path.abspath(fromname)
    fname = os.path.basename(fp)
    target = os.path.abspath(os.path.join(todir, fname))
    try:
        if os.path.exists(target):
            print('target %s exists.  Not linking' % (target))
        else:
            os.chdir(todir)
            os.symlink(usepath(fp), fname)
            os.chdir(startdir)
    except:
        print('failure linking %s' % (fp))
        print('target is %s' % (target))


# link contents of 'from' to 'to'

if not os.path.isdir(todir):
    os.mkdir(todir)
    print('making destination directory %s' % (todir))
    time.sleep(2)

for subdir in ('raw', 'rbin'):
    subdir_path = os.path.join(todir, subdir)
    if not os.path.isdir(subdir_path):
        os.mkdir(subdir_path)
        print('making directory %s' % (subdir_path))

for fromdir in fromdirs:
    # do raw and rbin
    for datadir in ('raw', 'rbin'):
        dirlist =  os.listdir(os.path.join(fromdir, datadir))
        instdirs = [d for d in dirlist if d not in ('config', 'log', 'reports')]
        print('------ %s -----\n' % (datadir))
        for instdir in instdirs:
            frompath = os.path.join(fromdir, datadir, instdir)
            topath   = os.path.join(todir,   datadir, instdir)
            if not os.path.isdir(topath):
                os.mkdir(topath)
                print('making directory %s' % (topath))
            filelist = os.listdir(frompath)
            print('linking  %s/* to %s/*\n' % (frompath, topath))

            for fname in filelist:
                fromname = usepath(os.path.join(frompath, fname))
                if opts.verbose:
                    print('linking %s' % (fromname))
                make_link(fromname, topath)

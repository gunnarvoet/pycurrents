#!/usr/bin/env python

'''
generate gbin/headings (also requires generation of ztimefit)

usage:

# to see usage:

make_hbins.py --help
make_hbins.py

# to run:

make_hbins.py controlfile


# controlfile:
# comments are preceeded by '#'
# should look like this (replace right-hand-side values with your own)

#--- begin hbin control file ---
cruisedir  /home/data/RR1201         # UHDAS data directory
gbin       ./gbin                    # put it somewhere else
time_inst  gpsnav                    # get time from the gpsnav directory
time_msg   gps                       # use the files with message 'gps'
sonar      nb150                     # just a placeholder

# optional for tighter control on POSMV QC
# use 0.2 to only use good data, use 60 to show all data (evaluation)
acc_heading_cutoff  60

#----- end hbin control file ----

(1) make controlfile
(2) run

    make_hbins.py controlfile

'''

import os
import sys
import glob
import logging

from pycurrents.adcp.gbin import Gbinner
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.system.misc import Bunch, Cachefile
from pycurrents.adcp.adcp_specs import Sonar

# Standard logging
_log = logging.getLogger(__file__)


def guess_hdg_inst_msgs(rbindir):
    hdg_inst_msgs=[]
    subdirs = [d.name for d in os.scandir(rbindir) if d.is_dir()]
    for s in subdirs:
        # generate dict with key=msg, val=msg_filelist
        mdict = {}
        flist = glob.glob(os.path.join(rbindir, s, '*rbin'))
        for f in flist:
            msg = f.split('.')[-2]
            if msg not in mdict:
                mdict[msg] = []
            mdict[msg].append(f)
        for msg, msg_filelist in mdict.items():
            for f in msg_filelist:
                try:
                    data=BinfileSet(f)
                except:
                    continue
                if 'heading' in data.columns:
                    hdg_inst_msgs.append((s, msg))
                    break
    return hdg_inst_msgs


def get_params(controlfile):
    try:
        pcache = Cachefile(controlfile)
        pcache.read()
    except:
        _log.error(f'could not evaluate {controlfile} parameters')
    #
    if 'gbin' not in list(pcache.cachedict.keys()):
        pcache.cachedict['gbin'] = None
    #
    if 'edit_params' not in list(pcache.cachedict.keys()):
        pcache.cachedict.edit_params = None
    if 'method' not in list(pcache.cachedict.keys()):
        pcache.cachedict.method = 'linear'
    if 'acc_heading_cutoff' in list(pcache.cachedict.keys()):
        pcache.cachedict['rbin_edit_params'] = dict(
            acc_heading_cutoff= pcache.cachedict['acc_heading_cutoff'])
    else:
        pcache.cachedict['rbin_edit_params'] = None
    #
    return pcache.cachedict


if __name__ == '__main__':
    if len(sys.argv)==1 or ("--help" in sys.argv) or ("-h" in sys.argv):
        print(__doc__)
        sys.exit()

    cachedict = get_params(sys.argv[1])

    hdg_inst_msgs = guess_hdg_inst_msgs(os.path.join(cachedict.cruisedir,'rbin'))
    config=Bunch( dict(hdg_inst_msgs = hdg_inst_msgs))

    _log.info('making gbin directory %s' % (cachedict.gbin))
    G=Gbinner(
    cruisedir=         cachedict.cruisedir,
    gbin=              cachedict.gbin,
    timeinst=          cachedict.time_inst,
    msg=               cachedict.time_msg,
    method=            cachedict.method,
    sonar=Sonar(       cachedict.sonar),
    config =           config,
    rbin_edit_params = cachedict.rbin_edit_params,
    )
    _log.info('getting time offsets')
    G.make_time_calib(update=True)
    _log.info('gridding headings')
    G.make_gridded_headings()


    _log.info('use "plot_hbins.py %s" for a quick look' % (cachedict.gbin))

#!/usr/bin/env python3
'''
apply a depth,scalefactor profile to a database


usage:

multiply_by_scalefactor.py dbpath amp_refbin_file

(This is a work in progress)

'''



import os
import sys
from pycurrents.adcp.qplot import qpc
from pycurrents.num import interp1
import pycurrents.system.pathops as pathops
import numpy as np
from pycurrents.codas import DB
import matplotlib.pyplot as plt
import subprocess
from optparse import OptionParser



def usage():
    print(__doc__)
    sys.exit()

def apply_amp_depth(db, z1, amp1, bpbp=None):
    u = db.get_variable('U', r = bpbp)
    v = db.get_variable('V', r = bpbp)
    depth = db.get_variable('DEPTH', r = bpbp)

    amp = interp1(z1, amp1, depth).reshape(depth.shape)
    ampones = np.ma.ones(depth.shape)
    ampmask = np.ma.getmaskarray(amp)
    amp[ampmask] = ampones[ampmask]

    db.put_array('U', (amp * u), r=bpbp)
    db.put_array('V', (amp * v), r=bpbp)


def get_block_numprofs(dbpath):
    '''
    return a list of tuples: (blocknumber, number of profiles)
    '''
    parts = dbpath.split(os.path.sep)
    loadparts = parts[:-2]
    loadparts.append('load')
    load_dir = os.path.sep.join(loadparts)
    #
    filelist=pathops.make_filelist(os.path.join(load_dir, '*cmd'))
    block_numprof = []
    for f in filelist:
        block = int(os.path.splitext(f)[0][-3:]) - 1 # blocks are 0-based
        cmd = 'grep new_profile %s | wc' % (f)
        status, output = subprocess.getstatusoutput(cmd)
        numprofiles = int(output.split()[0])
        block_numprof.append((block, numprofiles))
    #
    return block_numprof


def make_bpbp_tups(blk_numprofs):
    bptups = []
    for block, numprofiles in blk_numprofs:
        b0=block
        b1=block
        p0=0
        p1=numprofiles-1
        bptups.append(   ((b0,p0), (b1,p1))   )
    return bptups


def make_bpbp_tups_from_db(db):
    # get block,profile tuples from the database
    data=db.get_profiles()
    blk, prf = data.blkprf[:,0], data.blkprf[:,1]
    inewblock = np.where(np.diff(prf)<0)[0]
    iblkstarts=np.empty(len(inewblock)+1, dtype=int)
    iblkstarts[0]=0
    iblkstarts[1:]=inewblock+1
    iblkstops=np.empty(len(inewblock)+1, dtype=int)
    iblkstops[:-1] = iblkstarts[1:]-1
    iblkstops[-1]=len(prf)-1

    bptups = []
    for i0, i1 in zip(iblkstarts, iblkstops):
        p0=prf[i0]
        p1=prf[i1]
        b0=blk[i0]
        b1=blk[i1]
        bptups.append(   ((b0,p0), (b1,p1))   )
    return bptups


if __name__ == '__main__':

    parser = OptionParser(__doc__)

#    dbpath = '../os75bb.uvship.ampref/adcpdb/aship'
#    amp_refbin_fname = 'os75bb_n2_edited.ampz'
    plot_after=True

    (options, args) = parser.parse_args()
    if len(args) != 2:
        usage()
    dbpath = args[0]
    amp_refbin_fname = args[1]

    if not os.path.exists(dbpath + 'dir.blk'):
        print('dbpath %s is not valid' % (dbpath))
        sys.exit()
    db = DB(dbpath, read_only=False)
    u_orig = db.get_variable('U')
    v_orig = db.get_variable('V')

    try:
        # read the 2-column depth,amp file
        z1, amp1 =  np.loadtxt(amp_refbin_fname, unpack=True)
    except:
        print('failed to read 2-column depth,amlitude file (%s)' % (
            amp_refbin_fname))

    # end of lame checking
    #----
    # first determine whether we can do this in one fell swoop
    w = db.get_variable('W')
    try:
        db.put_array('W', (amp1 * w))
        one_chunk = True
        print('applying amplitude correction in one pass')
    except:
        one_chunk = False
        print('cannot write to this database in one pass')

    if one_chunk:
        apply_amp_depth(db, z1, amp1)
    else:
#        blk_numprofs = get_block_numprofs(dbpath)
#        bpbp_tups = make_bpbp_tups(blk_numprofs)
#        # replace the need for 'cmd' files; use db instead
        bpbp_tups = make_bpbp_tups_from_db(db)

        for bpbp in bpbp_tups:
            print(bpbp)
            apply_amp_depth(db, z1, amp1, bpbp=bpbp)

    if plot_after:
        u_new = db.get_variable('U')
        v_new = db.get_variable('V')
        txy = db.get_profiles(txy_only=True)

        fig, ax = plt.subplots(ncols=3)
        ax[0].plot(amp1, z1)
        ax[0].invert_yaxis()
        qpc(u_new - u_orig, profs=txy.dday, clim=(-0.1,0.1), ax=ax[1])
        qpc(v_new - v_orig, profs=txy.dday, clim=(-0.1,0.1), ax=ax[2])
        ax[1].set_title('measured velocity diff:  u*amp - u')
        ax[2].set_title('measured velocity diff:  v*amp - v')

        plt.show()




#
# [jules@manamana load]$ for file in `\ls *cmd`
# > do
# > echo -n $file"   "
# > grep new_profile $file | wc
# > done
# ens_blk001.cmd        300    2100   15452
# ens_blk002.cmd        300    2100   15600
# ###

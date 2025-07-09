#!/usr/bin/env python

import time
import os
import sys
import string

import matplotlib.pyplot as plt
import numpy as np
import argparse
from pycurrents.num import binstats
from pycurrents.system.misc import Bunch
import subprocess
from pycurrents.num import interp1           # interpolation
from pycurrents.num import Runstats               # running statistics
from pycurrents.plot.mpltools import savepngs
from pycurrents.adcp.uhdasfile import guess_dbname
from pycurrents.codas import get_profiles

unrotate_str = '''
           DB_NAME:       ../../adcpdb/${dbname}
           LOG_FILE:      rotate.log
           TIME_RANGE:    all

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          ${year}
                unrotate!
                amplitude=          1.0
                angle_0=            0.0
                end
              end

'''


rotate_str = '''
           DB_NAME:       ../../adcpdb/${dbname}
           LOG_FILE:      rotate.log
           TIME_RANGE:    all

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          ${year}
                time_angle_file:    ${hcorrfile}
                amplitude=          1
                angle_0=            0.0
                end
              end

'''


def write_rot_cmdfiles(dbname, year, hcorrfile):
    unrotfile = 'btwt_unrotate.tmp'
    rotfile = 'btwt_rotate.tmp'

    s=string.Template(unrotate_str)
    ss=s.substitute(dbname=dbname, year=year)
    with open(os.path.join('rotate',unrotfile),'w') as file:
        file.write(ss)

    s=string.Template(rotate_str)
    ss=s.substitute(dbname=dbname, year=year, hcorrfile=hcorrfile)
    with open(os.path.join('rotate', rotfile),'w') as file:
        file.write(ss)

    return unrotfile, rotfile # without path


def read_cals(wtcalfile, btcalfile):
    caldict = dict()
    caldict[wtcalfile] = '  0'
    caldict[btcalfile] = '  1'

    all_lines = []
    for fname in (wtcalfile, btcalfile):
        calval = caldict[fname]
        with open(fname, 'r') as newreadf:
            lines = newreadf.readlines()
        for line in lines:
            if 'nan' not in line:
                newstr = line.rstrip()
                newstr += calval
                all_lines.append(newstr)
    return all_lines

def write_allcals(outfile, all_lines):
    # write it out
    with open(outfile, 'w') as file:
        file.write('\n'.join(all_lines))


def read_allcals(calfile):
    txyv=np.loadtxt(calfile, comments='#')
    igood = ~np.isnan(np.sum(txyv, axis=1))
    isorted = np.argsort(txyv[igood,0])
    txyv_sorted = txyv[isorted,:]
    return txyv_sorted

def plot_phase(txyv):

    dday = txyv[:,0]
    ph = txyv[:,2]
    is_bt = txyv[:,3]


    f, ax = plt.subplots()
    ax.plot(dday[is_bt==0], ph[is_bt==0], 'c.', ms=6)
    ax.plot(dday[is_bt==1], ph[is_bt==1], 'k.', ms=1)
    ax.plot(dday[is_bt==0], ph[is_bt==0], 'co', ms=4,
            mfc='none', mec='c')

    ax.set_xlabel('decimal day')
    ax.set_ylabel('degrees')
    f.text(0.5,.95,'combined watertrack and bottom track', ha='center')

    return f, ax

def try_ginput(ax):

    xy = ax.ginput(35, show_clicks=True)
    axa = np.array(xy)
    x = axa[:,0]
    y = axa[:,1]

    ax.plot(x,y,'ro-')

    return axa


def write_binstats(txyv, btparams=None, wtparams=None, outfile='calfit.txt', scheme='coarse'):
    '''
    write binstats estimates (for future editing)
    returns binstats medians: dday, phase
    '''
    dday = txyv[:,0]
    ph = txyv[:,2]
    is_bt = txyv[:,3]

    # move this out
    if scheme == 'coarse':
        btp=Bunch()
        btp.step=0.25 # search in 0.25 day chunks
        btp.stdmin=2  # allow only binstd < stdmin
        btp.nummin=20 # allow only binn > nummin

        wtp=Bunch()
        wtp.step=2 # search in 2-day counts
        wtp.stdmin=5  # allow only binstd < stdmin
        wtp.nummin=2 # allow only binn > nummin
    else:
        btp=Bunch()
        btp.step=0.05 # search in 0.25 day chunks
        btp.stdmin=2  # allow only binstd < stdmin
        btp.nummin=5 # allow only binn > nummin

        wtp=Bunch()
        wtp.step=1 # search in 2-day counts
        wtp.stdmin=5  # allow only binstd < stdmin
        wtp.nummin=2 # allow only binn > nummin


    if btparams:
        btp.update_values(btparams)
    if wtparams:
        wtp.update_values(wtparams)

    # finer grain
    segends = np.arange(dday[0], dday[-1]+btp.step, btp.step)
    bt_binpt, bt_binmed, bt_binstd, bt_binnum=binstats(dday[is_bt==1], ph[is_bt==1],
                                       segends=segends, avgtype='median')
    okbt = (bt_binstd < btp.stdmin) & (bt_binnum > btp.nummin) & ~np.isnan(bt_binnum)

    # coarser grain
    segends = np.arange(dday[0], dday[-1]+wtp.step, wtp.step)
    wt_binpt, wt_binmed, wt_binstd, wt_binnum=binstats(dday[is_bt==0], ph[is_bt==0],
                                       segends=segends, avgtype='median')
    okwt = (wt_binstd < wtp.stdmin) & (wt_binnum > wtp.nummin) & ~np.isnan(wt_binnum)

    binpt = np.concatenate( (bt_binpt[okbt], wt_binpt[okwt]))
    binmed = np.concatenate( (bt_binmed[okbt], wt_binmed[okwt]))
    index=np.argsort(binpt)

    lines=[]
    lines.append('# points estimated from watertrack and bottom track cals')
    lines.append('#decimal day        phase')
    # fill in and write out the file with the binstats points
    for ii in index:
        lines.append('%15.7f   %5.2f' % (binpt[ii], binmed[ii]))
    with open(outfile,'w') as file:
        file.write('\n'.join(lines))

    return binpt[index], binmed[index]


def write_raw(txyv, outfile='calfit.txt'):
    '''
    write binstats estimates (for future editing)
    returns binstats medians: dday, phase
    '''
    dday = txyv[:,0]
    ph = txyv[:,2]

    index=np.argsort(dday)

    lines=[]
    lines.append('# points estimated from watertrack and bottom track cals')
    lines.append('#decimal day        phase')
    # fill in and write out the file with the binstats points
    for ii in index:
        lines.append('%15.7f   %5.2f' % (dday[ii], ph[ii]))
    with open(outfile,'w') as file:
        file.write('\n'.join(lines))

    return dday[index], ph[index]





if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="combine bottom track and watertrack to make one timeseries")


    parser.add_argument('--rawfile',
                         default='allcals.txt',
         help='filename for combined WT and BT data (default=allcals.txt)')

    parser.add_argument('--fitfile',
                         default='calfit.txt',
        help='filename for fitted line of WT+BT (default=calfit.txt)')

    parser.add_argument('--outfile',
                        default='calfit_edited.txt',
                        help='filename for edited points (default=calfit_edited)')

    parser.add_argument('--scheme',
                        default='coarse',
                        help='fixed list of choices for subsampling (default=coarse)')


    parser.add_argument('--trim',
                        default=None,
    help='last index for writing fitted points (overrides internal calculation')

    options = parser.parse_args()

    if options.scheme not in ('coarse', 'fine', 'raw'):
        print("ERROR: must specify 'scheme' as 'coarse', 'fine', or 'raw'")
        sys.exit()



    if '--help' in sys.argv:
        print("rerun quick_adcp.py with '--steps2rerun calib'; then run this from 'cal' directory")
        sys.exit()

    wtcalfile = 'watertrk/wtcal_edited.txt'      # generate and read
    btcalfile = 'botmtrk/btcal_edited.txt'       # generate and read
    rawfile = options.rawfile
    fitfile = options.fitfile                    # after binstats
    fit_edited = options.outfile                 # after PolygonInteractor

    dbpath = guess_dbname('../adcpdb')
    profs = get_profiles(dbpath, ddrange=0.1)
    year = profs.yearbase


    dbname = os.path.split(dbpath)[-1]  # stripping the path
    Tfile = '../edit/%s.tem' % (dbname)          # temperature file (for all ddays)
    final_angfile = 'ens_cal_fit.ang'            # use this with rotate.tmp

    for outfile in (rawfile, fitfile, fit_edited, final_angfile):
        if os.path.exists(outfile):
            print('ERROR: file %s exists.' % (outfile))
            print('Delete %s and try again' % (outfile))
            sys.exit(1)


    all_lines = read_cals(wtcalfile, btcalfile)
    write_allcals(rawfile, all_lines)
    txyv = read_allcals(rawfile)


    # plot and run binstats
    if options.scheme == 'coarse':
        fits = write_binstats(txyv, outfile=fitfile)
    elif options.scheme == 'fine':
        fits = write_binstats(txyv, outfile=fitfile, scheme='fine')
    elif options.scheme == 'raw':
        fits = write_raw(txyv, outfile=fitfile)


    f,ax=plot_phase(txyv)
    ax.plot(fits[0], fits[1], 'bo')
    ax.plot(fits[0], fits[1], 'm')

    pstr = '''

    Key-bindings

      't' toggle vertex markers on and off.  When vertex markers are on,
          you can move them, delete them

      'd' delete the vertex under point

      'i' insert a vertex at point.  You must be within epsilon of the
          line connecting two existing vertices

    '''
    print(pstr)
    print('- delete, move, or insert dots to improve the line\n')
    print('- final data will be output to %s' % (fitfile))
    print('- close window to write+quit\n')

    # load the binstats, manually edit
    cmd = 'btwt_editor.py --rawfile %s --fitfile %s --outfile %s --scheme %s' % (
                    rawfile, fitfile, fit_edited, options.scheme)
    print('about to run:\n %s' % (cmd))
    # now edit the points
    output = subprocess.getoutput(cmd)   # TODO -- get stdout to the screen
    print(output)

    time.sleep(1)

    cal_ed_fit = np.loadtxt(fit_edited, comments='#')
    # should already be monotonically nondecreasing but might have duplicates
    moni = np.where(np.diff(cal_ed_fit[:,0])>0)[0] # monotonic index
    calmon = cal_ed_fit[moni,:]                 # monotonic calibration times

    Tdat = np.loadtxt(Tfile, comments='%')
    ensdday = Tdat[:,0]

    padded_dday = np.zeros(len(calmon)+2)
    padded_ph = np.zeros(len(calmon)+2)

    padded_dday[0] = ensdday[0]    #first dday
    padded_dday[-1] = ensdday[-1]  #last dday
    padded_dday[1:-1] = calmon[:,0]

    padded_ph[0] = calmon[:,1][0]    #first ph
    padded_ph[-1] = calmon[:,1][-1]    #last ph
    padded_ph[1:-1]=calmon[:,1]


    medph = interp1(padded_dday, padded_ph, ensdday)
    if options.scheme == 'raw':
        medphsm = medph
    else:
        medphsm = Runstats(medph,51).mean #arbitrary; several hours

    lines= []
    for xy in zip(ensdday, medphsm):
        lines.append('%10.7f    %5.3f' % (xy[0], xy[1]))
    lines.append('')
    outfile = os.path.join('rotate',final_angfile)
    with open(outfile,'w') as file:
        file.write('\n'.join(lines))
    print('saved final interpolated angle file to %s' % (outfile))

    ax.plot(ensdday, medph, 'g.', ms=1)
    ax.plot(ensdday, medphsm, 'b.', ms=1)
    plt.show()
    outfile = os.path.join('rotate', final_angfile)
    savepngs(outfile, 90, f)
    print('saved figure to %s' % (outfile+'.png'))


    ## now make it useful
    unrot, rot = write_rot_cmdfiles(dbname, year, final_angfile)
    print('wrote 2 control files to "rotate" directory.')
    print('now do this:')
    print('\n\t cd rotate')
    print('\t rotate %s' % (unrot))
    print('\t rotate %s' % (rot))
    print('\t cd ../../')
    print('\t quick_adcp.py --steps2rerun navsteps:calib --auto')

#============================================

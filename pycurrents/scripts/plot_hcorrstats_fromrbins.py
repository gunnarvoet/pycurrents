#!/usr/bin/env python
# get statistics from attitude data; make plots
'''
This program calculates the difference in heading between reliable and accurate heading devices
- gridding is done a position device; eg. could be the 'gps' message from accurate heading
- optional: specify a decimal day range (relative to start or end, or actual dday rarnge)
- data flavors:
    - original rbins: plot (relative-accurate) headings (--plotdh)
    - 5min averages: mimic what CODAS does within the 5min averages
         - print the quality statistics of raw and ensemble averages (--printstats)
         - plot the raw and averaged heading correction (--plot_enshcorr)
         - write out a file like enshcorr.asc, enshcorr.ang (--print_enshcorr)
- output:
    - plots can be viewed, or not viewed, and optionally saved to a png file
    - statistics can be printed to a file or stdout
    - enshcorr.asc, enshcorr.ang must go to a file
- optional:
   - posmv heading accuracy cutoff (default is 0.02)
   - maximum gap over which to interpolate (default = 5sec)
   - ensemble length(seconds)

Examples:

plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --printstats
plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --plotdh --outfilebase km2014_hcorr
plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --plot_enshcorr
plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --print_enshcorr --outfilebase km2014_enshcorr
       plot_enshcorr.py --infile  km2014_enshcorr.asc  # to plot the file


'''

import numpy as np
import sys
import os
from optparse import OptionParser
import logging
import glob

if ('--noshow' in sys.argv):
    import matplotlib
    matplotlib.use('Agg')
else:
    import matplotlib
    import matplotlib.pyplot as plt



from pycurrents.adcp.attitude import Hcorr
from pycurrents.system.misc import Bunch
from pycurrents.adcp.uhdasfileparts import FileParts
from pycurrents.plot.mpltools import savepngs


## TODO
## - print (or plot) heading accuracy
## - max_dx isn't working (or needs a better test dataset)
## add the ability to create enshcorr.asc from the timestamps of another file

####### get options

# Standard logging
_log = logging.getLogger(__file__)

if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()

if '--help' in sys.argv:
    print(__doc__)


parser = OptionParser()

## specify instruments
parser.add_option("-r", "--reliable", dest="reliable",
                  default=None,
                  help="inst1:msg1 reliable heading device and message, eg. 'gyro:hdg'")

parser.add_option("-a", "--accurate", dest="accurate",
                  default=None,
                  help="inst2:msg2 accurate heading device and message, eg. 'posmv:pmv'")

parser.add_option("-p", "--position", dest="position",
                  default=None,
                  help="inst3:msg3 position instrument (headings are gridded onto these timestamps).  \nIf unspecified, try and use accurate device for positions")

# details about the extraction
parser.add_option("-s", "--step", dest="step",
                  default = 1, type=int,
                  help="subsample by STEP (default=1) : only works for --plothcorr")

parser.add_option("--ddrange", dest='ddrange', default=None,
                help='colon-delimited decimal day range (default gets all)')

parser.add_option("--cutoff", dest="cutoff",
                  default = 0.02,
           help="cutoff to accept heading accuracy (exceeds is bad). default=0.02")

parser.add_option("-y", "--yearbase", dest="yearbase",
                  default = None,
                  type = int,
                  help="add UTC timestamps to txy plot (requires yearbase)")

# specify output:
## rbin raw values
parser.add_option("--plotdh", dest="plotdh", action="store_true",
                  default=False, help="make the rbin heading difference plot")
## includes averages
parser.add_option("--nwin", dest="nwin",
                  default = 301, type=int,
                  help="averaging length (odd integer, default = 301).  Based on position sampling rate")

parser.add_option("--printstats", dest="printstats", action="store_true",
                  default=False, help="DO print out statistics.  If --printstats and --outfilebase, print to file")

parser.add_option("--print_enshcorr", action="store_true", dest="print_enshcorr",
                  default=False, help="print ___.ang and ___.asc files ")

parser.add_option("--plot_enshcorr", action="store_true", dest="plot_enshcorr",
                  default=False, help="plot enshcorr details. otherwise use plot_enshcorr.py outfilebase.asc ")

## graphics and saving
parser.add_option("--noshow", dest="show", action="store_false",
                  default=True,
                  help="do not display figure")

parser.add_option("-o", "--outfilebase", dest="outfilebase",
                  default=None, help="Save to this filename (outfilebase.png)")

parser.add_option("-u", "--uhdas_dir", dest="uhdas_dir",
                  default = None,
                  help="uhdas_directory with rbin files containing reliable and accurate heading instruments")

## lesser used
parser.add_option("--splitchar", dest='splitchar', default=':',
                help="specify different splitter. Ex.: "
                     "use  --splitchar ','  and --reliable inst,msg ")

parser.add_option("--markersize", dest="marker_size", default=2,
                type=int, help="Marker size. default is 2; max. is 6")

parser.add_option("--max_dx", dest="max_dx_sec", default=0, type=float,
                  help="maximum gap IN SECONDS for interpolation")

parser.add_option("--bigger_font", dest='bigger_font',  action="store_true",
                default=False, help="use a larger font when plotting ")



(options, args) = parser.parse_args()

###

if (options.plotdh or options.plot_enshcorr) and not (options.show or options.outfilebase):
    _log.error('plotting: either specify --outfilebase or do not use --noshow')
    sys.exit()

if not (options.plotdh or options.printstats or options.print_enshcorr or options.plot_enshcorr):
    _log.error('no action: select at least one of: --printstats, --plotdh, --print_enshcorr, or --plot_enshcorr')
    sys.exit()

if options.bigger_font:
    # make the fonts bigger
    font = {'weight' : 'bold',
            'size'   : 14}
    matplotlib.rc('font', **font)

for opt in (options.reliable, options.accurate):
    if options.splitchar not in opt:
        _log.error('illegal entry (%s) -- must set instrument and message in colon-delimited option' % (opt))
        sys.exit()

if (not options.accurate) or (not options.reliable):
    _log.error('must choose two heading devices (accurate and reliable)')
    sys.exit(1)

if options.position:
    if options.splitchar not in options.position:
        _log.error('illegal entry (%s) -- must set instrument and message in colon-delimited option' % (opt))
        sys.exit()

if not os.path.exists(options.uhdas_dir):
    _log.error('must specify uhdas directory with --uhdas_dir')
    sys.exit()

cruisename = os.path.basename(os.path.realpath(options.uhdas_dir))

reliable_filelist=[]
accurate_filelist=[]
try:
    rel_inst, rel_msg = options.reliable.split(options.splitchar)
    acc_inst, acc_msg = options.accurate.split(options.splitchar)
    if options.position:
        pos_inst, pos_msg = options.position.split(options.splitchar)
    else:
        pos_inst = acc_inst
        pos_msg = 'gps'

    rel_globstr = os.path.join(options.uhdas_dir, 'rbin', rel_inst , '*.%s.rbin' % (rel_msg))
    reliable_filelist=glob.glob(rel_globstr)

    acc_globstr = os.path.join(options.uhdas_dir, 'rbin', acc_inst , '*.%s.rbin' % (acc_msg))
    accurate_filelist=glob.glob(acc_globstr)

    pos_globstr = os.path.join(options.uhdas_dir, 'rbin', pos_inst , '*.%s.rbin' % (pos_msg))
    position_filelist=glob.glob(pos_globstr)

    if len(reliable_filelist) == 0:
        _log.error('no files found for %s' % (rel_globstr))
        sys.exit()
    if len(accurate_filelist) == 0:
        _log.error('no files found for %s' % (acc_globstr))
        sys.exit()
    if len(position_filelist) == 0:
        _log.error('no files found for %s' % (pos_globstr))
        sys.exit()

    if not options.yearbase:
        yearbase = FileParts(position_filelist[-1]).year

except Exception as e:
    _log.error(e)
    sys.exit()


if options.print_enshcorr and (not options.outfilebase):
    _log.error('You selected --print_enshcorr: must also select --outfilebase')
    sys.exit()

if options.outfilebase:
    outfilebase=options.outfilebase
    statfile = '%s_stats.txt'   % (outfilebase)
    hcorr_pngfile =  '%s_hcorr.png'       % (outfilebase)
    enshcorr_pngfile =  '%s_enshcorr.png'       % (outfilebase)


range_ = None
if options.ddrange:
    startdd, enddd = options.ddrange.split(options.splitchar)
    if not startdd and not enddd:
        _log.error('must pick at least a startdd or enddd')
        sys.exit()
    if startdd == '':
        range_ = float(enddd)
    elif enddd == '':
        range_ = float(startdd)
    else:
        range_ = (float(startdd), float(enddd))
else:
    range_='all'

if np.remainder(options.nwin, 2) == 0:
    _log.error('--nwin must be an odd integer')
    sys.exit()

max_dx_dday = options.max_dx_sec/86400.


uhdas_cfg = Bunch()  # to replicate a UhdasConfig instance
uhdas_cfg.gbin_params = Bunch()
uhdas_cfg.gbin_params['hdg_inst']  = rel_inst
uhdas_cfg.gbin_params['hdg_msg']  = rel_msg
uhdas_cfg.hcorr = [acc_inst, acc_msg]
uhdas_cfg.gbin_params['pos_inst']  = pos_inst
uhdas_cfg.gbin_params['pos_msg']  = pos_msg
uhdas_cfg.rbin = os.path.join(options.uhdas_dir, 'rbin')
uhdas_cfg.cruisename = os.path.basename(os.path.realpath(options.uhdas_dir))
uhdas_cfg.yearbase = yearbase
cruisename = uhdas_cfg.cruisename


qc_kw = {}
qc_kw['acc_heading_cutoff'] = float(options.cutoff)

#for name in ('maxrms', 'maxbms',
#             'acc_heading_cutoff',
#             'acc_roll_cutoff',
#             'gams_cutoff'):
#    kk =  list(cid.keys())
#    if name in kk:
#        qc_kw[name] = cid[name]


for kw in uhdas_cfg.keys():
    print('uhdas_cfg', kw, uhdas_cfg[kw])


#--------------

## always get the rbins and grid
titlestring = "%s: (%s-%s) statistics" % (cruisename, rel_inst, acc_inst)
cname='u_dday'

HH = Hcorr(uhdas_cfg=uhdas_cfg,  hcorr_inst=acc_inst)
msg = HH.get_rbins(cname=cname, range_=range_, step=options.step,
                    qc_kw=qc_kw)
if len(msg) > 0:
    print(msg)
    raise IOError(msg)

HH.grid_att(max_dx = max_dx_dday)

if options.printstats or options.print_enshcorr or options.plot_enshcorr:
    HH.hcorr_stats(nwin=options.nwin)


#######################################################
## (1) plot figure

if options.plotdh:
    _log.info('about to plot figure for heading diffs: %s-%s\n', (acc_inst, rel_inst))

    try:
        HH.plot_hcorr(titlestring=titlestring + ' (no averaging)')
        if options.show:
            plt.show()

        if options.outfilebase:
            savepngs(hcorr_pngfile, fig=HH.hcorr_fig,  dpi=90)
    except:
        _log.exception('could not make heading correction plot')


#######################################################

#if options.step is not 1, re-extract the data with step=1
if (options.printstats or options.print_enshcorr or options.plot_enshcorr) and options.step != 1:
    msg = HH.get_rbins(cname=cname, range_=range_, step=1, qc_kw=qc_kw)
    if len(msg) > 0:
        print(msg)
        raise IOError(msg)
    HH.grid_att(max_dx = max_dx_dday)
    HH.hcorr_stats(nwin=options.nwin)
_log.info('re-extracting the rbins with step=1')

#######################################################
## (2) print statistics (as if for daily_report)

if options.printstats:

    _log.info('about to print stats for %s\n', acc_inst)

    try:
        if len(HH.dh) == 0:
            slist = ['no %s data\n' % (acc_inst,)]
        elif HH.ensnumgood == 0:
            slist = ['no good %s data out of %d (%dsec) ensembles\n' % (
                    acc_inst,  HH.ensnumtotal,
                    np.round(options.nwin))]
        else:
            slist = HH.print_stats_summary()
            slist.append('')

        ## print
        outstr = '\n'.join(slist)
        if options.outfilebase:
            with open(statfile,'w') as file:
                file.write(outstr)
        else:
            print(outstr)

    except:
        _log.exception('could not get %s stats\n' % (acc_inst,))


#######################################################
## (3) print ___.ang and ___.asc

if options.print_enshcorr:
    _log.info('about to print hcorr for %s\n', acc_inst)

    try:
        HH.print_enshcorr(options.outfilebase, overwrite=True)
        HH.plot_enshcorr(titlestring=titlestring + ' (+enshcorr averages)')
    except Exception as e:
        _log.exception(f'could not print {options.outfilebase}.asc, {options.outfilebase}.ang\nError: {e}')

#######################################################
## (3) detailed plot of enshcorr

if options.plot_enshcorr:
    _log.info('about to plot enshcorr for %s\n', acc_inst)
    try:
        HH.plot_enshcorr(titlestring=titlestring)
        if options.show:
            plt.show()

        if options.outfilebase:
            savepngs(enshcorr_pngfile, fig=HH.enshcorr_fig,  dpi=90)
        else:
            plt.show()

    except Exception as e:
        _log.exception(f'could not print {options.outfilebase}.asc, {options.outfilebase}.ang\nError: {e}')

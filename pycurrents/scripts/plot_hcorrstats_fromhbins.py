#!/usr/bin/env python
'''
This program is really a way to test HbinDiagnostics, which is used
at sea via run_hbinhcorrstats.py print statistics and make QC plots
of the heading devices.

HbinDiagnostics calculates the difference in heading between reliable and
accurate heading devices:
- gridding was already done using the primary position instrument (creating hbins)
- optional: specify a decimal day range (relative to start or end, or actual dday range)
  Selecting ddrange:
     --ddrange :-2                         # last 2 days
     --ddrange 3:                          # first 3 days
     --ddrange 355:357                     # dday 355-357

Must specify whether to
   - make the plot [and whether to show the plot or not] (--plotdh)
   - print statistics [to screen, or to a file]   (--printstats)

Examples:

plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --printstats
plot_hcorrstats_fromrbins.py -a posmv:pmv -r gyro:hdg -u km2014 --plotdh --cutoff 0.013 --printstats

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



from pycurrents.adcp.hbin_diagnostics import HbinDiagnostics
from pycurrents.plot.mpltools import savepngs

# Standard logging
_log = logging.getLogger(__file__)


####### get options



usage = '\n'.join(["usage: %prog --accurate inst:msg --reliable inst:msg [--position inst:msg]  [--cutoff 0.02] --printstats --plotdh [--noshow] [--outfilebase hcorrplot] --uhdas_dir km2014 ",
     "   eg.",
     "       %prog --accurate posmv:pmv --reliable gyro:hdg --plotdh --uhdas_dir km2014"])


if len(sys.argv) == 1:
    print(__doc__)
    sys.exit()

if '--help' in sys.argv:
    print(__doc__)


parser = OptionParser()

parser.add_option("-r", "--reliable", dest="reliable",
                  default=None,
                  help="inst1:msg1 reliable heading device and message, eg. 'gyro_hdg'")

parser.add_option("-a", "--accurate", dest="accurate",
                  default=None,
                  help="inst2:msg2 accurate heading device and message, eg. 'posmv:pmv'")

parser.add_option("-s", "--step", dest="step",
                  default = 30,
                  help="subsample by STEP (default=30)")

parser.add_option("--ddrange", dest='ddrange', default=None,
                help='colon-delimited decimal day range (default gets all)')

parser.add_option("-y", "--yearbase", dest="yearbase",
                  default = None,
                  type = int,
                  help="add UTC timestamps to txy plot (requires yearbase)")

parser.add_option( "--cutoff", dest="cutoff",
                  default = 0.02,
                  type = float,
                 help="acc_heading_cutoff for posmv; used in raw statistics")

parser.add_option("--printstats", dest="printstats", action="store_true",
                  default=False, help="DO print out statistics.  If --printstats and --outfilebase, print to file")

parser.add_option("--plotdh", dest="plotdh", action="store_true",
                  default=False, help="DO make the plot")

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

parser.add_option("--max_dx", dest="max_dx", default=0, type=float,
                  help="maximum gap for interpolation")

parser.add_option("--bigger_font", dest='bigger_font',  action="store_true",
                default=False, help="use a larger font when plotting ")

(options, args) = parser.parse_args()

###


if (not options.show) and options.outfile is None:
    _log.error('not showing figure; must select an output file')

if (not options.plotdh) and (not options.printstats):
    _log.error('no action: select --printstats or --plotdh or both')

if options.bigger_font:
    # make the fonts bigger
    font = {'weight' : 'bold',
            'size'   : 14}
    matplotlib.rc('font', **font)


if options.splitchar not in options.accurate:
    _log.error('illegal entry (%s) -- must set instrument and message in colon-delimited option' % (
    options.accurate))

if not options.yearbase:
    _log.error('must set yearbase')


if not os.path.exists(options.uhdas_dir):
    _log.error('must specify uhdas directory with --uhdas_dir')
cruisename = os.path.basename(os.path.realpath(options.uhdas_dir))



###
gbindir=os.path.join(options.uhdas_dir, 'gbin')
hbin_filelist=[]
try:
    hbin_globstr = os.path.join(options.uhdas_dir, 'gbin', 'heading', '*.hbin')
    hbin_filelist=glob.glob(hbin_globstr)
    if len(hbin_filelist) == 0:
        _log.error('no files found for %s' % (hbin_globstr))
except Exception as e:
    _log.error(e)



if options.outfilebase:
    outfilebase=options.outfilebase
    statsfile = '%s_stats.txt'   % (outfilebase)
    pngfile =  '%s.png'       % (outfilebase)


range_ = -1
if options.ddrange:
    startdd, enddd = options.ddrange.split(options.splitchar)
    if not startdd and not enddd:
        _log.error('must pick at least a startdd or enddd')
    if startdd == '':
        range_ = float(enddd)
    elif enddd == '':
        range_ = float(startdd)
    else:
        range_ = (float(startdd), float(enddd))
else:
    range_=None


stats_winsecs = 300.

rel_inst, rel_msg = options.reliable.split(options.splitchar)
rel_inst_msg = '_'.join([rel_inst, rel_msg])
acc_inst, acc_msg = options.accurate.split(options.splitchar)
acc_inst_msg = '_'.join([acc_inst, acc_msg])

H=HbinDiagnostics(gbin=gbindir, yearbase=int(options.yearbase))
winsecs=300 #statistics window
H.get_segment(range_)

#######################################################
## (1) plot figure

if options.plotdh:
    _log.info('about to plot figure for %s\n', acc_inst)

        # used to plot the file the statistics were made from;
        # now plot 4 hrs of raw
    try:
        titlestring = "%s: (%s-%s) statistics" % (cruisename, rel_inst, acc_inst)
        H.get_hcorr(rel_inst_msg, acc_inst_msg, options.cutoff)
        H.plot_hcorr(titlestring=titlestring)

        if options.show:
            plt.show()

        if options.outfilebase:
            savepngs(pngfile, 90)

    except:

        _log.exception('could not make heading correction plot')


#######################################################
## (2) print statistics (for daily_report)

if options.printstats:
    _log.info('about to print stats for %s\n', acc_inst)

    try:

        H.get_hcorr(rel_inst_msg, acc_inst_msg, options.cutoff)
        H.hcorr_stats(winsecs=winsecs)

        if len(H.dh) == 0:
            slist = ['no %s data\n' % (acc_inst,)]
        elif H.ensnumgood == 0:
            slist = ['no good %s data out of %d (%dsec) ensembles\n' % (
                    acc_inst,  H.ensnumtotal,
                    np.round(winsecs))]
        else:

            H.get_rbin_stats() # find ptsPG before assembling slist
            slist = H.print_stats_summary()
            slist.append('')

        #print
        outstr = '\n'.join(slist)
        if options.outfilebase:
            with open(statsfile,'w') as file:
                file.write(outstr)
        else:
            print(outstr)

    except:
        _log.exception('could not get %s stats\n' % (acc_inst,))

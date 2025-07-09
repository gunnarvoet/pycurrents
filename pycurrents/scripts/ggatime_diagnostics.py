#!/usr/bin/env python

"""

usage:help:notes  --> pycurrents/scripts


Script for GGA message diagnostics.

**Usage**
      ggatime_diagnostics.py --uhdas_dir path/to/cruise/dir [options]
      ggatime_diagnostics.py [options] *.gps.rbin


**Options**

    *data source options*

    You must do one or the other:

    (1) usage with wildcard "*.gps.rbin" needs no other data source options

    (2) specify source directory:
       --uhdas_dir     path to CRUISE_DIRECTORY (contains raw, rbin, gbin etc)
                       -or- a wildcard list of files (instrument and message are deduced)

    *instrument and message*

    Options when using --uhdas_dir:

    (2a) specify one instrument and message pair (makes one plot)
      --instmsg       choose which instrument and message you want to plot (colon-delimited)
                       example--    gpsnav:gps

    (2b) use a  sensor_cfg.* file
      --sensor_cfg    choose a specific file to use for all gps.rbin files
                       example: /home/adcp/config/sensor_cfg.py  (this is the default)
                       example: /home/data/KM1001c/raw/config/KM1001c_sensor_cfg.py


    *choosing subsets*

    Optional subsetting:

    --startdday     decimal day to start # default is the beginning
    --ndays         number of days to plot #default is to plot all

    *plotting options*

    --zoomname      'auto', 'zoom', 'fixed'  (default), 'all' (does 'auto', 'zoom', and 'fixed')
    --titlestr      for the title  of plots

    *save/view options*

    --save_fig     (save figure to PNG file)
    --save_figT    (save figure and thumbnail to PNG files)
    --save_hist    (save histogram to TXT file)
    --print_hist   (print histogram to stdout)
    --prefix       (use this for the file name)   default uses inst:msg and zoomname
    --outdir       (save to this directory)       default = current directory
    --outdir2      (also save here; if subdir 'thumbnails' exists, save thumbnails there)


NOTE: if startdday is unspecified, positive ndays starts at the beginning and
                                   negative ndays works backward from the end
      if startdday is unspecified and ndays is unspecified, get the whole dataset (default)

**Examples**::

   # only works for an at-sea directory when the cruise is active:
   ggatimes_diagnostics.py --uhdas_dir /home/data/current_cruise --save_fig

   # make one
   ggatimes_diagnostics.py --uhdas_dir lmgould/LMG1804b --instmsg gpsnav:gps  --save_fig --prefix LMG1804b_gps

   ggatimes_diagnostics.py  --zoomname zoom --save_figT

   ggatimes_diagnostics.py  --print_hist  LMG1804b/rbin/gpsnav/*.gps.rbin


"""


import sys
import os

import logging
from optparse import OptionParser
#
if ('--noshow' in sys.argv):
    import matplotlib
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pycurrents.file.binfile_n import BinfileSet
import pycurrents.system.pathops as pathops       # see make_filelist
from pycurrents.system import Bunch
from pycurrents.adcp.plottime_diagnostics import  plot_gga_times, zoom_gga_fig, save_fig, add_UTC_fig
from pycurrents.adcp.plottime_diagnostics import  make_gga_hist, save_hist
from pycurrents.adcp.plottime_diagnostics import  sensor_cfg_dday, find_sensor_cfgs
from pycurrents.adcp.plottime_diagnostics import  metanames_from_sensors
from pycurrents.adcp.uhdas_cfg_api import SensorCfg

# Standard logging
_log = logging.getLogger(__file__)


if __name__ == '__main__':

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit(1)

    if '--help' in sys.argv:
        print(__doc__)

    parser = OptionParser()

    ##  specify the uhdas_dir or use a filelist of *.gps.rbin
    parser.add_option("--uhdas_dir", dest="uhdas_dir",
                      default = '',
                      help="uhdas directory you want to access")

    # if using uhdas_dir then specify the instrument+message OR
    #    guess all using sensor_cfg.py
    parser.add_option("--instmsg", dest="instmsg",
                      default = None,
                      help="choose instrument and message (inst:msg)")

    parser.add_option("--use_sensor_cfg", dest="use_sensor_cfg",
                      action="store_true",
                      default = False,
               help="reads and parse sensor_cfg.* (inst:msg).")

    parser.add_option("--sensor_file", dest="sensor_file",
                      default = None,
                      help="reads and parse this specific sensor_cfg.* file")

    # data extraction
    parser.add_option("--startdday", dest="startdday", default = None,
               help="choose dday to start the plot")

    parser.add_option("--ndays", dest="ndays", default = None, # i.e. all
               help="choose how many days to plot")

    #plotting options
    #  - always make the plot and the histogram
    #  - only save to disk if requested
    #  - maybe not show the plot (for remote work)


    parser.add_option("--yearbase", dest="yearbase",
                      default = None,
                      help="add UTC timestamps to txy plot (requires yearbase)")


    parser.add_option("--titlestr", dest="titlestr",
                      default = None,
               help="figure titles only.")

    parser.add_option("--noshow", dest="noshow", action="store_true",
                      default=False,
                      help="do not display figure")

    parser.add_option("--zoomname", dest="zoomname",
                      default = 'fixed',
                      help="zoom the figure, options: 'auto', 'fixed' (default) 'zoom', or 'all'")

    parser.add_option("--save_hist", dest="save_hist",  action="store_true",
                      default = False,
                      help="save histogram to file")

    parser.add_option("--print_hist", dest="print_hist",  action="store_true",
                      default = False,
                      help="print histogram to stdout")

    parser.add_option("--save_fig", dest="save_fig",  action="store_true",
                      default = False,
                      help="save the figure")

    parser.add_option("--save_figT", dest="save_figT",  action="store_true",
                      default = False,
                      help="save the figure AND a thumbnail")

    parser.add_option("-p", "--prefix", dest="prefix",
                      default = 'ggatime',
                      help="use PREFIX in the filename")

    parser.add_option("-o", "--outdir", dest="outdir",
                      default = './',  help="save figures or text to this directory")

    parser.add_option("--outdir2", dest="outdir2",
                      default = None,  help="also save figures or text to this directory")

    (options, args) = parser.parse_args()

    if options.uhdas_dir and len(args)>0:
        _log.error("ERROR: specify '--uhdas_dir' or a collection of rbin files, not both")


    if options.zoomname == 'all':
        zoomnames = ['auto', 'fixed', 'zoom']
    else:
        zoomnames = [options.zoomname,]

    outdir = options.outdir
    outdir2 = options.outdir2

    if options.save_figT:
        options.save_fig = True

    if len(args) > 0 and len(options.uhdas_dir) > 0:
        _log.error("ERROR: specify '--uhdas_dir' or a collection of rbin files")

    metanames = Bunch()
    if len(args) > 0:
        filelist = args
        instlist = []
        msglist = []
        for fname in filelist:
            pathparts = os.path.realpath(fname).split(os.sep)
            inst = pathparts[-2]
            msg = pathparts[-1].split('.')[-2]
            if inst not in instlist:
                instlist.append(inst)
            if msg not in msglist:
                msglist.append(msg)
        if len(instlist) > 1 or len(msglist) > 1:
            _log.warning('instrument or message from filelist not unique')
            sys.exit(2)
        imtups =  ( (instlist[0],msglist[0]),  )  # extract the one tuple
    else:
        uhdas_dir = options.uhdas_dir
        if options.sensor_file is None:
            sensor_file = find_sensor_cfgs(uhdas_dir)[0]  #maybe multiples
        else:
            sensor_file = options.sensor_file
        metanames = metanames_from_sensors(sensor_file)

        if not os.path.exists(sensor_file):
            _log.warning('could not guess sensor_cfg file')
            sys.exit(2)

        if options.instmsg: # force this to be one tuple
            imtups = tuple(options.instmsg.split(':')),
        else: #
            sensor_list = SensorCfg(sensor_file).config.sensors
            imtups = sensor_cfg_dday(sensor_list)
        _log.debug(imtups)

    #----
    cname = 'u_dday' # or use u_dday or dday  ( # different problems for each)

    for inst, msg in imtups:
        got_data = False

        if options.uhdas_dir:
            globstr = os.path.join(uhdas_dir, 'rbin', inst, '*%s.rbin' %  (msg))
            filelist=pathops.make_filelist(globstr, allow_empty=True)
        else:
            filelist=args

        if len(filelist) == 0:
            if options.uhdas_dir:
                _log.error('no files using %s' % (globstr))
                got_data = False
            else:
                _log.error('uhdas_dir not specified: no files found in arg list')
                got_data = False
        else:
            try:
                data=BinfileSet(filelist)
                if len(data.u_dday) == 0:
                    got_data = False
                    _log.error('%d files but no data using %s' % (len(filelist), globstr))
                else:
                    got_data = True
            except:
                _log.error('no data using %s' % (globstr))
                got_data = False


        if not got_data:
            continue

        first_day = data.starts[cname][0]  # dday
        last_day  = data.ends[cname][-1]  # dday
        if options.startdday:
            startdday = float(options.startdday)
        else:
            startdday = first_day

        if options.ndays:
            ndays = float(options.ndays)
            if ndays < 0:
                data.set_range(ddrange=[last_day + ndays, last_day], cname=cname)
            if ndays > 0:
                data.set_range(ddrange=[startdday, startdday + ndays], cname=cname)
        else:
            ndays = last_day-first_day

        if len(data.u_dday) == 0:
            _log.error('no data left after specifying start/stop')
            continue



        f, ax= plot_gga_times(data, inst, yearbase=options.yearbase)
        add_UTC_fig(f, ax, yearbase=options.yearbase)
        # zoom (or add UTD dates)

        for zoomname in zoomnames:
            if options.titlestr is None:
                if inst in metanames.keys():
                    titlestr = 'GGA from %s (%s)  zoom=%s' % (inst, metanames[inst], zoomname)
                else:
                    titlestr = 'GGA from %s zoom=%s' % (inst, zoomname)
                if options.uhdas_dir:
                    dirstr = os.path.basename(os.path.realpath(options.uhdas_dir))
                    titlestr = '(%s) %s' % (dirstr, titlestr)
            else:
                titlestr=options.titlestr

            f.suptitle(titlestr)
            plt.draw()

            zoom_gga_fig(f, ax, zoomname=zoomname)
            # save
            if options.save_fig:
                save_fig(f, inst, save_dir = outdir, prefix = options.prefix,
                         zoomname=zoomname, thumbnail=options.save_figT)
                if options.outdir2:
                    save_fig(f, inst, save_dir = outdir2, prefix = options.prefix,
                         zoomname=zoomname, thumbnail=options.save_figT)

            # histogram
            outlist = make_gga_hist(data, inst, titlestr=titlestr)
            if options.save_hist:
                save_hist(outlist, save_dir=outdir, prefix=options.prefix, inst=inst)
                if options.outdir2:
                    save_hist(outlist, save_dir=outdir2, prefix=options.prefix,
                              inst=inst)
            if options.print_hist:
                print('\n'.join(outlist))

    if not options.noshow:
        plt.show()

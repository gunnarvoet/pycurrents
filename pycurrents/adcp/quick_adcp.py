"""
Automated processing of shipboard ADCP data.

This version of quick_adcp.py only supports python processing.
We are no longer maintaining Matlab processing. Matlab data
files are still part of the standard output, but the engine
that does the processing is Python. See the web documentation
for more information:

     http://currents.soest.hawaii.edu/docs/adcp_doc/index.html

======================================   ====================================
        run this                             to see this
======================================   ====================================
quick_adcp.py --help                   :        (this page)
quick_adcp.py --vardoc                 : print documentation for variables
quick_adcp.py --varvals                : print variables and current values
--------------------------------------   ------------------------------------
To see commands for various data types, use --commands as follows.
--------------------------------------   ------------------------------------
quick_adcp.py --commands  postproc     :   UHDAS post-processing
quick_adcp.py --commands  uhdaspy      :   UHDAS processing
quick_adcp.py --commands  ltapy        :   LTA or STA files (averaged)
quick_adcp.py --commands  enrpy        :   ENR files (beam coords)
quick_adcp.py --commands  pingdata     :   original pingdata demo
======================================   ====================================

NOTES:

- All these switches use TWO dashes attached to a word. If you use one
  dash or leave a space afterwards, it will fail.
- Wild cards:

  - use quotes on the command line: "*.LTA"
  - do not quote in the control file

- Only pingdata and UHDAS have automatic generation of a heading
  correction (from a gps-aided device such as Ashtech).   There is
  a text file describing how to approach the heading correction
  if you look in the documentation (there is a link in the file
  created by adcptree.py)

"""

## Jules Hummon; 2001/01/07, from lastfiles.py

## moved as_all to fall after putnav; added -readme
## JH 2002/01/24 added refsm (still using smoothr for ref layer plots)
##               changed switches to --help, --overview, --howto
## lastfiles.py ported to python by C. Flagg
## JH 2002/08/31 merge lastfiles.prl, quick_adcp.prl, lastfiles.py

## JH 2004/06/01 - adding posmv heading correction, uhdas incremental,
##
##      new timerange convention:
##          scn_time_range        correct times from scanned files (all input files)
##          origdb_time_range     time range from database at start
##          remaining_time_range  time range after blkfile deletion (incremental)
##          thisload_time_range   time range from files to be loaded
##          loaded_time_range     full db time range after load (same as 'all')
##     ------------
##     specifically: for batch mode, any kind
##        origdb = [long ago]
##        remaining_time_range (unused?)
##        scn_time_range = thisload_time_range = loaded_time_range
##     ------------
##     incremental processing is *not* supported for pingdata, ENS, LTA
##     ----------------
##     incremental UHDAS                  staged = all through blk5, partial
##       adcpdb blocks: | blk0 | blk1 | blk2 | blk3 | blk4 (partial)
##          files (eg.) | 0    | 1    | 2    | 3    | 4
##        'delblks = 1' means "delete 1  blockfile" (to clear out partial blk file)
##        (delblks = 0  means "assume we're starting a blk now" (for debugging)
##        origdb_time_range:    beginning of file0 to file4 (at the time of load)
##        scn_timerange:        scan all raw files
##        remaining_time_range: blk 0,1,2,3  (i.e. remaining in database, after deletion
##        thisload_time_range:  beginning of blk4 through end of scn_time_range
##        loaded_time_range:    all (specified)
##
## JH 2005/04: uhdas heading correction done with hcorr_inst; applied
##       with either post_headcorr or ping_headcorr (unrotate works here)
##
## JH 2009/2010 -- adding various python parts
## JH various changes to move to python-based processing (put matlab
##    numpy, and matplotlib code in quick_mat.py, quick_npy.py, quick_mpl.py,
##    respectively.  changing various arguments.
## JH 2013 -- do not support matlab

## update this!

# quick_adcp.py : opts=parse_opts(argv) , quick_adcp.py(argv), print_vals
#
# quick_setup   : check_opts, get_asvars, run_rawsetup
# quick_aset.py : adcpsect setup -- no fancy imports
# quick_run     : defines all routines such as run_refabs(otps):
# quick_subs    : actually perform calculations

# quick_mat     : calculations requiring matlab
# quick_npy     : other calculations; requires numpy only
# quick_mpl     : matplotlib plots
###########


import sys
import os
import time
import traceback
import logging

import numpy as np

from pycurrents.adcp.quick_setup    import Q_setup
from pycurrents.adcp.quick_setup    import (quickFatalError, get_filelist,
                                            nodb_times)
from pycurrents.adcp.quick_run      import Q_run
from pycurrents.adcp.quick_asect    import Q_asect
from pycurrents.adcp.quick_subs     import Q_subs
from pycurrents.adcp.quick_npy      import Q_npy
from pycurrents.adcp.quick_mpl      import Q_mpl

from pycurrents.system.misc import Bunch
from pycurrents.adcp.quick_template import write_report

# (1) set up logger
_log = logging.getLogger(__name__)

class Processor(Q_setup, Q_run, Q_subs, Q_asect, Q_npy, Q_mpl):
    def __init__(self, opts):
        self.opts = opts


class Qchecker(Q_setup):
    def __init__(self, opts):
        self.opts = opts

#----------------------------------------------------------------------


def usage():
    print(__doc__)
    sys.exit()

#----------------------------------------------------------------------

def print_vals(dict, headerstr=None):

    strlist = []

    if headerstr:
        strlist.append(headerstr)


    keys = list(dict.keys())           ## need to do this in two lines:
    keys.sort()                  ## (1) get keys, (2) sort it

    for key in keys:
        s = '%s   %s' % (key.ljust(30), str(dict[key]))
        strlist.append(s)


    s = '\n\n'
    strlist.append(s)
    return '\n'.join(strlist)


#----------------------------------------------------------------

def get_default_opts():
    opts = Bunch({})  #new 12/2010

    ## defaults for input variables
    ## try to use
    ##   True/False
    ##   integers if used as such
    ##   None, for things that might be undefined

    opts['help'] = False         # print help

    opts['varvals']    = False   # print dictionary values
    opts['vardoc']     = False   # detailed use for each variable

    opts['commands']   = None    # print specific help
    opts['expert']     = None    # print help for experts

    opts['debug']      = False   # verbosity error messages.
                                 #  if True, write more to screen
                                 # and log file

#                        === directories and files ===
#
#     variable         default   # description
#     -------         ---------- # -----------------
#

    ### these do not have useful defaults and are REQUIRED for use

    opts['datatype'] = None
                                 # choose what kind of data logging (and
                                 #   hence which kind of data files
                                 #   are being processed)
                                 #
                                 # default is "pingdata"
                                 #
                                 #  name          what
                                 #  ----          ----
                                 #  "pingdata"     implies DAS2.48 (or 2.49) NB
                                 #
                                 #  "uhdas"        implies known directory
                                 #                     structure for access
                                 #                     to raw data
                                 #  "lta", "sta"   VmDAS averages
                                 #

    opts['sonar'] = None         # eg. nb150, wh300, os75bb, os38nb
                                 # or os75 (mixed pings, set default with pingpref)

    opts['yearbase'] = None      # 4 digits (acquisition year)

    opts['ens_len'] = None       # seconds in an ensemble; default set in dbinfo

    opts['cruisename'] = None    # used for plot titles
                                 # defaults to the averaged data case, where
                                 # cruise name is the same as procdir name

    opts['shipname'] = None      # used in netCDF file

# required in post-processing;

    opts['beamangle'] = None     # degrees (integer).
                                 #   (may not need to be specified
                                 #   if found during single-ping processing)

    opts['dbname']   = None      #  traditionally
                                 #   - start with "a"
                                 #   - then append  4 characters
                                 # defined as the 'XXX' in 'adcpdb/XXXdir.blk'

##  ---- end of required parameters ---

    opts['cntfile']    = None    # override defaults with values from this
                                 #   control file.  Format is the same as
                                 #   command line options, but whitespace is
                                 #   unimportant.  Do not quote wildcard
                                 #   characters in the cnt file (whereas
                                 #   you would for the command line)
                                 # Defaults are overridden by this cntfile
                                 # Commandline options can override either.
##

    opts['proc_yearbase'] = None # 4 digits (defaults to yearbase,
                                 #                 i.e. acquisition year)



    opts['datadir'] = None       # data path. defaults are:
                                 #     (1) relative to scan or load directory
                                 #     (2) full path
                                 #  ../ping       (for LTA, ENS, pingdata)
                                 #
                                 # for NON-UHDAS processing only.
                                 # use "sonar" and cruise_cfg.m for UHDAS


    opts['datafile_glob'] = None #look for sequential data files.
                                 # (not for UHDAS data)
                                 #    defaults are:
                                 #  pingdata.???  (for pingdata)
                                 #  *.LTA         (for LTA files)
                                 #  *.ENS         (for ENS files)

    opts['data_filelist'] = None # ascii file with paths to data
                                 #     (1) relative to scan or load directory
                                 #     (2) full path
                                 #  ../ping       (for LTA, ENS, pingdata)
                                 #
                                 # for NON-UHDAS processing only.
                                 # use "sonar" and cruise_cfg.m for UHDAS


#-----
                                 # Reference layer smoothing:
                                 # two possibilities:
                                 # (1) old:  "smoothr"
                                 #     - bin-based reference layer;
                                 #     - simple averaging
                                 # (2) default: "refsm"
                                 #     - refavg decomposition
                                 #     - calculates timeseries+baroclinic,
                                 #     - minimize error "refsm"
                                 #
                                 #     additionally, supports:
                                 #     - navigation from 'gps' or from
                                 #       translated positions, based on
                                 #       transducer offset from ADCP
                                 #     - ship speed from
                                 #         - 'nav' (traditional calculation
                                 #            of ship speed (from first
                                 #            difference of positions from
                                 #             ensemble end-times)
                                 #         - 'uvship' (new, EXPERIMENTAL)
                                 #            average of ship speeds from
                                 #            pings used, calculted during
                                 #            single-ping processing


    # these two are set in quick_setup.py (check_ref_method)
    opts['ref_method'] = None    ##  Default: use "refsm" for reference layer
                                 #       - positions inputted with "put_txy"
                                 #       - ship speeds inputted with "put_tuv"
                                 ##  other choice: use "smoothr" for reference layer
                                 #       - ship speed and position inputted with "putnav"
                                 #   Plots are done with smoothr, regardless

    ## these two combine in RefSmooth to create tuv.asc for "put_tuv"
    opts['refuv_source'] = None  # default = ship speeds from fixfile
                                 # otherwise EXPERIMENTAL:
                                 #     specify 'uvship' to use
                                 #     ship speeds from "*.uvship" file,
                                 #     (averaged from only those pings used)
                                 #     (only exists for recent software)


    opts['refuv_smoothwin'] = None # default blackman filter half-width = 3
                                 #     (use 2*N-1  ensembles on each side for
                                 #            reference-layer smoothing
                                 # (goes into Refsm as bl_half_width)
                                 # 0: no smoothing
                                 # 1: "use this one point" (no smoothing)
                                 # 2: less smoothing
                                 # 3: default
                                 # (goes into Refsm as bl_half_width)

                                 #------------
     # xducer_dx, xducer_dy      # The next two variables use the offset
                                 # between transducer and gps to "realign"
                                 # the positions closer to the adcp.
                                 # SINGLEPING processing: translated positions are
                                 # if 0
                                 #      in load/*.gps2 --> (catnav) --> nav/*.gps
                                 # if dx!=0 or dy!=0
                                 #      in load/*.gpst2 --> (catnav) --> nav/*.agt

                                 # POSTPROCESSING: run with "--steps2rerun"
                                 #     and specify "navsteps:calib"
                                 #     translates fixfile (.gps or .ags)
                                 #     to txy_file .agt

                                 ## THESE ARE ADDITIVE (add to dbinfo, recaclulate)

    opts['xducer_dx'] = 0        # positive starboard distance from GPS to ADCP
    opts['xducer_dy'] = 0        # positive forward distance from GPS to ADCP


    opts['fixfile'] = None       # override the default fix file.
                                 # defaults are:
                                 # if datatype is pingdata, default is [dbname].ags
                                 # otherwise:
                                 #        [dbname].gps (for uhdas)
 ####


    opts['ub_type']  = '1920'    # For NB DAS only: User buffer type:
                                 # 720 for demo; 1920 for recent cruises



#
#           === processing options ===
#
#    variable         default     # description
#    -------       ----------     -----------------

    opts['rotate_amplitude'] = 1 # run "rotate" on the entire database with
                                 #     amplitude (scale factor) = 1.0
    opts['rotate_angle']     = 0 # run "rotate" on the entire database with
                                 #   this angle (phase), usially a tweak from
                                 #   bottom track or watertrack calibration

    opts['rl_startbin'] = 2      # first bin for reference layer: 1-nbins
    opts['rl_endbin'] = 20       # last bin for reference layer : 1-nbins

    opts['pgmin'] = 50           # only accept PG greater than this value
                                 # --> don't go below 30 <--
                                 # default is 50 for pre-averaged datatypes
                                 #      ('pingdata', 'lta', and 'sta')
                                 # default is 20 for single-ping datatypes
                                 #   ('uhdas', 'enr', 'ens', 'enx')

    opts['slc_bincutoff'] = 0    # default=disabled (0).  Apply a shallow low
                                 # correlation cutoff only above this bin (1-nbins)

    opts['slc_deficit'] = 0      #  default=disabled (0). Flag bins shallower than
                                 # slc_bincutoff with correlation less
                                 # than (max - slc_deficit)


    opts['jitter'] = 15          # OBSOLETE!!
                                 # jitter cutoff (increase value to keep more data)
                                 # MATLAB: jitter is a parameterization of horizontal
                                 #         and vertical second derivatives of u,v
                                 # PYTHON: jitter is the vertical average of median
                                 #         filter applied to each bin in the ref. layer


    opts['find_pflags'] = False  #  automatically find profile flags
                                 #  apply editing (dbupdate, etc)
                                 #  You should be familiar with gautoedit
                                 #      before using this...



   #          === REPROCESSING options ===
   #
   #
   #   variable         default     # description
   #   -------       ----------     -----------------

    opts['steps2rerun'] = ''     # colon-separated list of the following:
                                 # 'rotate:apply_edit:navsteps:calib:matfiles:netcdf'
                                 # designed for batch mode; assumes codasdb
                                 #  already in place, operates on entire
                                 #  database.
                                 #
                                 # 'rotate' is:
                                 #   apply amplitude and phase corrections
                                 #   using these (if specified):
                                 #      rotate_angle (contstant angle)
                                 #      rotate_amplitude (scale factor)
                                 # Apply time-dependent correction manually
                                 #
                                 # 'navsteps' is:
                                 #   [adcpsect+refabs+smoothr+refplots]
                                 #   and reference layer smoothing by
                                 #   refsm (default; uses put_txy, put_tuv)
                                 #   or smoothr (uses putnav)
                                 #
                                 # 'apply_edit' is:
                                 #   badbin, dbupdate, set_lgb, setflags
                                 #
                                 # 'calib' is:
                                 #   botmtrk (refabsbt, btcaluv)
                                 #   watertrk (adcpsect, timslip, adcpcal)
                                 #
                                 # 'matfiles' is:
                                 #   adcpsect for vector and contour
                                 #   Always use  "sonar" for defaults
                                 #   (specify top_plotbin for better results
                                 #    IF you have codas python extensions)
                                 #   or use "firstdepth" to tweak top values
                                 #
                                 # 'netcdf' is:
                                 #  short form (for science) netCDF
                                 #
                                 # 'write_report' is:
                                 # write a summary of cruise metadata
                                 #   - lands in "cruise_info.txt"
                                 # ONLY use this option to generate a cruise
                                 # report for a cruise without one; check for
                                 # "cruise_info.txt" before running in this mode

   #          === Data extraction options ===


    opts['numbins'] = 128        # max number of bins to extract for editing

    opts['firstdepth'] = None    # depth of shallowest bin for adcpsect extraction

##           === specialized processing options  ===

    opts['auto'] = False         # 1: whiz along (do not prompt); do all
                                 #    requested steps (default is all step)
                                 #    0 to prompt at each step


      ############## for UHDAS  processing only ####################
      #                 batch or incremental                       #

    opts['proc_engine'] = 'python'   # Always "python"; only for metadata.

    opts['cfgpath'] = 'config'   # UHDAS only
                                 # Find cfg files (*_cfg.m, *_proc.m) here.
                                 # NOTE: path should be absolute or can be
                                 #   relative root processing directory
                                 #   (if relative, rendered absolute
                                 #   before being used, to remove ambiguity)
                                 # NOTE: cruisename is the prefix for these files
    opts['configtype'] = 'python'   # 'python' python processing


                                 # the following two are RDI beam numbers
    opts['badbeam'] = None       # badbeam for 3-beam data (beam=1,2,3,4)
    opts['beam_order'] = None    # remap beams in this order, eg [1,2,4,3]

    opts['max_search_depth'] = 0 # use predicted topography as follows:
                                 # 0 = always use amp to identify the bottom
                                 #     and remove velocities below the bottom
                                 # -1 = never look for the bottom using amplitude
                                 #      therefore never edit data below the 'bottom'
                                 # positive integer:
                                 #  - if predicted topo is deeper than this
                                 #     depth, then we are in deep water and do
                                 #     not expect to find the bottom. Therefore
                                 #     DO NOT try and identify the bottom
                                 #         (eg. do not idenfity strong
                                 #         scattering layers in deep water)
                                 #  - impacts weak-profile editing
                                 #  - used to be "use_topo4edit" with a search
                                 #     depth of 1000

    opts['incremental'] = False  # for incremental processing of UHDAS data:
                                 # (used to be "delbkls 1"), controls:
                                 # - Averaging will continue with whatever is new.
                                 # - Reload unloaded ens_blk*.cmd files.
                                 # - deletes last partial block file, reloads that
                                 #   plus the remainder.
                                 # other effects: "only do the last"
                                 # - day (autoedit , i.e. --find_pflags)
                                 # - plots (last 2 days of plots only)
                                 # - always rewrite cruise_info.txt metadata file

    opts['pingpref'] = None      # (only activated with these choices for --sonar:
                                 #    os150, os75, os38 (i.e. without the pingtype specified)
                                 #   - used to choose default ping type if interleaved
                                 #   - otherwise it uses whatever is there
                                 #   (whereas eg. os75bb would only use bb pings)

    opts['new_block_on_start'] = False
                                 # force a new block.  To be used with --dday_bailout
                                 # and --incremental (eg. to allow depthchg)

 # default: use the 'sonar' option to choose ping type
                                 # else: use any ping found, but if multiple pings,
                                 # choose this kind in preference (disregards 'sonar')

    opts['maxrunsecs'] = None    # For incremental recovery at sea, set to
                                 #    something smaller than the timeout.
                                 # Averaging code will stop after this duration

    opts['timeout_secs'] = 86400 # For batch processing, disable
                                 #        (set large) the timeout.
                                 # for underway (incremental) processing,
                                 #         set to 1000

    opts['max_BLKprofiles'] = 300# max number of profiles per block.  Might
                                 #  want to make smaller to test incremental
                                 #  processing (must be 512 or less)

    opts['update_gbin'] = False  # UHDAS; update gbin files


    opts['py_gbindirbase'] = None # defaults to uhdas_dir/gbin for python IO

    opts['gbin_gap_sec'] = 15   # do not interpolate over gaps longer than
                                # this many seconds.  Longer gaps require
                                # longer averaging intervals and have worse
                                # statistics (especially if interleaved)

      ############## for UHDAS  processing only, incremental ##################

    opts['save_lastens'] = 0     # save average and raw data from last 5-minute
                                 # ensemble as "lastens.mat"  (for underway
                                 # access to lastens).  Slows down progress
                                 ## (usually implemented through run_lastensq.py)
                                 # --> leave this as an integer

    opts['nosave_editcfg'] = 0   # usually write editcfg parameters to a log file
                                 # Turn this on to avoid saving, if incremental
                                 # processing, to avoid excessively large
                                 # log files --> leave this as an integer


    opts['dday_bailout'] = None  # may be useful for testing (UHDAS only)
                                 #   (bail out of averaging at this time)


    opts['use_rbins'] = False     # for better ship speeds, experimental
    opts['ping_headcorr'] = False # UHDAS only.  apply heading corrections on-the-fly

    opts['skip_avg'] = False     # underway UHDAS processing: 5-minute averages
                                 # are done by an outside source. results:
                                 #  (1) scan only first and last file
                                 #  (2) skip Pingavg; go straight to ldcodas
                                 # NOTE: this means *.bin *cmd files are not made

    opts['uvwref_start'] = None  # python slice start (single-ping refl u,v,w)
    opts['uvwref_end'] = None    # python slice end   (single-ping refl u,v,w)
                                 # To use, set as appropriate eg. slice(3,10)
                                 # Writes load/*uvwref.txt

      ######### PYTHON only ########

    opts['printformats'] = 'png' # print formats to use with matplotlib
                                 # figures -- colon-delimited list.
                                 # Defaults to 'png'.   check your matplotlib
                                 # installation for other backends

    opts['top_plotbin'] = None   # shallowest bin to use for data extraction
                                 # bins are 1,2,3,...
                                 # --> overrides 'firstdepth' if both ar chosen
                                 # --> requires codas python extensions
                                                                  #

    ## end of dictionary (defaults) definition
    return opts


def parse_opts(argv):
    import getopt
    opts = Bunch({})
    try:
        options, args = getopt.getopt(argv, '',
                                      ['help',
                                       'howto_ping',
                                       'howto_lta',
                                       'varvals',
                                       'debug',
                                       'tips',
                                       'commands=',
                                       'expert',
                                       'vardoc',
                                       'overview',
                                       'setup_info',
                                       'cntfile=',
                                       'proc_yearbase=',
                                       'yearbase=',
                                       'beamangle=',
                                       'dbname=',
                                       'datatype=',
                                       'sonar=',
                                       'procdir=',
                                       'cruisename=',
                                       'shipname=',
                                       'configtype=',
                                       'datadir=',
                                       'data_filelist=',
                                       'datafile_glob=',
                                       'fixfile=',
                                       'ub_type=',
                                       'ens_len=',
                                       'xducer_dx=',
                                       'xducer_dy=',
                                       'ref_method=',
                                       'refuv_source=',
                                       'refuv_smoothwin=',
                                       'rotate_amplitude=',
                                       'rotate_angle=',
                                       'rotate_file=',
                                       'timeout_secs=',
                                       'rl_startbin=',
                                       'rl_endbin=',
                                       'uvwref_start=',
                                       'uvwref_end=',
                                       'pgmin=',
                                       'slc_deficit=',
                                       'slc_bincutoff=',
                                       'jitter=',
                                       'numbins=',
                                       'max_search_depth=',
                                       'badbeam=',
                                       'beam_order=',
                                       'top_plotbin=',
                                       'firstdepth=',
                                       'auto',
                                       'steps2rerun=',
                                       # for single-ping
                                       'dday_bailout=',
                                       'cfgpath=',
                                       'proc_engine=',
                                       'ping_headcorr',
                                       'use_rbins',
                                       'update_gbin',
                                       'py_gbindirbase=',
                                       'gbin_gap_sec=',
                                       'editcfg_file=',
                                       # for unattended automatic processing
                                       'save_lastens',
                                       'nosave_editcfg',
                                       'incremental',
                                       'pingpref=',
                                       'new_block_on_start',
                                       'skip_avg',
                                       'maxrunsecs=',
                                       'max_BLKprofiles=',
                                       'find_pflags',
                                       # plotting / calcuation  options
                                       'printformats=',
                                       ])
        #all the rest are data file names
        if len(args) > 0:
            abslist = []
            for f in args:
                abslist.append(os.path.realpath(f))
            # write it out in data_filelist
            data_fname = os.path.realpath(os.path.join('ping','datafile_list.txt'))
            with open(data_fname,'w') as file:
                file.write('\n'.join(abslist))
            opts['data_filelist'] = data_fname
            opts['filelist'] = []
            opts['datafile_glob'] = ''
            _log.info('%d raw data filenames specified on commandline' % (len(abslist)))
            _log.info('storing raw data filenames in %s' % (data_fname))

    except:
        msg = '\n -----> incorrect argument in argument list <----\n'
        msg += traceback.format_exc()
        raise quickFatalError(msg)

    for o, a in options:
        if o in ('--help', ):
            usage()
        elif o in ('--howto_ping', ):       opts['howto_ping']      = True
        elif o in ('--howto_lta', ):        opts['howto_lta']       = True
        elif o in ('--varvals', ):          opts['varvals']         = True
        elif o in ('--overview', ):         opts['overview']        = True
        elif o in ('--vardoc', ):           opts['vardoc']          = True
        elif o in ('--commands', ):         opts['commands']        = a
        elif o in ('--expert', ):           opts['expert']          = True
        elif o in ('--setup_info', ):       opts['setup_info']      = True
        elif o in ('--tips', ):             opts['tips']            = True
        elif o in ('--debug', ):            opts['debug']           = True
        elif o in ('--cntfile', ):          opts['cntfile']         = a
        elif o in ('--proc_yearbase', ):    opts['proc_yearbase']   = int(a)
        elif o in ('--yearbase', ):         opts['yearbase']        = int(a)
        elif o in ('--beamangle', ):        opts['beamangle']       = int(a)
        elif o in ('--dbname', ):           opts['dbname']          = a
        elif o in ('--datatype', ):         opts['datatype']        = a
        elif o in ('--sonar', ):            opts['sonar']           = a
        elif o in ('--procdir', ):          opts['procdir']         = a
        elif o in ('--cruisename', ):       opts['cruisename']      = a
        elif o in ('--shipname', ):         opts['shipname']        = a
        elif o in ('--configtype', ):       opts['configtype']      = a
        elif o in ('--datadir', ):          opts['datadir']         = a
        elif o in ('--data_filelist', ):    opts['data_filelist']   = a
        elif o in ('--datafile_glob', ):    opts['datafile_glob']   = a
        elif o in ('--fixfile', ):          opts['fixfile']         = a
        elif o in ('--ub_type', ):          opts['ub_type']         = str(a)
        elif o in ('--ens_len', ):          opts['ens_len']         = int(a)
        elif o in ('--xducer_dx', ):        opts['xducer_dx']       = int(a)
        elif o in ('--xducer_dy', ):        opts['xducer_dy']       = int(a)
        elif o in ('--ref_method', ):       opts['ref_method']      = a
        elif o in ('--refuv_source', ):     opts['refuv_source']    = a
        elif o in ('--refuv_smoothwin', ):  opts['refuv_smoothwin'] = a
        elif o in ('--rotate_amplitude', ): opts['rotate_amplitude']= float(a)
        elif o in ('--rotate_angle', ):     opts['rotate_angle']    = float(a)
        elif o in ('--rotate_file', ):      opts['rotate_file']     = a
        elif o in ('--rl_startbin', ):      opts['rl_startbin']     = int(a)
        elif o in ('--rl_endbin', ):        opts['rl_endbin']       = int(a)
        elif o in ('--uvwref_start', ):     opts['uvwref_start']    = int(a)
        elif o in ('--uvwref_end', ):       opts['uvwref_end']      = int(a)
        elif o in ('--pgmin', ):            opts['pgmin']           = int(a)
        elif o in ('--slc_deficit', ):      opts['slc_deficit']     = int(a)
        elif o in ('--slc_bincutoff', ):    opts['slc_bincutoff']   = int(a)
        elif o in ('--jitter', ):           opts['jitter']          = int(a)
        elif o in ('--numbins', ):          opts['numbins']         = int(a)
        elif o in ('--max_search_depth', ): opts['max_search_depth']= int(a)
        elif o in ('--badbeam', ):          opts['badbeam']         = int(a)
        elif o in ('--beam_order', ):
            opts['beam_order']     = []
            for num in a.split(':'):
                opts['beam_order'].append(int(num))
        elif o in ('--top_plotbin', ):      opts['top_plotbin']     = int(a)
        elif o in ('--firstdepth', ):       opts['firstdepth']      = int(a)
        elif o in ('--auto', ):             opts['auto']            = True
        elif o in ('--steps2rerun', ):      opts['steps2rerun']     = a
        # for single-ping
        elif o in ('--dday_bailout', ):     opts['dday_bailout']    = float(a)
        elif o in ('--cfgpath', ):          opts['cfgpath']         = a
        elif o in ('--proc_engine', ):      opts['proc_engine']         = a
        elif o in ('--update_gbin', ):      opts['update_gbin']     = True
        elif o in ('--py_gbindirbase', ):   opts['py_gbindirbase']       = a
        elif o in ('--gbin_gap_sec', ):     opts['gbin_gap_sec']         = a
        elif o in ('--editcfg_file', ):     opts['editcfg_file']    = a
        elif o in ('--ping_headcorr', ):    opts['ping_headcorr']   = True
        elif o in ('--use_rbins', ):        opts['use_rbins']        = True
        elif o in ('--timeout_secs', ):     opts['timeout_secs']    = int(a)
        # for unattended automatic processing
        elif o in ('--save_lastens', ):     opts['save_lastens']    = 1
        elif o in ('--nosave_editcfg', ):   opts['nosave_editcfg']  = 1
        elif o in ('--incremental', ):      opts['incremental']      = True
        elif o in ('--pingpref', ):         opts['pingpref']      = a
        elif o in ('--new_block_on_start', ): opts['new_block_on_start'] = True,
        elif o in ('--skip_avg', ):         opts['skip_avg']        = True
        elif o in ('--maxrunsecs', ):       opts['maxrunsecs']      = int(a)
        elif o in ('--max_BLKprofiles', ):  opts['max_BLKprofiles'] = int(a)
        elif o in ('--find_pflags', ):      opts['find_pflags']     = True
        elif o in ('--printformats', ):     opts['printformats']    = a
        else:
            msg = print_vals(opts)
            msg += '\nswitch <%s> failed' % o
            raise quickFatalError(msg)

    ## end of dictionary update from argv

    opts['procdir'] = os.path.realpath(os.getcwd())

    return opts

#--- end parse_opts ------------------------------------------------------


##------------------------------------------------------------------
def run_navsteps(steps2run, opts, proc, stepN):
    _log.info('\n-------------------------')
    _log.info('---- running navsteps ---')
    navstepN=0

    if len(opts['steps2rerun']) > 0 and opts['datatype'] != 'pingdata':
        _log.info('-------------------------')
        stepN+=1
        _log.info('step %s: adjust GPS sensor location' % (stepN))
        navstepN+=1
        _log.info('navstep %s' % (navstepN))
        proc.run_xducerxy()

    ##  adcpsect
    _log.info('-------------------------')
    stepN+=1
    _log.info('step %s: nav steps: run adcpsect' % (stepN))
    navstepN+=1
    _log.info('navstep %s' % (navstepN))
    proc.run_adcpsect()

    ## refabs
    _log.info('-------------------------')
    stepN+=1
    _log.info('step %s: nav steps: run refabs' % (stepN))
    navstepN+=1
    _log.info('navstep %s' % (navstepN))
    proc.run_refabs()

    ## always run smoothr navigation
    _log.info('-------------------------')
    stepN+=1
    _log.info('step %s: nav steps: run smoothr for plots'%(stepN))
    navstepN+=1
    _log.info('navstep %s' % (navstepN))
    proc.run_smoothr()

    if opts['ref_method'] == 'refsm':
        _log.info('-------------------------')
        stepN+=1
        _log.info('step %s: nav steps: smooth navigation for velocities' % (stepN))
        navstepN+=1
        _log.info('navstep %s' % (navstepN))
        refsm_OK = proc.run_refsm()
        if refsm_OK:
            _log.info('-------------------------')
            stepN+=1
            _log.info('step %s: nav steps: put positions and uvship from refsm into codasdb ' % (stepN))
            navstepN+=1
            _log.info('navstep %s' % (navstepN))
            proc.run_put_txy()
            proc.run_put_tuv()
        else:
            return
    else:  # Using smoothr output from earlier unconditional run.
        _log.info('-------------------------')
        stepN+=1
        _log.info('step %s: nav steps: put smoothed nav from smoothr into codasdb' % (stepN))
        navstepN+=1
        _log.info('navstep %s' % (navstepN))
        proc.run_putnav()

    try:
        proc.run_plotnav_mpl()
    except Exception as err:
        _log.exception('cannot make reference layer plots')
        tb = traceback.format_exc()
        _log.debug("Traceback for %s:\n%s", err, tb)

    ## "refplots" plot ref layer (needed smoothr output to run)
    _log.info('-------------------------')
    stepN+=1
    _log.info('step %s: nav steps: make reflayer plots' % (stepN))
    navstepN+=1
    _log.info('navstep %s' % (navstepN))
    try:
        proc.run_plotrefl_mpl()
    except Exception as err:
        _log.exception('Failure to make navigation plot')
        tb = traceback.format_exc()
        _log.debug("Traceback for %s:\n%s", err, tb)

#-- end run_navsteps -----------------------------------------------

# We need to split quick_adcp into get_opts() and quick_adcp_core()
# so that the quick_adcp script can use the opts to set up the logging.
# We need to retain the combined quick_adcp() so that the API
# doesn't change for routines in uhdas that import it.

def get_opts(arglist):
    """
    Get and return a dictionary with all options.

    Options come first from defaults, second from the command line,
    and last from a cntfile if it was specified on the command line.
    """
    opts = get_default_opts()
    cmdline_opts = parse_opts(arglist)
    if 'cntfile' in cmdline_opts:
        try:
            linelist = list()
            with open(cmdline_opts['cntfile']) as newreadf:
                lines = newreadf.readlines()
            for line in lines:
                line = line.split('#')[0]
                tokens = line.split()
                for token in tokens:
                    linelist.append(token)
            cntopts = parse_opts(linelist)
            opts.update(cntopts)
        except Exception as err:
            _log.exception('error parsing cntfile %s',
                          cmdline_opts['cntfile'])
            tb = traceback.format_exc()
            _log.debug("Traceback for %s:\n%s", err, tb)
            raise err

    opts.update(cmdline_opts)

    return opts


def quick_adcp_core(opts):
    """
    Execute all requested processing steps.
    """
    ## FIXME: I moved the next 2 lines down from the beginning of get_opts
    ##        because the logging system is not yet fully set up.
    ##        Do we need it at all?  If so, is it OK to leave it here?
    if not {'--commands', '--help', '--vardoc'}.intersection(set(sys.argv[1:])):
        _log.debug('sys.argv = %s', ' '.join(sys.argv))
    ## If it is left in this location there is no need for the '--help'
    ## check because usage() is run earlier by parse_opts.

    # check options, ensure errors are logged:
    try:
        Qchecker(opts).check_opts()
    except Exception:
        _log.exception("Error found while checking options.")
        raise

    # Everything is done with methods of the aggregate Processor.
    proc = Processor(opts)

    # set up dictionary for steps to run
    ## steps2run MUST be a tuple
    if  len(opts['steps2rerun']) > 0:
        steps2rerun = opts['steps2rerun'].split(':')
        _log.info('found steps2rerun: %s' % (opts['steps2rerun']))
    else:
        steps2rerun = None
    rerun_allowed = ('find_pflags', 'rotate', 'apply_edit',
                     'navsteps', 'calib', 'matfiles', 'netcdf', 'write_report')

    steps2run = [] #initialize, then append

    if not steps2rerun: # running for the first time


        steps2run.append('write_clearflags') # write_clearflags.tmp
        # gbins
        if opts['update_gbin'] is True:  #  if singleping, update gbin
            steps2run.append('update_gbin')

        # scan
        steps2run.append('scandata')  # scanping (scanraw), get_time_range

        # averaging, loading
        steps2run.append('avg_and_load')
        steps2run.append('codaseditsetup')
        steps2run.append('setflags')  # 3. setflags
        steps2run.append('getnav')    # 4. ubprint (catnav)
        steps2run.append('lst_hdg')    # 4. list heading; plot it
        if 'hcorr_inst' in list(opts.keys()):
            if opts['hcorr_inst'] is not None:
                steps2run.append('plot_headcorr')  # 5. plot head corr
        if opts['rotate_angle'] != 0 or opts['rotate_amplitude'] != 1:
            steps2run.append('rotate')    # 6. rotate
        steps2run.append('navsteps')
        if opts['find_pflags']:
            steps2run.append('find_pflags')#13. find profile flags (autoedit)
            steps2run.append('apply_edit') #14. apply editing
            steps2run.append('navsteps')   #15. adcpsect, refabs, smoothr,
                                           #  (or refsm or Refsm or Refsm_uvship ), putnav
                                           #  refplots
        steps2run.append('lst_temp')  #16. run lst_temp and plot temperature
        steps2run.append('plot_temp')  #16. run lst_temp and plot temperature
        steps2run.append('lst_npings')  #16. run lst_npings and plot it
        steps2run.append('calib')     #17. botmtrk (refabsbt, btcaluv) and guess xducer_xy
        steps2run.append('matfiles')  #18. adcpsect for vector and contour
        steps2run.append('netcdf')  #18. adcpsect for vector and contour
        if 'navsteps' in steps2run: #artificial indent for easier reading
            steps2run.append('adcpsect')  # 8. adcpsect for reflayer plots
            steps2run.append('refabs')    # 9. refabs for reflayer plots or smoothr
            steps2run.append('smoothnav') #10. smoothr or refsm or Refsm or Refsm_uvship
            steps2run.append('putnav')    #11. putnav (using smoothr or refsm or Refsm_uvship)
            steps2run.append('refplots')  #12. plot refl
    else:
        steps2run = []      #start with a blank, add steps to rerun
        # assume this is a "rerun" step.  look for options

        for ii in range(0,len(steps2rerun)):
            if steps2rerun[ii]  in rerun_allowed:
                steps2run.append(steps2rerun[ii])
                _log.debug('%d  appending %s', ii, steps2rerun[ii])
            else:
                msg = 'steps2rerun should come from:\n'
                msg += 'rotate:find_pflags:apply_edit:navsteps:calib:matfiles:netcdf\n'
                msg += 'option "%s" not matched' % steps2rerun[ii]
                raise quickFatalError(msg)

        if 'navsteps' in steps2rerun:
            steps2run.append('adcpsect')  # 8. adcpsect for reflayer plots
            steps2run.append('refabs')    # 9. refabs for reflayer plots or smoothr
            steps2run.append('smoothnav') #10. smoothr or refsm or Refsm or Refsm_uvship
            steps2run.append('putnav')    #11. putnav (using smoothr or refsm or Refsm_uvship)
            steps2run.append('refplots')  #12. plot refl

    if opts['find_pflags']:
        steps2run.append('find_pflags')
    ### start steps2rerun ###
    steps2run.append('codaseditsetup')

    _log.info('=====================================================')
    if steps2rerun:
        _log.info('===========  new run: steps2rerun====================')
    _log.info('=====================================================')
    _log.info('command line was: %s' % (' '.join(sys.argv)))
    _log.info('cwd is %s\nabout to run these steps:\n - %s',
                    os.getcwd(), '\n - '.join(steps2run))

    ### more things to define after loading opts and testing for dbname
    ### TODO -- get these out of opts keys (put in separate dict)
    opts['wtrk_step'] = 7  #choose between one of: 5,7,9
    opts['btrk_step'] = (opts['wtrk_step'] - 1)/4  # FIXME: not used;
                                                    # if used, should be int?
    opts['adjust_time'] = 1  #we do want to correct times when we scan
    opts['min_filter_fraction']=  .5 # make more strict if p-code (eg 0.75)
    opts['filter_hwidth']    = 0.0208 # otherwise use  0.0208  (half hour)
                                 # 15 minutes (if p-code GPS)

    ## get adcpsect parameters
    ## adcpsect output
    as_vars = proc.get_asvars()

    as_vars['dbname']  = opts['dbname']
    opts['firstdepth'] = as_vars['firstdepth']

    # The following is interactive-only, so don't bother with logging module(?)
    if opts['varvals']:
        print(print_vals(as_vars, '-----  adcpsect variables ------'))
        print(print_vals(opts, '-----  opts  -----'))
        sys.exit()

    if 'matfiles' in steps2run:
        ## data extraction
        ## must choose one

        if not as_vars['firstdepth'] and not opts['top_plotbin']:
            msg = 'must set "firstdepth" or "top_plotbin"'
            raise quickFatalError(msg)
        ## top_plotbin wins if chosen; requires codas python extensions
        if opts['top_plotbin']:
            tmpname = os.path.join('adcpdb', opts['dbname'])
            if os.path.exists(tmpname):
                from pycurrents.adcp.quick_codas import binmaxdepth
                # set firstdepth using max_plotbin.
                #  NOTE users expect 1-based; codas reader is zero-based
                as_vars['firstdepth'] = int(binmaxdepth(\
                        os.path.join('adcpdb', opts['dbname']), \
                            opts['top_plotbin']-1))

    ############## Warnings: ################

    if not steps2rerun:    # if this is a first run, but it could be incremental
    ## find out whether there are any files

        get_filelist(workdir='scan', opts=opts)

        ## diagnostics:
        if len(opts['filelist']) == 0:
            msg = 'NO data files found'
            raise quickFatalError(msg)
        else:
            _log.debug('starting with data files '
                      +'(as seen from scan/ or load/ directory):\n'
                      +'\n'
                      + opts['filelist'][0] + '\n...\n')
        # check file suffix against datatype (should catch some problems)
        datatype_mismatch = 0
        for ii in range(0, len(opts['filelist'])):
            fext = os.path.splitext(opts['filelist'][ii])[1][1:]

            if (opts['datatype'][-3:] in ('lta', 'LTA', 'sta', 'STA') and \
                                                  fext in ('ens', 'ENS')) or \
               (opts['datatype'][-3:] in ('ens', 'ENS') and \
                                              fext in ('lta', 'LTA', 'sta', 'STA')) :
                datatype_mismatch = 1
                badext = fext
        if datatype_mismatch:
            msg = 'datatype is %s but at least one file has %s extension' % \
                  (opts['datatype'], badext)
            raise quickFatalError(msg)



    ###-----------------  entry in log file ...  --------------------###

    ## now that we are starting to process, write the command and the current
    ## variables and values when quick_adcp.py was called:

    loglist = ['\n\n\n\n', time.asctime()]
    loglist.append('running:')
    loglist.append(' '.join(sys.argv))
    loglist.append(print_vals(as_vars, '\n\n-----  adcpsect variables ------'))
    loglist.append(print_vals(opts,
         '\n\n-----  quick_adcp.py variables and current values ------'))
    loglist.append('configured to run the following steps:')
    for ii in range(0, len(steps2run)):
        loglist.append(steps2run[ii])

    _log.debug('\n'.join(loglist))


    ###----------------- ...  start processing --------------------###

    stepN = 0
    ## (a) set up editing files
    if 'write_clearflags' in  steps2run: #for codas editing parameters
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: set up files in "edit" directory \n'%(stepN))
        proc.run_write_clearflags()   # stages clearflags.tmp


    ## (b) update gbins *before* scan
    if 'update_gbin' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: generate gbins\n' % (stepN))
        proc.run_updatepygbin() #


    ## (1) scan new files if requested
    if 'scandata' in steps2run:
        _log.info('---------------------------------------------')
        stepN += 1
        _log.info('step %s: scan files for time range\n', stepN)
        if opts['datatype'] == 'uhdas':
            try:
                proc.run_scanping_npy()  #UHDAS data
            except Exception as err:
                _log.exception('cannot run scan')
                tb = traceback.format_exc()
                _log.debug("Traceback for %s:\n%s", err, tb)
        else: # sta, lta, pingdata
            proc.run_scandata() #makes scan file

    # always get the raw filelist time ranges
    timefile = os.path.join('scan','%(dbname)s.scn' % opts)
    trfile = os.path.join('scan','%(dbname)s.tr' % opts)
    time_range_string = None
    if os.path.exists(trfile):
        try:
            with open(trfile,'r') as newreadf:
                time_range_string = newreadf.readlines()[0]
        except Exception as err:
            _log.exception('Issue with reading time ranges')
            tb = traceback.format_exc()
            _log.debug("Traceback for %s:\n%s", err, tb)
            pass
    trddlist = proc.get_time_range(timefile, time_range_string)
    proc.write_timerange_file(trfile, trddlist[0])
    opts['scn_time_range'] = trddlist[0]
    opts['scn_startdd'] = trddlist[1]
    opts['scn_enddd'] = trddlist[2]

    if 'avg_and_load' in steps2run:
        block_list = proc.listblocks(workdir='adcpdb')
        if block_list:
            if opts['incremental']:
                trfile = os.path.join('adcpdb','%(dbname)s.tr' % opts)
                trddlist = proc.get_time_range(block_list)
                proc.write_timerange_file(trfile, trddlist[0])
                opts['origdb_time_range'] = trddlist[0]
                opts['origdb_startdd'] = trddlist[1]
                opts['origdb_enddd'] = trddlist[2]
            else:
                raise quickFatalError("A database is already in place; data can"
                                      " be added only by using the 'incremental'\n"
                                      " option.  Otherwise, to reload, delete the"
                                      " existing database first. The blocklist is\n"
                                      "%s\n" % '\n'.join(block_list))
        else:
            _log.info('no database found: starting from scratch')

            opts['origdb_time_range'] = nodb_times[0]
            opts['origdb_startdd'] = nodb_times[1]
            opts['origdb_enddd'] =  nodb_times[2]

        _log.debug('in quick_adcp.py before load, just looked for database times')
        _log.debug('origdb_time_range is %s ', opts['origdb_time_range'])
        _log.debug('(%f to %f)', opts['origdb_startdd'], opts['origdb_enddd'])


        if opts['datatype'] == 'pingdata':
            _log.info('---------------------------------------------')
            stepN+=1
            _log.info('step %s: load averaged data (to database)' % (stepN))
            proc.run_loadping()
        else:
            if opts['datatype'] in ('lta', 'sta'):
                _log.info('---------------------------------------------')
                stepN+=1
                _log.info('step %s: load averaged data (to database)' % (stepN))
                proc.run_loadlta_npy()
            else: #uhdas
                _log.info('---------------------------------------------')
                stepN+=1
                _log.info('step %s: generate averaged data...' % (stepN))
                proc.run_py_pingeditsetup() #load/ping_editparams.txt
                proc.run_pybincmd_uhdas()  # Make bin and cmd files.
                _log.info('---------------------------------------------')
                stepN+=1
                _log.info('step %s: load averaged data (to database)' % (stepN))
            # load database with *bin, *cmd
            proc.run_loaddb()

    ## ALWAYS get time range of whole database
    trfile = os.path.join('adcpdb','%(dbname)s.tr' % opts)
    block_list = proc.listblocks(workdir='adcpdb')
    trddlist = proc.get_time_range(block_list)
    proc.write_timerange_file(trfile, trddlist[0])
    opts['loaded_time_range'] = trddlist[0]
    opts['loaded_startdd']    = trddlist[1]
    opts['loaded_enddd']      = trddlist[2]

    if opts['steps2rerun']:  # not loading
        opts['thisload_time_range'] = ''
        opts['thisload_startdd']    = -10000
        opts['thisload_enddd']      = -10000
    elif opts['thisload_startdd'] is None:
        # if redoing a broken step to finish first run
        opts['thisload_time_range'] =    opts['loaded_time_range']
        opts['thisload_startdd']    =    opts['loaded_startdd']
        opts['thisload_enddd']      =    opts['loaded_enddd']

    seconds_loaded = np.floor(86400*(opts['loaded_enddd']
                                     - opts['loaded_startdd']))

    _log.info('database time range:')
    _log.info(opts['loaded_time_range'])
    _log.info('(%f to %f)', opts['loaded_startdd'], opts['loaded_enddd'])

    ## list configuration changes on database
    proc.run_lstconfig()

    # check now; beam angle should exist by now
    proc.check_beamangle()

    #### (3) get ready for autoedit:
    ## python edit setup after load
    if 'codaseditsetup' in  steps2run: #for codas editing parameters
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: set up files for codas editing (gautoedit.py)\n' % (stepN))
        proc.run_py_codaseditsetup()#edit/codas_editparams.txt

    ## (4) run setflags
    if 'setflags' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: run setflags?\n' % (stepN))
        proc.run_setflags()

    ##### bail out completely if there is only one profile
    if opts['loaded_startdd'] == opts['loaded_enddd']:
        _log.info('only one profile; quitting quick_adcp')
        return seconds_loaded

    ## (5) get navigation fixes
    if 'getnav' in  steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: get navigation\n' % (stepN))
        proc.run_getnav()
        proc.run_plot_uvship()

    ## (6) now get heading correction
    # list heading
    if 'lst_hdg' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: list heading\n' % (stepN))
        proc.run_lsthdg()

    if ('plot_headcorr' in steps2run): # and (opts['datatype'] == 'pingdata'):
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: plot heading correction\n' % (stepN))
        proc.run_plotheadcorr()

    ##  rotate
    if 'rotate' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: rotate velocities\n' % (stepN))
        proc.run_rotate()

    if not steps2rerun: ## first time only; another chance later
        if 'navsteps' in steps2run:
            run_navsteps(steps2run, opts, proc, stepN)

    ## find profile flags (autoedit)
    if 'find_pflags' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: find profile flags \n' % (stepN))
        proc.run_py_findpflags()

    ## apply editing
    if 'apply_edit' in  steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: apply editing \n' % (stepN))
        proc.run_applyedit()

        ## rerun nav steps
    if steps2rerun:
        if 'navsteps' in steps2run:
            _log.info('---------------------------------------------')
            stepN+=1
            _log.info('step %s: run all navsteps \n' % (stepN))
            run_navsteps(steps2run, opts, proc, stepN)

    ## now run bottom track and water track calibrations
    if 'calib' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: run calibration steps \n' % (stepN))
        try:
            proc.run_calib()
        except Exception as err:
            _log.exception('Failure to run calibration')
            tb = traceback.format_exc()
            _log.debug("Traceback for %s:\n%s", err, tb)
        try:
            proc.run_guess_xducerxy()
        except Exception as err:
            _log.exception('Failure to guess xducerxy')
            tb = traceback.format_exc()
            _log.debug("Traceback for %s:\n%s", err, tb)
    ## now run lst_temp and plot
    if 'lst_temp' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: extract and plot temperature \n' % (stepN))
        proc.run_lstplot_temp()

    ## run lst_npings and plot
    if 'lst_npings' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: extract and plot number of pings per ensemble \n' % (stepN))
        proc.run_lstplot_npings()

    ## make matlab files
    if 'matfiles' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: extract matlab "allbins" \n' % (stepN))
        proc.run_matfiles(as_vars)

    ## make netcdf short form
    if 'netcdf' in steps2run:
        _log.info('---------------------------------------------')
        stepN+=1
        _log.info('step %s: generate netcdf file \n' % (stepN))
        try:
            proc.run_adcp_nc(as_vars)
        except Exception as err:
            _log.exception('Failure to make netcdf file')
            tb = traceback.format_exc()
            _log.debug("Traceback for %s:\n%s", err, tb)



    # in general, only do it for new processing
    if not steps2rerun:
        _log.info('---------------------------------------------')
        _log.info('writing "cruise_info.txt"\n')
        write_report(opts, 'cruise_info.txt', overwrite=opts['incremental'])
    else:
        # allows us to write report for an old cruise
        if 'write_report' in steps2rerun:
            _log.info('writing "cruise_info.txt"\n')
            write_report(opts, 'cruise_info.txt')

    return seconds_loaded


def quick_adcp(arglist):
    opts = get_opts(arglist)
    return quick_adcp_core(opts)

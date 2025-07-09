import sys
import os
from argparse import ArgumentParser

from pycurrents.adcpgui_qt.lib.miscellaneous import get_dict_from_config_file

# Standard logging
import logging
_log = logging.getLogger(__name__)

### Argument parsers ###
dataviewer_help = """
Script for ADCP CODAS data viewer.

**Usage**

    *view mode: view CODAS database*
        call from from a processing directory: dataviewer.py
        call from anywhere                   : dataviewer.py path/to/proc/dir

    *editing mode: `gautoedit`*
        call from processing "edit" dir      : dataviewer.py -e

    *singleping viewer (UHDAS only, correct configuration files in place)*
        call from processing "edit" dir      : dataviewer.py -p
        call from processing "edit" dir      : dataviewer.py -p [options]

    *compare 2 databases*
        call from anywhere:    dataviewer -c path1 path2

**Arguments**
    *path*
        path to processing directory or sonar name

**Options**
    *modes*
    -v [--view]      view codas adcp data
    -e [--edit]      edit codas adcp data
    -p [--ping]      view codas and singleping data
    -c [--compare]   view (compare) data from 2 sonars

    *color plots*
    -s [--step]      steps, duration (days) to view in panels
    -n [--numpanels] number of panels (<= 12)
    -t [--title]     title for panel and topo plots (overrides default)

    *topo. map*
    -m [--minutes]   number of minutes to average in topo. map
    --zoffset        subtract this altitude from all topography
    --vecscale       vector scale: larger number shrinks vectors
    --ref_sonar      name of the reference sonar (only in compare mode)

    *data*
    --dbname         path to database (up to but not including 'dir.blk')
    --startdday      decimal day to start
    --sonar          such as 'os38bb', 'wh300', to read raw data
    --netcdf         path to NetCDF file (*.nc)

    *accessibility*
    --whitebg        show pcolor masked (bad) values as white
    --colorblind     switches on colorblind friendly color schemes

    *logging*
    --debug          If present, switches on debug level logging.
                     Optional argument is debug_file_path
                     (default being ./debug.log)

    *for expert only*
    --advanced       enables advanced forensic thanks to
                     a custom Ipython console

    *for edit , compare and single ping modes only*
     These parameters might be needed if 'dbinfo' is insufficient
      (or not exist):
    --cruisename     base name for configuration file
    --beamangle      angle of the ADCP beams, in deg., upward from vertical
    --configtype     read 'python' (default) or 'matlab' config files
    --ibadbeam       index of the non-working beam, (1, 2, 3 or 4)
                     (see RDI manual)
    --uhdas_dir      path to directory containing 'raw', 'rbin' and 'gbin'

    *setting file*
    --setting_file   path to setting file. One can specify all the above
                     options (and more) via a *.ini file.
                     (see pycurrents/*MODE*_setting_template.ini)
                     N.B.: the options specified the in *.ini will override
                           the related command line options.
    *progress file*
    --progress_file  path to progress file (.pgrs). For a given cruise,
                     this file will bring the user back to his/her previously
                     saved progression.
                     N.B.: the options specified the in *.pgrs will override
                           the command line and/or *.ini options.

**Examples**::

   dataviewer.py path/to/cruiseID/sonar -n 3 -t sonar
   dataviewer.py -c path/to/sonar1 path/to/sonar2

"""


def dataviewer_option_parser(arglist=[]):
    """
    Options/arguments parser for dataviewer GUI

    Args:
        arglist: list of command line options/arguments, list of str.

    Returns: options, ArgumentParser object
    """
    parser = ArgumentParser(usage=dataviewer_help, add_help=False)
    # Custom help doc
    parser.add_argument('-h', '--help', dest='help',
                        action='store_true')
    # Logging level
    parser.add_argument("--debug", dest="debug",
                        action='store_true',
                        help="switches on debug level logging.\n ")
    # Display options
    parser.add_argument("--colorblind", dest="colorblind",
                        action='store_true',
                        help="switches on colorblind friendly color schemes")
    parser.add_argument("--advanced", dest="advanced",
                        action='store_true',
                        help="enables advanced forensic thanks to a custom" +
                             " Ipython console")
    # - modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--view", dest="mode", action='store_const',
                        const="view", default="view",
                        help="view codas adcp data")
    group.add_argument("-e", "--edit", dest="mode", action='store_const',
                        const="edit", default="view",
                        help="edit codas adcp data")
    group.add_argument("-p", "--ping", dest="mode", action='store_const',
                        const="single ping", default="view",
                        help="view codas and singleping data")
    group.add_argument("-c", "--compare", dest="compare", nargs='+',
                        help="view (compare) data from 2 sonars at least")
    # - color plots
    parser.add_argument("-s", "--step", dest='day_step',
                        type=float, nargs='?', default=None,
                        help="duration (days) to view in panels")
    parser.add_argument("-n", "--numpanels", dest="num_axes",
                        type=int, nargs='?', default=4,
                        help="number of panels (<= 12)")
    parser.add_argument("--whitebg", dest='background',
                        nargs='?', const='w', default=None,
                        help="show pcolor masked (bad) values as white")
    parser.add_argument("-t", "--title", dest="plot_title",
                        type=str, nargs='?', default=None,
                        help="title for panel and topo plots\n" +
                             " (overrides default which is dbname)")
    # - topo. map
    parser.add_argument("--vecscale", dest="vec_scale",
                        type=float, nargs='?', default=None,
                        help='vector scale: larger number shrinks vectors')
    parser.add_argument("--zoffset", dest="z_offset",
                        type=float, nargs='?', default=None,
                        help='subtract this altitude from all topo.' +
                             ' (eg. Lake Superior)')
    parser.add_argument("-m", "--minutes", dest="delta_t",
                        type=float, nargs='?', default=None,
                        help="number of minutes to average in topo. map" +
                             "(default is 30)")
    parser.add_argument("--ref_sonar", dest="ref_sonar",
                        type=str, nargs='?', default='',
                        help="name of the reference sonar " +
                             "(only in compare mode)")
    # Data options
    parser.add_argument("path", metavar='path',
                        type=str, nargs='?', default=None,
                        help="path to database, (up to but not including" +
                             " 'dir.blk')")
    parser.add_argument("--dbname", dest="dbpathname",
                        type=str, nargs=1,
                        default=[os.getcwd()],
                        help="path to database, (up to but not including" +
                             " 'dir.blk')")
    parser.add_argument("--uhdas_dir", dest="uhdas_dir",
                        type=str, nargs='?', default=None,
                        help="path to directory containing 'raw'," +
                             " 'rbin' and 'gbin'")
    parser.add_argument("--netcdf", dest="netcdf",
                        type=str, nargs='?', default=None,
                        help="path to NetCDF file (*.nc)")
    # FIXME: use_bt still under dev.
    # parser.add_argument("--use_bt", dest="use_bt",
    #                     action='store_true',
    #                     help="calculate ocean velocities using BT values (not nav)")
    parser.add_argument("--startdday", dest="start_day",
                        type=float, nargs='?', default=None,
                        help="starting time (decimal day)")
    parser.add_argument("--sonar", dest="sonar",
                        type=str, nargs='?', default=None,
                        help="such as 'os38bb', 'wh300'")
    parser.add_argument("--cruisename", dest="cruisename",
                        type=str, nargs='?', default=None,
                        help="cruise ID or title for plots " +
                           "(or use 'cruiseid'")
    parser.add_argument("--beamangle", dest="beamangle", type=float,
                        nargs='?', default=None,
                        help='angle of the ADCP beams, in deg.,' +
                             ' upward from vertical')
    parser.add_argument("--ibadbeam", dest="ibadbeam", type=int,
                        nargs='?', default=None,
                        help='index of the non-working beam, (0, 1, 2 or 3)')
    parser.add_argument("--configtype", dest="configtype", default='python',
                        help="read 'python' or 'matlab' config files")
    # Configuration file
    parser.add_argument("--setting_file", dest="setting",
                        type=str, nargs=1,
                        default=None,
                        help="path to configuration file. One can specify" +
                             " all the above options (and more) via a *.ini" +
                             " file. (see pycurrents/*MODE*_setting_template.ini)" +
                             "N.B.: the options specified the in *.ini will" +
                             " override the command line options.")
    # Progress file
    parser.add_argument("--progress_file", dest="progress",
                        type=str, nargs=1,
                        default=None,
                        help="path to progress file. For a given cruise, " +
                             "this file will bring the user back to the" +
                             " previously saved progression step."
                             "N.B.: the options specified the in *.pgrs will" +
                             " override the command line and *.ini options.")

    # Checking options' compatibility
    options = parser.parse_args(args=arglist)
    if options.help:
        print(dataviewer_help)
        sys.exit(0)
    # - override options with config. parameters
    if options.setting or options.progress:
        if options.progress:
            path_to_cfg = options.progress
        else:
            path_to_cfg = options.setting
        ini_dict = get_dict_from_config_file(path_to_cfg)
        for key in ini_dict:
            try:
                if getattr(options, key) != ini_dict[key]:
                    setattr(options, key, ini_dict[key])
            except AttributeError:
                continue
        options.setting = ini_dict
    # - look for database
    if options.path:
        options.dbpathname = [os.path.abspath(options.path)]
    if options.dbpathname:
        for ii, path in enumerate(options.dbpathname):
            options.dbpathname[ii] = os.path.abspath(os.path.expanduser(path))
    if options.netcdf:
        options.dbpathname = [os.path.abspath(options.netcdf)]
        options.netcdf = True
        if options.mode != "view":
            msg = "======WARNING======\n"
            msg += 'NetCDF files can only be used in "view" mode for now'
            print(msg)
            _log.debug(msg)
            sys.exit(0)
    if options.compare:
        # - check mode incompatibility
        if options.mode == "single ping":
            msg = "======WARNING======\n"
            msg += '"Compare" mode and "single Ping" mode are not compatible'
            print(msg)
            _log.debug(msg)
            sys.exit(0)
        else:
            options.mode = 'compare'
        # - check if provided folders exist
        paths = []
        for user_entry in options.compare:
            path = os.path.abspath(user_entry)
            if os.path.exists(path):
                paths.append(path)
            else:  # - check if options.dbpathname + sonar-name exist
                path = os.path.join(options.dbpathname[0], user_entry)
                if os.path.exists(path):
                    paths.append(path)
        options.compare = paths
        # - add more panels
        if options.num_axes < 8:
            options.num_axes = 8
        # - check if at least 2 sonars
        if len(options.compare) < 2:
            print('======At least 2 sonars are required in compare mode======')
            print(dataviewer_help)
            sys.exit(0)
    if options.vec_scale:
        try:
            options.vec_scale = 1./options.vec_scale
        except ZeroDivisionError:
            options.vec_scale = 0
    if options.num_axes:
        if options.num_axes > 12:
            options.num_axes = 12
    if options.mode == "single ping":
        options.advanced = True
    if options.ibadbeam is not None:
        options.ibadbeam -= 1
        print(options.ibadbeam)
        if options.ibadbeam < 0 or options.ibadbeam > 3:
            print('======Wrong ibadbeam index======')
            print(dataviewer_help)
            sys.exit(0)
    if options.debug:  # FIXME: unknown incompatibility between --debug and --advanced
        options.advanced = False

    return options


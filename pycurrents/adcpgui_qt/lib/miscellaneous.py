import os
import sys
import logging
import time
import glob
import subprocess
import configparser
from numpy import where
from datetime import datetime, timedelta
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QTextCursor

from pycurrents.system.misc import Bunch  # BREADCRUMB: common lib from here...
from pycurrents.system import pathops
from pycurrents.num import Stats
from pycurrents.adcp import EA_estimator
from pycurrents.adcp.uhdas_defaults import serial_suffix
from pycurrents.adcp.raw_multi import Multiread  # BREADCRUMB: ...to here

# Standard logging
_log = logging.getLogger(__name__)


# Loggers
def nowstr():
    '''
    get utc time from computer clock, return string "yyyy/mm/dd hh:mm:ss"
    '''
    return time.strftime("%Y/%m/%d %H:%M:%S")


# Formatting
def utc_formatting(x, pos=None, yearbase=2010):
    # Fix for Ticket 685
    date = datetime(yearbase, 1, 1) + timedelta(x)
    return date.strftime('%m/%d %H:%M')


# For testing purposes
def get_qapp():
    """
    Attempt to handle QApplication instances during testing phase
    Better use qtbot !!!
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([''])
    return app


# Matplotlib lib
def reset_artist(artist):
    """
    Remove artist from axis

    Args:
        artist: Matplotlib artist or collection of artists
    """
    # N.B.: exceptions in case artist == collection or artist == something
    #       unexpected
    excepted_errors = (ValueError, TypeError, AttributeError, KeyError)
    if artist:
        try:
            artist.remove()
        except excepted_errors:
            try:
                for art in artist:
                    try:
                        art.remove()
                    except excepted_errors:
                        continue
            except excepted_errors:
                pass
    return None


# For backward compatibility purposes...FIXME
def backward_compatibility_quick_fix(params, CD):
    """
    Fill in missing database's info for backward compatibility purposes

    Args:
        params: dict. of parameters

    Returns: compatible params
    """
    if 'dbname' not in params.keys():
        params['dbname'] = CD.dbpathname.split('/')[-1]
    if 'pgmin' not in params.keys():
        params['pgmin'] = 50
    if not params['beamangle']:
        params['beamangle'] = CD.beamangle

    return params


# Utils
def dict_diff_to_str(first_dict, second_dict):
    diff = {}
    for k in first_dict.keys():
        if first_dict[k] != second_dict[k]:
            diff[k] = second_dict[k]
    return diff.__str__()


def is_in_data_range(display_feat):
    start = display_feat.start_day
    end = display_feat.start_day + display_feat.day_step
    t1 = display_feat.day_range[0] < start < display_feat.day_range[1]
    t2 = display_feat.day_range[0] < end < display_feat.day_range[1]

    return t1 and t2


def blank_function(*args, **kwargs):
    pass


# Stream redirection
class OutLog:
    def __init__(self, edit, out=None, color=None):
        """
        Redirects stream to a PyQt widget.

        Original credits: https://riverbankcomputing.com/pipermail/pyqt/...
                          ...2009-February/022025.html

        Args:
            edit: PyQt widget, preferably QTextEdit
            out: alternate stream (can be the original sys.stdout)
            color: alternate color (i.e. different color for stderr), QColor
        """
        self.edit = edit
        self.out = out
        self.color = color

    def write(self, text):
        """
        Standard method for stream
        """
        if self.color:
            tc = self.edit.textColor()
            self.edit.setTextColor(self.color)
        self.edit.moveCursor(QTextCursor.End)
        self.edit.insertPlainText(text)
        if hasattr(self.edit, 'repaint'):
            # refresh QTextEdit as the stream comes in
            self.edit.repaint()
        if self.color:
            self.edit.setTextColor(tc)
        if self.out:
            self.out.write(text)

    def flush(self):
        """
        Standard method for stream
        """
        # Need to avoid error when closing form because
        # it is a default/required method for streams
        pass


# 'fud' is 'Fake UhDas'
def vars_from_fud(fake_file):
    """
    get variables from fake_uhdas; stage rbins

    Args:
        fake_file: path to file, str.
    """
    fudbunch = Bunch().from_pyfile(fake_file)
    varbunch = Bunch()
    for name in ['uhdas_dir', 'vmdas_dir', 'yearbase', 'adcp', 'shipkey']:
        varbunch[name] = fudbunch[name]

    varbunch.lists = Bunch(heading=[], position=[], rollpitch=[], hcorr=[])

    for tup in fudbunch.navinfo:
        dir, msg, num = tup
        ## using str on a tuple to show the string representation of the tuple in the menu
        if msg in serial_suffix.position:
            varbunch.lists['position'].append(str((dir, msg)))
        if msg in serial_suffix.heading:
            varbunch.lists['heading'].append(str((dir,msg)))
            varbunch.lists['hcorr'].append(str((dir,msg)))
        if msg in serial_suffix.rollpitch:
            varbunch.lists['rollpitch'].append(str((dir,msg)))

        varbunch.cruisename = os.path.basename(fudbunch.uhdas_dir)
        varbunch.ducer_depth = ''
        varbunch.h_align = ''
    return varbunch


# Mining VmDAS data info
def list_vmdas_files(selected_dir):
    """
    List all *ENR, *LTA and *STA files present in the selected directory
    Args:
        selected_dir: path to selected directory, str.
    """
    enr_files, lta_files, sta_files = [], [], []
    try:
        enr_files = pathops.make_filelist(
            os.path.join(selected_dir, '*ENR'))
    except ValueError:  # error raised when no *.ENR
        pass
    try:
        lta_files = pathops.make_filelist(
            os.path.join(selected_dir, '*LTA'))
    except ValueError:  # error raised when no *.LTA
        pass
    try:
        sta_files = pathops.make_filelist(
            os.path.join(selected_dir, '*STA'))
    except ValueError:  # error raised when no *.LTA
        pass
    return enr_files, lta_files, sta_files


def EA_estimation_from_enr(enr_files, inst_type):
    """
    Return Estimated Alignment (EA) of the ADCP

    Args:
        enr_files: list of *ENR file paths, [str.,..., str.]
        inst_type: instrument type, eg. 'os', 'wh', 2 letters, str.

    Returns: printable message, str.
    """
    numenr = len(enr_files)
    step = 1
    if numenr > 3:
        step = numenr * 10
    m = Multiread(enr_files, inst_type)
    data = m.read(step=step, stop=10000)
    npts = len(data.dday)
    msg = ''
    if npts > 3:
        underway_min_speed = 1.0
        mag, a, iused = EA_estimator.get_xducer_angle(data, 2)
        igood = where(mag > underway_min_speed)[0]
        if not len(igood) == 0:
            S = Stats(a[igood])
            msg += 'Transducer angle estimated from water data:\n  '
            msg += 'mean=%5.2f ,stddev=%5.2f, num pts=%4d\n' % (
                S.mean, S.std, S.N)
        if data.bt_xyze.count() > 0:
            mag, a, iused = EA_estimator.get_xducer_angle(data, -1)
            igood = where(mag > float(underway_min_speed))[0]
            if not len(iused) == 0 and not len(igood) == 0:
                S = Stats(a[igood])
                msg += 'Transducer angle estimated from bottomtrack:\n  '
                msg += 'mean=%5.2f ,stddev=%5.2f, num pts=%4d\n' % (
                    S.mean, S.std, S.N)
    return msg


# Mining UHDAS data info
def get_pingtypes(filelist, instmodel):
    m = Multiread(filelist, instmodel)
    pingtypes = []
    if instmodel[:2] in ('os', 'pn', 'ec'):
        pingbunch = Bunch()
        pingbunch.bb = m.bbchunks
        pingbunch.nb = m.nbchunks
        for pingtype in pingbunch.keys():
            if len(pingbunch[pingtype]) > 0:
                pingtypes.append(instmodel + pingtype)
    else:
        if len(m.chunks) > 0:
            pingtypes.append(instmodel)
    return pingtypes


def get_adcp_filelist(datadir):
    ext_names = Bunch()
    ext_names['ENR'] = 'vmdas'
    ext_names['raw'] = 'uhdas'
    for suffix in ext_names.keys():
        filelist = glob.glob(os.path.join(datadir, '*.%s' % (suffix)))
        if len(filelist) > 0:
            filelist.sort()
            return filelist, ext_names[suffix]
    return [], None


# System
def run_command(arg_list, comment=''):
    """
    Run command line

    Args:
        arg_list: list of command line arguments, [str., ..., str.]
    """
    _log.debug("arg_list: " + ' '.join(arg_list))
    print("===Please Wait While the Process is Running===")
    print(comment)
    try:
        # Run command
        # Version 1: working but no live stdout
        output = subprocess.check_output(
            ' '.join(arg_list),
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True)
        # Version 2: working but still no live stdout !
        # process = subprocess.Popen(' '.join(arg_list),
        #                            stdout=subprocess.PIPE,
        #                            stderr=subprocess.STDOUT)
        # for c in iter(lambda: process.stdout.read(1), ''):
        #     print('PRINTING')
        #     sys.stdout.write(c)
        # process.wait()
    except subprocess.CalledProcessError as exc:
        # Inform user & quit
        msg = "Status : FAIL"
        msg += str(exc.returncode)
        msg += str(exc.output)
        print(msg)
        _log.error(msg)
        sys.exit(1)
    else:
        msg = str(output)
        print(msg)


# Tailing files
#   Author - Kasun Herath <kasunh01 at gmail.com>
#   Source - https://github.com/kasun/python-tail
class Tail(object):
    """
    Represents a tail command.
    """
    def __init__(self, tailed_file):
        """
        Initiate a Tail instance.
        Check for file validity, assigns callback function to standard out.

        Args:
            tailed_file: File to be followed, str.
        """
        self.check_file_validity(tailed_file)
        self.tailed_file = tailed_file
        self.callback = sys.stdout.write

    def follow(self, s=1):
        """
        Do a tail follow.
        If a callback function is registered it is called with every new line.
        Else printed to standard out.

        Args:
            s: Number of seconds to wait between each iteration; Defaults to 1
        """
        with open(self.tailed_file) as file_:
            # Go to the end of file
            file_.seek(0, 2)
            while True:
                curr_position = file_.tell()
                line = file_.readline()
                if not line:
                    file_.seek(curr_position)
                    time.sleep(s)
                else:
                    self.callback(line)

    def register_callback(self, func):
        """Overrides default callback function to provided function."""
        self.callback = func

    def check_file_validity(self, file_):
        """
        Check whether the a given file exists, readable and is a file
        Args:
            file_: File to be followed, str.
        """
        if not os.access(file_, os.F_OK):
            raise TailError("File '%s' does not exist" % (file_))
        if not os.access(file_, os.R_OK):
            raise TailError("File '%s' not readable" % (file_))
        if os.path.isdir(file_):
            raise TailError("File '%s' is a directory" % (file_))


class TailError(Exception):
    def __init__(self, msg):
        self.message = msg

    def __str__(self):
        return self.message


# Handling Config. Files
def write_dict2config_file(path_to_ini, config_dict, section_name='DEFAULT'):
    """
    Write any dictionary into a standard *.ini configuration file.
    Check following for details on *.ini file formatting:
        https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

    Args:
        path_to_ini: path to *.ini file, str.
        config_dict: dictionary of parameters, dict.
        section_name: str.
    """
    # built parser
    parser = configparser.ConfigParser(
        config_dict, default_section=section_name)
    # Write to file
    with open(path_to_ini, 'w+') as f:
        parser.write(f)


def get_dict_from_config_file(path_to_ini):
    """
    Parse and return a dictionary from the parameters specified in a given
    *.ini configuration file.Check following for details
    on *.ini file formatting:
        https://docs.python.org/3/library/configparser.html#supported-ini-file-structure

    Args:
        path_to_ini: path to *.ini file, str.

    Returns: dict.

    """
    # built parser
    parser = configparser.ConfigParser()
    # read *.ini
    parser.read(path_to_ini)
    # Find out section name
    section_list = parser.sections()
    if not section_list:
        section_name = 'DEFAULT'
    else:
        section_name = section_list[0]  # only the one section here
    # Turn into dictionary
    ini_dict = dict(parser[section_name])
    # Evaluate strings
    for key in ini_dict.keys():
        val_str = ini_dict[key]
        try:
            ini_dict[key] = eval(val_str)
        except (NameError, SyntaxError):
            continue

    return ini_dict



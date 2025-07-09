import os
import glob
import re
import logging

from pycurrents.adcpgui_qt.presenter.intercommunication import get_dbpath
from pycurrents.data.timetools import ddtime  # BREADCRUMB: common library

# Standard logging
_log = logging.getLogger(__name__)


class ASCIIandPathContainer:
    tmp_edit_filename = dict(
        bottom='tmp_bottom.asc',
        badprf='tmp_badprf.asc',
        badbin='tmp_badbin.asc')

    log_edit_filename = dict(
        bottom='abottom.asclog',
        badprf='abadprf.asclog',
        badbin='abadbin.asclog')

    def __init__(self, mode, path_to_db):
        """
        Container Class containing ascci files, system paths and
        read/write/open/close methods for communication with the CODAS database

        Args:
            mode: GUI mode, str.
            path_to_db: path to CODAS database, str.
        """
        self.mode = mode
        self.working_directory = os.path.abspath("./")
        # Sanity check
        if isinstance(path_to_db, list):
            path = path_to_db[0]
        else:
            path = path_to_db
        # FIXME: quick fix
        if not '.nc' == path[-3:]:
            self.db_path = get_dbpath(path)
        else:
            self.db_path = path
        if self.mode in ['edit', 'single ping']:
            # log file
            self.edit_dir_path = os.path.abspath(
                os.path.join(self.db_path, "../..", "edit"))
        if self.mode == 'edit':
            # edit templates
            self.tmp_edit_paths = dict(
                bottom=os.path.join(
                    self.edit_dir_path, self.tmp_edit_filename['bottom']),
                badprf=os.path.join(
                    self.edit_dir_path, self.tmp_edit_filename['badprf']),
                badbin=os.path.join(
                    self.edit_dir_path, self.tmp_edit_filename['badbin']))
            self.log_edit_paths = dict(
                bottom=os.path.join(
                    self.edit_dir_path, self.log_edit_filename['bottom']),
                badprf=os.path.join(
                    self.edit_dir_path, self.log_edit_filename['badprf']),
                badbin=os.path.join(
                    self.edit_dir_path, self.log_edit_filename['badbin']))
            self.log_path = os.path.join(self.edit_dir_path,
                                         self.mode + '.log')
        else:
            # log file
            self.log_path = os.path.join(self.working_directory,
                                         self.mode + '.log')

    def __str__(self):
        msg = ""
        for key in self.__dict__.keys():
            msg += "   %s: %s\n" % (key, self.__dict__[key])
        return msg

    def write_to_log(self, message):
        """Write given message to log file"""
        # Log in ascii file
        # Bug fix for ticket 898
        try:
            with open(self.log_path, 'a') as file:
                file.write(message)
        except OSError:
            msg = 'PERMISSION DENIED: cannot write in %s\n' % self.log_path
            msg += 'message: %s\n' % message
            _log.warning(msg)

    def update_asclog_files(self):
        """Preserve contents of *X*.asc files in a*X*.asclog"""
        for k in self.log_edit_paths.keys():
            logfile, tmpfile = self.log_edit_paths[k], self.tmp_edit_paths[k]
            # for backward compatibility: if no logfile, cat old contents there
            if os.path.exists(logfile) and os.path.exists(tmpfile):
                _log.debug('-- Preserving contents of %s in %s ---' %
                          (tmpfile, logfile))
                with open(tmpfile, 'r') as newreadf:
                    contents = newreadf.read()
                with open(logfile, 'a') as file:
                    file.write(contents)
            elif os.path.exists(tmpfile):
                # rename tmpfile to logfile
                _log.debug('--- Renaming %s to %s ---' % (tmpfile, logfile))
                os.rename(tmpfile, logfile)

    def remove_tmp_files(self):
        """Remove temporary files from the edit folder"""
        for tmp_file in self.tmp_edit_paths.values():
            try:
                os.remove(tmp_file)
            except FileNotFoundError:
                _log.debug("--- %s not found ---" % tmp_file)
                continue

    def cull_asc_dates(self, yearbase=None, ddrange=None):
        """Remove edits, within a given time range, from the ascci files"""
        filelist = self._current_asc_files() + self._current_asclog_files()
        if len(filelist) == 0:
            return
        pat = r"\b\d{2,4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\b"

        for fname in filelist:
            with open(fname, 'r') as newreadf:
                lines = newreadf.readlines()
            newlines = []
            for line in lines:
                matchobj = re.findall(pat, line)
                if len(matchobj) > 0:
                    timestamp = matchobj[0]
                    dd = ddtime(yearbase, timestamp)
                    if dd < ddrange[0] or dd > ddrange[1]:
                        newlines.append(line)
        # overwrite original file with those lines taken out
        with open(fname, 'w') as file:
            file.writelines(''.join(newlines))

    def _current_asc_files(self):
        """Return the path(s) of the existing *.asc file(s)"""
        return glob.glob(os.path.join(self.edit_dir_path, '*.asc'))

    def _current_asclog_files(self):
        """Return the path(s) of the existing *.asclog file(s)"""
        return glob.glob(os.path.join(self.edit_dir_path, '*.asclog'))


class ASCIIandPathContainerCompareMode(dict):
    def __init__(self, list_db_paths):
        """
        Container Class containing ascci files, system paths and
        read/write/open/close methods for communication with
        the CODAS databases. For compare mode only.

        Args:
           list_db_paths: list of system paths to codas databases, [str., ...]
        """
        super().__init__()
        for db_path in list_db_paths:
            sonar_name = db_path.split('/')[-1]  # Assuming a certain format
            # Check if sonar_name already exist and change name if needed
            # Bug Fix - Ticket 816
            ii = 0
            while True:
                if sonar_name in list(self.keys()):
                    ii += 1
                    sonar_name = sonar_name .split('_')[0] + "_" + str(ii)
                else:
                    break
            self[sonar_name] = ASCIIandPathContainer("edit", db_path)
        # Group attributes
        self.log_path = os.path.join(os.path.abspath("./"), 'compare.log')

    def __str__(self):
        msg = ""
        for key in self.keys():
            msg += "   %s: %s\n" % (key, self[key].__str__())
        return msg

    # Group methods
    def write_to_log(self, message):
        """Write given message to log file"""
        # Log in ascii file
        with open(self.log_path, 'a') as file:
            file.write(message)

    def _db_paths(self):
        db_path = []
        for sonar_name in list(self.keys()):
            db_path.append(self[sonar_name].db_path)
        return db_path

    def _edit_dir_paths(self):
        edit_dir_paths = []
        for sonar_name in list(self.keys()):
            edit_dir_paths.append(self[sonar_name].edit_dir_path)
        return edit_dir_paths

    db_paths = property(_db_paths)
    edit_dir_paths = property(_edit_dir_paths)

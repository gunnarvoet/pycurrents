import os
import sys
import logging
import subprocess
from datetime import datetime
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QTextEdit, QDockWidget, QMainWindow, QWidget
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QGridLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QColor, QIcon
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt


from pycurrents.adcpgui_qt.lib.qtpy_widgets import (iconUHDAS,
    make_busy_cursor, restore_cursor, CustomSeparator)
from pycurrents.adcpgui_qt.lib.miscellaneous import OutLog

# Standard logging
_log = logging.getLogger(__name__)


class GenericForm(QMainWindow):
    def __init__(self, parent=None):
        """
        Generic form framework

        Args:
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        # Form styling
        self.setWindowIcon(QIcon(iconUHDAS))
        # Attributes
        self.row = 0
        # Widgets
        # - Entries box
        self.entriesBox = QWidget(parent=self)
        self.entriesLayout = QGridLayout()
        self.entriesBox.setLayout(self.entriesLayout)
        # - Text area
        self.logTextArea = QTextEdit(parent=self)
        self.logTextArea.setReadOnly(True)
        self.entriesLayout.addWidget(self.logTextArea)
        # - docking window
        self.dock = QDockWidget("Log Messages", parent=self)
        self.dock.setWidget(self.logTextArea)
        self.dock.setFloating(False)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock)
        # - central widget
        self.setCentralWidget(self.entriesBox)
        # Redirects stdout to self.logWidget
        sys.stdout = OutLog(self.logTextArea, sys.stdout,
                            color=QColor(0, 128, 0))

    def _print(self, msg, color='black'):
        """
        Custom method for printing message in text area

        Args:
            msg: message to be printed, str.
            color: 'black' or 'red'
        """
        if color == 'black':
            color = QColor(0, 0, 0)
        elif color == 'red':
            color = QColor(255, 0, 0)
        elif color == 'green':
            color = QColor(0, 128, 0)
        self.logTextArea.setTextColor(color)
        self.logTextArea.append(msg)
        self.logTextArea.repaint()
        # set back to black
        self.logTextArea.setTextColor(QColor(0, 0, 0))
        self.logTextArea.repaint()

    def _exists(self, path):
        """
        Check if path exists. If not, write message to log messages and pass

        Args:
            path: system path, str.

        Returns: True or False, bool.
        """
        if os.path.exists(path):
            msg = "%s already exists! " % path
            msg2 = '\nDelete, move, rename existing, choose a different path'
            msg2 += ' or data/file(s) will be overwritten\n'
            self._print(msg + msg2, color='red')
            return True
        else:
            return False

    # FIXME: redundant command with pycurrents.adcpgui_qt.lib.miscenallous.run_command
    def run_command(self, arg_list, comment=''):
        """
        Run command line & print stdout in form's text area

        Args:
            arg_list: list of command line arguments, [str., ..., str.]
        """
        make_busy_cursor()
        _log.debug("arg_list: " + ' '.join(arg_list))
        self._print("===Please Wait While the Process is Running===",
                    color='red')
        # Log in file
        pwd = os.getcwd()
        log_filename = "run_command.log"
        log_file_path = os.path.join(pwd, log_filename)
        log_file = open(log_file_path, 'a')
        timestamp = "\n===" + str(datetime.now()) + "===\n"
        self._print(comment)
        # Version 1: some stdoutput are not caught
        # try:
        #     output = subprocess.check_output(
        #         ' '.join(arg_list), stderr=subprocess.STDOUT, shell=True,
        #         universal_newlines=True)
        # except subprocess.CalledProcessError as exc:
        #     msg = "Status : FAIL"
        #     msg += str(exc.returncode)
        #     msg += str(exc.output)
        #     self._print(msg, color='red')
        #     log.error(msg)
        #     # Inform user & quit
        #     print("Status : FAIL", exc.returncode, exc.output)
        #     sys.exit(1)
        # else:
        #     self._print(str(output), color='green')
        #
        # Version 2: catches all outputs
        #            from http://blog.kagesenshi.org/2008/02/...
        #                      ...teeing-python-subprocesspopen-output.html
        log_file.write(timestamp)
        log_file.write("Command: " + ' '.join(arg_list) + "\n")
        p = subprocess.Popen(' '.join(arg_list), shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log_file.write("Std Output:\n")
        while True:
            line = ''.join(p.stdout.readline().decode("utf-8").splitlines())
            self._print(line, color='green')
            log_file.write(line+"\n")
            if line == '' and p.poll() is not None:
                break
        log_file.close()
        restore_cursor()

    def _separator(self):
        """
        Add separation line in entries box
        """
        self.row += 1
        self.entriesLayout.addWidget(
            CustomSeparator(parent=self), self.row, 0, 1, -1)

    # Override built-in method hide
    def hide(self):
        # Force hide docked window (necessary if undocked)
        self.dock.hide()
        # Original callback
        super().hide()

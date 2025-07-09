"""
Functions, strings, and instances to facilitate use of the logging module
"""

import logging
import os
import re
import sys
import traceback

import numpy as np

formatterMinimal = logging.Formatter("%(message)s")

formatTLN = "%(asctime)s %(levelname)-8s %(name)-12s %(message)s"
formatterTLN = logging.Formatter(formatTLN)

formatTLM = "%(asctime)s %(levelname)-8s %(module)-14s %(message)s"
formatterTLM = logging.Formatter(formatTLM)

formatTLMpid = "%(asctime)s %(levelname)-8s %(process)7d:%(module)-14s %(message)s"
formatterTLMpid = logging.Formatter(formatTLMpid)

# For parsing:
_fields = {
    "TL": ["asctime", "levelname", "message"],
    "TLN": ["asctime", "levelname", "name", "message"],
    "TLM": ["asctime", "levelname", "module", "message"],
    "TLMpid": ["asctime", "levelname", "process", "module", "message"],
}
_regexs = {
    "TL": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(.*)",
    "TLN": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(\w+)\s+(.*)",
    "TLM": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(\w+)\s+(.*)",
    "TLMpid": r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+(\w+)\s+(\d+):(\w+)\s+(.*)",
}

_formats = list(_fields.keys())


def _parse_logfile(filename, format):
    if format not in _formats:
        raise ValueError(f"format '{format}' is not in supported list: {_formats}")
    logpat = _regexs[format]
    with open(filename) as infile:
        loglines = infile.readlines()
    logrecords = []
    for line in loglines:
        match = re.match(logpat, line)
        if match:
            logrecords.append(list(match.groups()))
        elif logrecords:
            logrecords[-1][-1] += line
    return logrecords, _fields[format]


def logfile_to_numpy(filename, format):
    """
    Parse a logfile into a numpy structured array, based on the format.  The
    numpy dtype uses datatime64 for the first field and "object", here a Python
    string, for the rest.

    This handles multi-line message records by appending additional lines to
    the last field (the "message") of the last record identified by the regular
    expression match.
    """
    logrecords, fields = _parse_logfile(filename, format)
    tups = []
    for record in logrecords:
        record[0] = record[0].replace(",", ".")  # milliseconds
        tups.append(tuple(record))
    field_list = [("time", "datetime64[ms]")]
    field_list.extend([(name, object) for name in fields[1:]])
    dtype = np.dtype(field_list)
    return np.array(tups, dtype=dtype)


# logging lib
def unexpected_error_msg(err):
    err = str(err)  # Might or might not be a string...
    msg = "Unexpected error:" + " ".join([err, traceback.format_exc()])
    return msg


def getLogger(fpath=""):
    """
    Returns a logging.Logger instance, either root or named.

    If a root logger is already configured (with a handler),
    then a named logger is returned; otherwise the root logger
    is configured to simply print messages, and it is returned.

    example, near top of a module:

        log = getLogger(__file__)
        log.info('starting %s', __file__)

    The name argument can be a file path, in which case it is
    stripped down to the base file name without extension.
    """

    fname = os.path.split(fpath)[1]
    fnamebase = os.path.splitext(fname)[0]

    _log = logging.getLogger()
    if _log.handlers:
        _log = logging.getLogger(fnamebase)
    else:
        logging.basicConfig(format="%(message)s", level=logging.DEBUG)
    return _log


def getDebugFileHandler(debug_log_path):
    """
    Return custom logging handler for debug mode.
    It grabs all log messages, format them and
    sticks them into a debug.log ascii file

    Args:
        log: standard logger instance from logging.getLogger
    """
    # redirect debug messages to debug.log
    fileHandlerDebug = logging.FileHandler(debug_log_path)
    fileHandlerDebug.setLevel(logging.DEBUG)
    fileHandlerDebug.setFormatter(formatterTLN)

    return fileHandlerDebug


def setDebugLogger(debug_log_path=""):
    """
    Set specific logger for debug mode.
    Logger redirects log.debug entries to the specified file and stdout.
    It also redirects the stderr to the specified file

    Args:
        debug_log_path: path to log file, str.
                        if none, default file is ./debug.log
    """
    if not debug_log_path:
        debug_log_path = os.path.join(os.getcwd(), "debug.log")
    # Define handlers
    fileHandler = getDebugFileHandler(debug_log_path)  # redirect log entry to file
    fileHandler.setFormatter(formatterTLN)
    stdoutHandler = logging.StreamHandler(sys.stdout)  # redirect log entry to stdout
    stdoutHandler.setFormatter(formatterTLN)
    # Define basic config
    logging.basicConfig(
        handlers=[fileHandler, stdoutHandler], level=logging.DEBUG, format=formatTLN
    )
    # Redirect stderr to debug.log
    stderr_logger = logging.getLogger("STDERR")
    sl = STDERRLogger(stderr_logger)
    sys.stderr = sl


def setLoggerFromOptions(options):
    """
    Set logger based on options

    Args:
        options: ArgumentParser instance
    """
    if options.debug:
        # set-up logger
        debug_log_path = ""
        if isinstance(options.debug, str):
            debug_log_path = os.path.abspath(options.debug)
        setDebugLogger(debug_log_path)
        # Logging
    else:
        stdoutHandler = logging.StreamHandler(sys.stdout)
        stdoutHandler.setLevel(logging.WARNING)
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        stdoutHandler.setFormatter(formatter)
        logging.basicConfig(handlers=[stdoutHandler], level=logging.WARNING)


class STDERRLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    see: https://www.electricmonk.nl/log/2011/08/14/redirect-stdout-and-stderr-to-a-logger-in-python/
    """

    def __init__(self, logger, log_level=logging.ERROR):
        self.logger = logger
        self.log_level = log_level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

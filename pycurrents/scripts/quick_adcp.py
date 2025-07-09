#!/usr/bin/env python
import logging
import os
import sys

import matplotlib
matplotlib.use('Agg')

from pycurrents.adcp.quick_adcp import get_opts, quick_adcp_core
from pycurrents.adcp.quick_adcp import usage
from pycurrents.system.logutils import formatterTLM


logging.captureWarnings(True)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logging.getLogger('matplotlib').setLevel(logging.WARN)

_log = logging.getLogger()

arglist = sys.argv[1:]

if not arglist:
    usage()

opts = get_opts(arglist)

if opts['debug']:
    _log.setLevel(logging.DEBUG)

logfile = os.path.join(os.getcwd(), 'quick_run.log')

mode = 'a' if opts['steps2rerun'] else 'w'
handler = logging.FileHandler(logfile, mode)

handler.setFormatter(formatterTLM)
_log.addHandler(handler)

quick_adcp_core(opts)


import logging

# Standard logging
_log = logging.getLogger(__name__)

REFORMVAR_TEMPLATE = """

###-------------------------------------------------------
### begin python program "reform_vmdas_form.py"

# list of tuples: (instrument, message, N_R file number)
__navinfo__


__yearbase__     # first year of data
__uhdas_dir__    # location of raw, rbin
__vmdas_dir__    # location of ENR, N1R, etc.
__adcp__         # sonar: 2 letters for instrument, and freq (kHz)
__shipkey__      # used to name uhdas files

"""


REFORMFILE_TEMPLATE = """

from pycurrents.adcp.vmdas import FakeUHDAS

# get the variables from %(reformvar_file)s
fname = '%(reformvar_file)s'
with open(fname) as f:
    code = compile(f.read(), fname, 'exec')
    exec(code)



dt_factor = 3   # median(dt) * dt_factor = when to break the files in to parts
                # 3   :   allows more variable ping rate (eg. if triggering)
                # 0.5 :   assumes fixed ping rate (might make lots of pieces)


# convert vmdas data to uhdas data
F = FakeUHDAS(yearbase=yearbase,
              sourcedir=vmdas_dir,
              destdir=uhdas_dir,
              sonar=adcp,
              dt_factor=dt_factor,
              navinfo=navinfo,
              ship=shipkey)
F()


"""

REFORM_SUCCESS_MSG = """
%s has been created.
Click "Convert to UHDAS" to recast vmdas data as if it were UHDAS data.
Or close this form, cd to config folder and manually run in a shell:
        python %s
"""

PROC_STARTER_END_MSG = """
Now everything is set up for UHDAS single-ping processing.
To proceed automatically, click the button to "Set up Processing Directories"

To do this manually:
  - create your processing directory using "adcptree.py"
  - change directories to that location
  - in that directory, create your quick_adcp.py control file
Your quick_adcp.py control file should start with this:
      --yearbase  %s
      --cruisename %s
"""

UHDAS_PROCGEN_APPENDIX = """
uhdas_dir = '%s'
yearbase = %s  # usually year of first data logged
shipname = '%s'  # for documentation
cruiseid = '%s'  # for titles
"""

CONTROL_FILE_TEMPLATE = """
 --yearbase %s  ## required, for decimal day conversion (year of first data)
 --cruisename %s  ## *must* match prefix in config dir
 --dbname %s  ## database name; in adcpdb.  eg. a0918
 --datatype uhdas  ## datafile type
 --sonar %s  ## specify instrument letters, frequency,
                ##     (and ping type for ocean surveyors)
 --ens_len %s  ## averages of 300sec duration
 --configtype  python  ## file used in config/ dirctory is python
 --max_search_depth %s  ## try to identify the bottom and eliminate
                           ##    data below the bottom IF topo says
                           ##    the bottom is shallower than 1000m
 --xducer_dx %s  ## positive starboard distance from GPS to ADCP
 --xducer_dy %s  ## positive forward distance from GPS to ADCP
 --update_gbin  ## always update the gbin
"""

CONTROL_FILE_TEMPLATE_HEAD_CORR = """
 --ping_headcorr  ## ps0918_proc.py says use HDT first, correct to ashtech
"""

DATAVIEWER_READY_MSG = """Review this file:\n%s \n...or scroll up to read (contents shown above)

This important information contains:
- comments about the dataset
- steps to take in postprocessing

You can view the dataset immediately using dataviewer.py:
    dataviewer.py %s"""

SINGLE_PING_READY_MSG = """
%s is now ready for single-ping processing.
Follow the instructions above or
click "Set up Processing Directories" to move to the next form
"""

ARCHITECTURE_REQUIREMENT_MSG = """
The folder architecture does not comply to requirements
Proceed to the operation manually following the documentation
See: https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/index.html
"""

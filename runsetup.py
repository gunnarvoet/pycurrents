#!/usr/bin/env python3

"""
Build pycurrents, including extensions.  This is a wrapper for
installation with setuptools and pip.

Setuptools defaults are used, with one exception that is described
below. If the installation
location is the linux standard, /usr/local, you will need to use
the --sudo option. Do not use sudo directly on the runsetup.py
command, and do not use the --sudo option unless you need to.
Alternatives include changing the ownership of /usr/local so that
sudo is not needed, or allowing the installation to occur (by default)
in your user-based location.  For Linux, that is with the prefix
'~/.local/'.  This will automatically add that location to your
python search path, if it was not already there.  You will need
to add '~/.local/bin' to your PATH environment variable, however,
so that scripts will be found.

IMPORTANT: If you will be working with CODAS (or UHDAS) shipboard
ADCP databases, then the codas3 C library and executables must
already have been installed, and the path to its binaries must
already be on your PATH.

Note that there is no need to use runsetup.py at all; you can
use, for example, the Python standard

    pip install .

Using ./runsetup.py in typical cases is equivalent to

    pip install --log=runsetup.log .

except that it uses a 2-step process and leaves behind a wheel.  You
can delete it, or reuse it, or just leave it.  It will be overwritten
if the source code is updated and ./runsetup.py is re-run.

Prior to January, 2023, runsetup.py handled an additional case: if the codas
installation prefix was a path that starts with the Python sys.prefix,
then scripts were installed in the codas binary location.  This had
little practical advantage, and is not possible with consistent use
of pip as the frontend for building and installing.

"""

import os
import subprocess
import sys
from optparse import OptionParser

from setup_helper import (find_codasbase,
                          find_executable,
                          show_installed,
                          uninstall,
                          build,
                          clean,)


package = 'pycurrents'

def main():
    usage = "./runsetup.py [options] [test args]\n  With no options, build and install.\n"
    usage += __doc__
    parser = OptionParser(usage=usage)
    parser.add_option('--scratch', action='store_true',
                                   default=False,
                                   help='rebuild and install all modules')
    parser.add_option('--clean', action='store_true',
                                   default=False,
                                   help='run "hg purge --all"')
    parser.add_option('--uninstall', action='store_true',
                                   default=False,
                                   help='uninstall with pip, if installed')
    parser.add_option('--yes', action='store_true',
                                   default=False,
                                   help="don't ask before uninstalling")
    parser.add_option('--develop', action='store_true',
                                   default=False,
                                   help='install in editable mode')
    parser.add_option('--cython',  action='store_true',
                                   default=False,
                                   help='Run cython, then rebuild everything.'
                                        ' (Only if you really know what you are doing.)')
    parser.add_option('--show', action='store_true',
                                   default=False,
                                   help='show installation status and exit')
    parser.add_option('--sudo', action='store_true',
                                   default=False,
                                   help='use sudo for install/uninstall/clean steps')
    parser.add_option('--test', action='store_true',
                      default=False,
                      help='Run tests. Most tests require that '
                            'the "pycurrents_test_data" directory be located '
                            'next to this pycurrents repo.')
    parser.add_option('--test_and_log', action='store_true',
                      default=False,
                      help=('Run tests and save the '
                            'logger output in ./test.log and '
                            'the standard output in ./test.stdout'))
    parser.add_option('--Break_system_packages', action='store_true',
                                   default=False,
                                   help='python 3.11 interaction passthrough to pip.')

    options, args = parser.parse_args()

    print("Python executable for building is", sys.executable)

    installed, install_mode = show_installed(package)

    if installed is None:
        print('ERROR: something is wrong with your python 3 installation.'
              ' It should include a "pip" or "pip3" command, but we cannot'
              ' find it.  Quitting.')
        sys.exit(-1)

    try:
        codas_prefix = find_codasbase()
        print("codas prefix for lib and include is", codas_prefix)
    except RuntimeError:
        print("No CODAS3 installation was found; proceeding without it.")

    if options.show:
        return

    if options.clean:
        if not installed or install_mode == 'normal':
            clean(options)
        else:
            print('pycurrents is installed as editable; '
                  ' before running with --clean, uninstall, and optionally'
                  ' reinstall in normal mode.')
        return

    if options.uninstall:
        if installed:
            uninstall(package, options)
        return

    if options.scratch:
        if installed:
            uninstall(package, options)
        clean(options)

    if options.cython:
        run_cython(timecheck=(not options.scratch))

    if options.test or options.test_and_log:
        test(log_to_file=options.test_and_log, testargs=args)
    else:
        if installed:
            uninstall(package, options)
        build(package, options)

# functions specific to this package, defined here instead of in setup_helper

def run_cython(timecheck=True):
    print("in run_cython with timecheck = ", timecheck)
    for dirpath, dirnames, filenames in os.walk('.', topdown=False):
        for fn in (f for f in filenames if f.endswith('.pyx')):
            pyxfile = os.path.join(dirpath, fn)
            root, ext = os.path.splitext(fn)
            cfile = os.path.join(dirpath, root + '.c')
            if timecheck and os.path.exists(cfile):
                if os.path.getmtime(pyxfile) <= os.path.getmtime(cfile):
                    continue
            cmd = "cython -3 %s" % pyxfile
            print(cmd)
            os.system(cmd)

def test(log_to_file=False, testargs=None):
    # N.B. pycurrents and test_data folders have to be side by side for running
    #      all the tests
    pytest_cmd = find_executable(['pytest-3', 'pytest'])
    if pytest_cmd is None:
        print("can't find pytest or pytest-3")
        sys.exit(-1)

    print("Start Testing")
    # Default pytest options
    argslist = ['-v', '--disable-pytest-warnings']
    # Check if pytestqt is installed
    pytestqt_installed = True
    try:
        import pytestqt
        pytestqt.version
    except ImportError:
        pytestqt_installed = False
    # Check whether or not we have display
    display = "DISPLAY" in os.environ
    # Ignore GUI testing if need be
    if not pytestqt_installed or not display:
        argslist.append('--ignore=./pycurrents/adcpgui_qt')
    argslist.append('--ignore=./pycurrents/test')  # Handled separately at the start.
    # Logging to file
    if log_to_file:
        argslist += ['--log-file', './test.log', '|', 'tee', './test.stdout']
        print("Logging test results in ./test.stdout")
    # NOTE: Using pytest.main is the proper way to call the test from a script
    #       yet it generates cryptic errors
    #       (i.e. does not find pycurrents modules)
    # import pytest
    # pytest.main(argslist)
    # NOTE: Using a subprocess seem to do the job though

    command0 = " ".join([pytest_cmd, "pycurrents/test"])
    proc = subprocess.run(command0, shell=True)
    if proc.returncode != 0:
        sys.exit(-1)

    command_line = " ".join(['MPLBACKEND=agg', pytest_cmd] + argslist + testargs)
    subprocess.run(command_line, shell=True)
    print("Final Testing Stage: run the following command\n"
          "    figview.py ./test_figures")


if __name__ == '__main__':
    main()

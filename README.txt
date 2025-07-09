Note
====
This is [pycurrents](https://currents.soest.hawaii.edu/hgstage/pycurrents/) at changeset `3518:a9ae5a40f793` from July 03, 2025, with a few modifications for easy installation under [uv](https://docs.astral.sh/uv/). I added the files `MANIFEST.in` and `pyproject.toml` and removed a bunch of stuff in `setup.py` - not sure if the latter was necessary.

The package can now be built / added via a simple `uv add pycurrents` where `pycurrents` points to these source files.

-- old readme below --

Installation
=======================================

For a normal installation, such as in a conda environment, run

   ./runsetup.py

For a global installation, such as on a UHDAS machine, run

    ./runsetup.py --sudo

For more information, see the runsetup.py docstring.
Python's building and installation mechanisms (distutils
and setuptools) do not always detect dependencies correctly
or clean out obsolete files, so if in doubt, you may use
the --scratch option to rebuild and reinstall everything.

Usage: runsetup.py [options]

Options:
  -h, --help  show this help message and exit
  --scratch   rebuild all modules
  --clean     delete build directory
  --cython    run cython, then rebuild everything
  --show      show installation prefix and exit
  --sudo      sudo will be applied to the build step
  --test      runs "pytest -v"


Use of the --cython option is not recommended unless you are
a developer, and even then only under rare circumstances.

To thoroughly clean out the repo's working directory, removing anything that
is not tracked, use

    hg purge --all



Installations made with code updated at the end of 2019 can be uninstalled with

    pip uninstall pycurrents

Use of pip to install pycurrents is *not* yet recommended because it will not
correctly generate a function used to locate the test data.

=======================================

To regenerate the pycurrents documentation (a work in progress),
install sphinx (with all it's requirements) and do this

cd doc
make html


The documentation starts in    _build/html/index.html

Requirements
============
pycurrents requires python 3.6+, matplotlib 2.1+, and pyqt5.


Testing
=======
Two options are available for testing:
1. Use the testing options provided in the package, that "--test" or
   "--test_and_log" as follows:
     ./runsetup.py --test
   or
     ./runsetup.py --test_and_log
  The first option will run the test units and display theirs outputs on the screen.
  The second option put the logging module output in "test.log" and
  everything you would otherwise see on the screen in "test.stdout".

2. Run pytest directly for more flexibility. For instance, to run the test units
   in "very verbose" mode, type:

   pytest -vv

   Note that, pytest should be run from the repo base directory (where this
   README.txt file is). There are many more pytest options you might want to use,
   displayed with "pytest --help".

The tests also make a "test_figures" directory for the resulting plots.
They can be displayed and scanned by running "figview.py" after the tests
have run:
  figview.py ./test_figures

Note that testing of adcpgui_qt requires installation of the
pytest-qt package, which is available in Ubuntu beginning with
17.10, and is also available via pip and conda (from the conda-forge
channel). In order to ignore adcpgui_qt while using pytest, use the
"--ignore=./pycurrents/adcpgui_qt" option.

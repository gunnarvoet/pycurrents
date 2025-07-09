# formatting: black

import os
import glob

from setuptools import find_packages, setup, Extension
import Cython
from Cython.Build import cythonize
import numpy

if Cython.__version__.startswith("3."):
    npy_macros = [("NPY_NO_DEPRECATED_API", "NPY_1_7_API_VERSION")]
else:
    npy_macros = []

# We are using the following variable to label the c files
# that are compiled from pyx source; or, if desired, to make
# it easy to change back to pyx extension and using build_ext
# from Cython.Distutils.
pyx = ".pyx"


## Define all extension modules
nbvelmod = Extension(
    "pycurrents.adcp.nbvel",
    [
        "pycurrents/adcp/src/nbvel" + pyx,
        "pycurrents/adcp/src/nbspeedsubs.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

transformmod = Extension(
    "pycurrents.adcp._transform",
    [
        "pycurrents/adcp/src/_transform" + pyx,
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

bottommod = Extension(
    "pycurrents.adcp._bottombounce",
    [
        "pycurrents/adcp/src/_bottombounce" + pyx,
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

checksumsmod = Extension(
    "pycurrents.data.nmea.checksums",
    [
        "pycurrents/data/nmea/src/checksums" + pyx,
    ],
)

pyfiletailmod = Extension(
    "pycurrents.file.pyfiletail",
    [
        "pycurrents/file/src/pyfiletail" + pyx,
        "pycurrents/file/src/filetail.c",
    ],
)

ringbufmod = Extension(
    "pycurrents.num.ringbuf",
    [
        "pycurrents/num/src/ringbuf" + pyx,
        "pycurrents/num/src/ringbufnan.c",
    ],
)

runstatsmod = Extension(
    "pycurrents.num.runstats",
    [
        "pycurrents/num/src/runstats" + pyx,
        "pycurrents/num/src/ringbufnan.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

glitchmod = Extension(
    "pycurrents.num.glitch",
    ["pycurrents/num/src/glitch" + pyx],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

swmod = Extension(
    "pycurrents.data._sw",
    ["pycurrents/data/src/_sw" + pyx],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

timemod = Extension(
    "pycurrents.data._time",
    [
        "pycurrents/data/src/_time" + pyx,
        "pycurrents/data/src/time_.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)


modemod = Extension(
    "pycurrents.data._modes",
    ["pycurrents/data/src/_modes" + pyx],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

utilitymod = Extension(
    "pycurrents.num.utility",
    [
        "pycurrents/num/src/utility" + pyx,
        "pycurrents/num/src/_pnpoly.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

medianmod = Extension(
    "pycurrents.num._median",
    [
        "pycurrents/num/src/_median" + pyx,
        "pycurrents/num/src/med_wirth.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

zgridmod = Extension(
    "pycurrents.num.zg",
    [
        "pycurrents/num/src/zg" + pyx,
        "pycurrents/num/src/msgmaker.c",
        "pycurrents/num/src/zgrid.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)
interp1mod = Extension(
    "pycurrents.num.int1",
    [
        "pycurrents/num/src/int1" + pyx,
        "pycurrents/num/src/interp1.c",
    ],
)


unistatmod = Extension(
    "pycurrents.ladcp.unistat",
    [
        "pycurrents/ladcp/src/unistat" + pyx,
        "pycurrents/ladcp/src/ustatp.c",
    ],
    include_dirs=[numpy.get_include()],
    define_macros=npy_macros,
)

ext_modules = [
    nbvelmod,
    transformmod,
    bottommod,
    checksumsmod,
    pyfiletailmod,
    ringbufmod,
    zgridmod,
    interp1mod,
    runstatsmod,
    glitchmod,
    utilitymod,
    swmod,
    timemod,
    modemod,
    medianmod,
    unistatmod,
]

ext_modules = cythonize(ext_modules, force=True, language_level=3)

scripts = glob.glob("pycurrents/scripts/*.py")

setup(
    name="pycurrents",
    packages=find_packages(),
    package_data={
        "pycurrents.adcpgui_qt.lib": ["images/*.png"],
        "pycurrents.adcp": ["templates/*", "templates/*/*", "templates/*/*/*"],
    },
    ext_modules=ext_modules,
    scripts=scripts,
    zip_safe=False,
)

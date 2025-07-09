'''
Module for accessing codas databases in python.  Numpy is required.

In most cases, functions and modules should be imported directly
from this module, not from the submodules in which they are
defined.

The following functions are always provided:

*    :func:`~pycurrents.codas._codas.to_day`:  convert y,m,d,h,m,s
     to decimal dday

*    :func:`~pycurrents.codas._codas.to_date`: convert decimal day
     and yearbase to y,m,d,h,m,s

*    :func:`~pycurrents.codas.to_datestring`: convert decimal day and
     yearbase to string, yyyy/mm/dd hh:mm:ss

If the codas library is found when pycurrents is installed, then the
following codas access functions will be provided:

*    :func:`~pycurrents.codas.tools.get_profiles`: extract profile
     data from CODAS db as a :class:`~pycurrents.codas.tools.ProcEns`

*    :func:`~pycurrents.codas.tools.get_txy`: extract profile
     time, lon, lat data from CODAS db as a
     :class:`~pycurrents.codas.tools.ProcEns`, but with no
     other profile data.

*    :func:`~pycurrents.codas.tools.dbname_from_path`: given either
     a dbname or a directory containing a db, return the dbname.
     This is used by *get_profiles* and *get_txy*, but may be
     useful by itself.

Classes provided with the codas library are:

*    :class:`~pycurrents.codas._codas.DB`: low-level interface to CODAS db
*    :class:`~pycurrents.codas.tools.ProcEns`: (Processed Ensembles)
            container for profile data from a CODAS db

'''


try:
    from pycurrents.codas._codas import DB, ProfileDict
    from pycurrents.codas._codas import to_day, to_date
    from pycurrents.codas._codas import CodasError, CodasRuntimeError
    from pycurrents.codas._codas import CodasRangeError
    from pycurrents.codas._codas import CodasRangeBeforeStart, CodasRangeAfterEnd
    from pycurrents.codas.codasmask import masked_codas, badval_dict
    from pycurrents.codas.tools import (ProcEns,
                                        get_profiles,
                                        get_txy,
                                        dbname_from_path)
except ImportError:
    from pycurrents.data.timetools import to_day, to_date


def to_datestring(yearbase, dday):
    """
    Given scalar dday, return a standard string version of the date
    and time; given a sequence of ddays, return a list of strings.
    """
    dfmt = '%4d/%02d/%02d %02d:%02d:%02d'
    dates = to_date(yearbase, dday)
    if dates.ndim == 1:
        return dfmt % tuple(dates)
    return [dfmt % tuple(d) for d in dates]

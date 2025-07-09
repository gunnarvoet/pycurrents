


from pycurrents.codas import DB
def binmaxdepth(dbname, bin, startdd=None, ndays=None, r=None):
    """
    Find the maximum depth of a given depth bin.

    bin is the 0-based index.

    The time range can be specified flexibly; for example,
    ndays = -3 yields the last three days.  See docstring for
    codas.DB.get_profile for details.
    """

    db = DB(dbname)
    r = db.get_range(startdd=startdd, ndays=ndays, r=r)
    z = db.get_variable('DEPTH', r=r, nbins = bin+1)
    return z[bin,:].max()


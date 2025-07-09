import os

from pycurrents.codas import get_profiles
from pycurrents.get_test_data import get_test_data_path

dbpath = os.path.join(get_test_data_path(), "codas_db/os38nb_py/aship")


def test_get_profiles_nbins():
    d_all = get_profiles(dbpath, ndays=1)
    assert len(d_all.dep) == 70
    d_1 = get_profiles(dbpath, ndays=1, nbins=1)
    assert len(d_1.dep) == 1
    assert d_1.depth_interval == d_all.depth_interval
    d_0 = get_profiles(dbpath, ndays=1, nbins=0)
    assert d_0.depth_interval == d_all.depth_interval

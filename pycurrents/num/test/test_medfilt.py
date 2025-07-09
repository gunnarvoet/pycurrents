
import numpy as np
from numpy.testing import assert_almost_equal

from pycurrents.num import Runstats

def test_medfilt():
    xx = np.arange(10, dtype=float)
    xx[5] = np.nan
    xx[7] = 20
    rs = Runstats(xx, 3)
    rsm = Runstats(np.ma.masked_invalid(xx), 3)
    print('original ndarray', repr(xx))
    expected = np.array([0.5, 1.0, 2.0, 3.0, 3.5,
                        5.0, 13.0, 8.0, 9.0, 8.5])
    assert_almost_equal(rs.medfilt(0), expected)
    assert_almost_equal(rsm.medfilt(0).filled(np.nan), expected)

    expected = np.arange(10, dtype=float)
    expected[7] = 20
    assert_almost_equal(rs.medfilt(40), expected)
    assert_almost_equal(rsm.medfilt(40).filled(np.nan), expected)

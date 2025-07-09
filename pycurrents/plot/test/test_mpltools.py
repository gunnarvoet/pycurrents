import pytest
from numpy.testing import assert_allclose, assert_equal
import numpy as np

from pycurrents.plot.mpltools import (boundaries,
    regrid_for_pcolor,)

def test_boundaries():
    centers = [0.5, 1, 2, 4]
    expected = np.array([0.25, 0.75, 1.5, 3, 5])
    result = boundaries(centers)
    assert_allclose(result, expected)

def test_regrid_for_pcolor():
    with pytest.raises(ValueError):
        regrid_for_pcolor(np.arange(3), np.arange(10))
    with pytest.raises(ValueError):
        regrid_for_pcolor(np.arange(3), np.random.rand(3, 2))
    with pytest.raises(ValueError):
        regrid_for_pcolor(np.arange(3), np.random.rand(2, 3), axis=0)
    x = [1, 2, 4, 5]
    x_expected = [0.5, 1.5, 3, 4.5, 5.5]
    c = np.random.rand(3, 4)
    x2, c2 = regrid_for_pcolor(x, c)
    assert_allclose(x2, x_expected)
    assert_equal(c, c2)

    x_expected = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    x2, c2 = regrid_for_pcolor(x, c, dx_max=1)
    assert_allclose(x2, x_expected)
    assert c2.shape == (3, 5)
    assert np.isnan(c2[:, 2]).all()

    c1 = c.T.copy()
    x3, c3 = regrid_for_pcolor(x, c1, dx_max=1, axis=0)
    assert_equal(x3, x2)
    assert_allclose(c3.T, c2)

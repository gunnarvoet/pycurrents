import pytest

import numpy as np
from numpy.testing import assert_array_almost_equal
from pycurrents.num import interp1

nx = 10
xold = np.arange(nx, dtype=float)
yold = xold ** 2
yold[5] = np.nan
yold2c = np.column_stack((yold, xold))
yold2r = np.vstack((yold, xold))
n2, n3 = 2, 3
yold32 = np.arange(nx * n2 * n3).reshape(n3, n2, nx)
yold31 = np.ascontiguousarray(yold32.swapaxes(2, 1))
yold30 = np.ascontiguousarray(yold32.T)
xnew = np.linspace(-1, 10, 17)

def test_1d():
    ynew = interp1(xold, yold, xnew)
    expected = np.interp(xnew, xold, yold, left=np.nan, right=np.nan)
    assert_array_almost_equal(ynew, expected)

def test_2d_c():
    ynew = interp1(xold, yold2c, xnew)
    func = lambda y: np.interp(xnew, xold, y, left=np.nan, right=np.nan)
    expected = np.apply_along_axis(func, 0, yold2c)
    assert_array_almost_equal(ynew, expected)

def test_2d_r():
    ynew = interp1(xold, yold2r, xnew, axis=1)
    func = lambda y: np.interp(xnew, xold, y, left=np.nan, right=np.nan)
    expected = np.apply_along_axis(func, 1, yold2r)
    assert_array_almost_equal(ynew, expected)

def test_masked_input_auto():
    ynew = interp1(xold, np.ma.masked_invalid(yold), xnew)
    assert np.ma.is_masked(ynew)

def test_forced_masked_output():
    ynew = interp1(xold, yold, xnew, masked=True)
    assert np.ma.is_masked(ynew)

def test_forced_nomask_output():
    ynew = interp1(xold, np.ma.masked_invalid(yold), xnew, masked=False)
    assert not np.ma.is_masked(ynew)

@pytest.mark.parametrize('axis,y', [(0, yold30), (1, yold31), (2, yold32)])
def test_3d(axis, y):
    func = lambda y: np.interp(xnew, xold, y, left=np.nan, right=np.nan)
    expected = np.apply_along_axis(func, axis, y)
    ynew = interp1(xold, y, xnew, axis=axis)
    assert_array_almost_equal(ynew, expected)

@pytest.mark.parametrize('axis,y', [(0, yold30), (1, yold31), (2, yold32)])
def test_3d_masked_x(axis, y):
    mxold = np.ma.array(xold, copy=True)
    mxold[1] = np.ma.masked
    mask = np.ma.getmaskarray(mxold)
    cxold = mxold.compressed()
    sl = [slice(None)] * y.ndim
    sl[axis] = ~mask
    cy = y[tuple(sl)]
    func = lambda y: np.interp(xnew, cxold, y, left=np.nan, right=np.nan)
    expected = np.apply_along_axis(func, axis, cy)
    ynew = interp1(mxold, y, xnew, axis=axis, masked=False)
    assert_array_almost_equal(ynew, expected)

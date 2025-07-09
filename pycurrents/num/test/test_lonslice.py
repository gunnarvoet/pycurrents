# TODO: add optional testing for xarray
# This could include writing a temporary netcdf file,
# then testing that the slicing works with netCDF4 and
# xarray.

import pytest

import numpy as np
from numpy.testing import assert_array_equal

from pycurrents.num import (lon_rangeslices,
                            lonslice_array,
                            lonslice_arrays)

lon1 = np.arange(6) * 60  # 0 ...300
lon2 = lon1 - 180         # -180 ...120

arr1 = np.arange(12).reshape(2, 6)
arr2 = np.hstack((arr1[:, 3:], arr1[:, :3]))

lims = [(-180, 90), (-60, -5), (-30, 35), (5, 90), (90, 260), (340, 80)]

@pytest.mark.parametrize('limits', lims)
def test_lon_rangeslices(limits):
    newlon1, _, _ = lon_rangeslices(lon1, limits)
    newlon2, _, _ = lon_rangeslices(lon2, limits)
    assert_array_equal(newlon1 % 360, newlon2 % 360)

@pytest.mark.parametrize('limits', lims)
def test_lon_rangeslices_with_step(limits):
    newlon1, _, _ = lon_rangeslices(lon1, limits, step=2)
    newlon2, _, _ = lon_rangeslices(lon2, limits, step=2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)

@pytest.mark.parametrize('limits', lims)
def test_lonslice(limits):
    newarr1, newlon1 = lonslice_array(arr1, lon1, limits)
    newarr2, newlon2 = lonslice_array(arr2, lon2, limits)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)

    newarr1, newlon1 = lonslice_array(arr1.T, lon1, limits, axis=0)
    newarr2, newlon2 = lonslice_array(arr2.T, lon2, limits, axis=0)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)

@pytest.mark.parametrize('limits', lims)
def test_lonslice_masked(limits):
    marr1 = np.ma.array(arr1)
    marr2 = np.ma.array(arr2)
    newarr1, newlon1 = lonslice_array(marr1, lon1, limits)
    newarr2, newlon2 = lonslice_array(marr2, lon2, limits)
    assert np.ma.isMA(newarr1)
    assert np.ma.isMA(newarr2)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)

    newarr1, newlon1 = lonslice_array(marr1.T, lon1, limits, axis=0)
    newarr2, newlon2 = lonslice_array(marr2.T, lon2, limits, axis=0)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)


@pytest.mark.parametrize('limits', lims)
def test_lonslice_latslice(limits):
    slices = (slice(1), None)  # Take the second row; leave as 2-D.
    newarr1, newlon1 = lonslice_array(arr1, lon1, limits, slices=slices)
    newarr2, newlon2 = lonslice_array(arr2, lon2, limits, slices=slices)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)
    assert newarr1.shape[0] == 1
    slices = (1, None)  #  Reduce to 1-D
    newarr1, _ = lonslice_array(arr1, lon1, limits, slices=slices)
    assert newarr1.ndim == 1

@pytest.mark.parametrize('limits', lims)
def test_lonslice_latslice_with_step(limits):
    slices = (slice(1), 2)  # Take the second row; leave as 2-D.
    newarr1, newlon1 = lonslice_array(arr1, lon1, limits, slices=slices)
    newarr2, newlon2 = lonslice_array(arr2, lon2, limits, slices=slices)
    assert_array_equal(newarr1, newarr2)
    assert_array_equal(newlon1 % 360, newlon2 % 360)
    assert newarr1.shape[0] == 1
    slices = (1, 2)  #  Reduce to 1-D
    newarr1, _ = lonslice_array(arr1, lon1, limits, slices=slices)
    assert newarr1.ndim == 1

@pytest.mark.parametrize('limits', lims)
def test_lonslice_arrays(limits):
    slices = (slice(1), None)  # Take the second row; leave as 2-D.
    (newarr1, newarr2), _ = lonslice_arrays((arr1, arr1), lon1, limits,
                                            slices=slices)
    assert_array_equal(newarr1, newarr2)

@pytest.mark.parametrize('limits', lims)
def test_lonslice_arrays_with_step(limits):
    slices = (slice(1), 2)  # Take the second row; leave as 2-D.
    (newarr1, newarr2), _ = lonslice_arrays((arr2, arr2), lon2, limits,
                                            slices=slices)
    assert_array_equal(newarr1, newarr2)


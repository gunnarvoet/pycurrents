import pytest
import numpy as np
from numpy.testing import assert_array_equal, assert_allclose
from pycurrents.adcp.transform import heading_rotate, rdi_xyz_enu, Transform


vel_arrays = [np.arange(4, dtype=float),
              np.arange(40, dtype=float).reshape(10, 4),
              np.arange(120, dtype=float).reshape(10, 3, 4),
              ]

nanvel_arrays = [vel.copy() for vel in vel_arrays]
for nvel in nanvel_arrays:
    if nvel.ndim == 1:
        nvel[:] = np.nan
    else:
        nvel[0] = np.nan

mvel_arrays = [np.ma.masked_invalid(v) for v in vel_arrays]

arrays = vel_arrays + nanvel_arrays + mvel_arrays
arrays3 = [a[..., :3] for a in arrays]

arrays34 = arrays3 + arrays

# In the following we test the most basic fuctionality: with variously
# dimensioned inputs, and with H, P, and R all zero, do we get outputs
# identical to the inputs?

@pytest.mark.parametrize("vel", arrays34)
def test_heading_scalar(vel):
    target = heading_rotate(vel, 0)
    assert_array_equal(vel, target)

@pytest.mark.parametrize("vel", arrays34)
def test_heading_array(vel):
    if vel.ndim > 1:
        heading = np.zeros((vel.shape[0]))
    else:
        heading = 0
    target = heading_rotate(vel, heading)
    assert_array_equal(vel, target)

@pytest.mark.parametrize("vel", arrays34)
def test_hpr_scalar(vel):
    target = rdi_xyz_enu(vel, 0, 0, 0)
    assert_array_equal(vel, target)

@pytest.mark.parametrize("vel", arrays34)
def test_hpr_array(vel):
    if vel.ndim > 1:
        heading = np.zeros((vel.shape[0]))
    else:
        heading = 0
    target = rdi_xyz_enu(vel, heading, heading, heading)
    assert_array_equal(vel, target)

# Higher-level smoke-test: can we go from beam to xyz and back?

@pytest.mark.parametrize("vel", arrays)
def test_Transform_roundtrip(vel):
    T = Transform()
    xyz = T.beam_to_xyz(vel)
    target = T.xyz_to_beam(xyz)
    assert_allclose(vel, target, atol=1e-8)
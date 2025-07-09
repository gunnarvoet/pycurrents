"""
Coordinate transforms for ADCP data
"""

import numpy as np
from pycurrents.adcp._transform import _heading_rotate, _heading_rotate_m
from pycurrents.adcp._transform import _hpr_rotate, _hpr_rotate_m

def _process_vel(vel, min_comps=2):
    vel = np.array(vel, dtype=np.float64, copy=True, subok=True)
    if vel.ndim == 0:
        raise ValueError("vel must have at least one dimension")
    velshape = vel.shape  # saved: original shape of vel
    if velshape[-1] < min_comps or velshape[-1] > 4:
        raise ValueError("vel.shape[-1] must be %s to 4; vel.shape is %s",
                         min_comps, velshape)
    if vel.ndim == 1:
        vel = vel.reshape(1,1,vel.shape[0])
    elif vel.ndim == 2:
        vel = vel.reshape(vel.shape[0], 1, vel.shape[1])
    return vel, velshape

def _process_attitude(att, name, vel, velshape):
    att = np.asanyarray(att, dtype=np.float64)
    if att.ndim > 1:
        raise ValueError("%s must be scalar or 1D array, but shape is %s",
                         name, att.shape)
    if att.ndim == 0:
        att = att.reshape(1)
    natt = att.shape[0]
    if natt != 1 and natt != vel.shape[0]:
        raise ValueError(
            "With vel.ndim > 1, %s must match first dimension of vel"
            " but %s.shape is %s and original vel.shape is %s",
              name, name, att.shape, velshape)
    att = np.broadcast_to(att, (vel.shape[0],), subok=True)
    return att

def heading_rotate(vel, heading):
    """
    Rotate a velocity or sequence of velocities by heading.

    vel is a sequence or array of entries, [u, v, ...],
    where u and v are optionally followed by w, e; that is, vel
    can have 2, 3, or 4 entries, and only the first two will
    be modified on output.  vel may be 1, 2, or 3-D.

    heading is a single value in degrees, or a 1-D sequence
    that must match the first dimension of vel if vel is 2-D or 3-D.

    The output is rotated *heading* degrees *Clockwise* from the
    input.

    The data ordering convention is that if vel is 3-D, the indices
    are time, depth, component; heading is assumed to be a
    constant or a time series, but not varying with depth.

    This is a wrapper around a cython function.
    """
    vel, velshape = _process_vel(vel)
    heading = _process_attitude(heading, "heading", vel, velshape)

    if np.ma.is_masked(vel) or np.ma.is_masked(heading):
        # If either input has masked values, use the fully masked function.
        velmask = np.ma.getmaskarray(vel).astype(np.int8)
        hmask = np.ma.getmaskarray(heading).astype(np.int8)
        velr, outmask = _heading_rotate_m(vel, heading, velmask, hmask)
        velr = np.ma.array(velr, mask=outmask)
    else:
        # If either input is a masked array with mask False,
        # strip off the mask, do the calculation,
        # and convert the output back into a masked array.
        maskout = np.ma.isMaskedArray(vel)
        if maskout:
            vel = vel.view(np.ndarray)
        if np.ma.isMaskedArray(heading):
            heading = heading.view(np.ndarray)
        velr = _heading_rotate(vel, heading)
        if maskout:
            velr = np.ma.asarray(velr)

    return velr.reshape(velshape)



# The following may get a name-change, and/or be brought inside
# the Transform class, since it is instrument-dependent.

def rdi_xyz_enu(vel, heading, pitch, roll, orientation='down', gimbal=False):
    """
    Transform a velocity or sequence from xyz to enu.

    vel is a sequence or array of entries, [u, v, w, ...],
    where u, v and w are optionally followed by e; that is, vel
    can have 3, or 4 entries, and only the first three will
    be modified on output.  vel may be 1, 2, or 3-D.

    heading is a single value in compass degrees, or a 1-D sequence
    that must match the first dimension of vel if vel is 2-D or 3-D.

    pitch and roll have the same constraints as heading.
    pitch is tilt1; roll is tilt2;

    gimbal = False (default) adjusts the raw pitch (tilt1) for the
    roll (tilt2), as appropriate for the internal sensor.

    The data ordering convention is that if vel is 3-D, the indices
    are time, depth, component; heading is assumed to be a
    constant or a time series, but not varying with depth.

    This is a wrapper around a cython function.
    """
    vel, velshape = _process_vel(vel, min_comps=3)
    heading = _process_attitude(heading, "heading", vel, velshape)
    pitch = _process_attitude(pitch, "pitch", vel, velshape)
    roll = _process_attitude(roll, "roll", vel, velshape)

    if (np.ma.is_masked(vel) or np.ma.is_masked(heading)
            or np.ma.is_masked(pitch) or np.ma.is_masked(roll)):
        # If any input has masked values, use the fully masked function.
        velmask = np.ma.getmaskarray(vel).astype(np.int8)
        hmask = np.ma.mask_or(np.ma.getmaskarray(roll),
                                np.ma.getmaskarray(pitch),
                                shrink=False)
        hmask = np.ma.mask_or(hmask, np.ma.getmaskarray(heading),
                                shrink=False)
        hmask = hmask.astype(np.int8) # cython 11.2 can't handle bool
        velr, outmask = _hpr_rotate_m(vel, heading, pitch, roll,
                                        velmask, hmask,
                                        orientation, gimbal)
        velr = np.ma.array(velr, mask=outmask)
    else:
        # If either input is a masked array with mask False,
        # strip off the mask, do the calculation,
        # and convert the output back into a masked array.
        maskout = np.ma.isMaskedArray(vel)
        if maskout:
            vel = vel.view(np.ndarray)
        if np.ma.isMaskedArray(heading):
            heading = heading.view(np.ndarray)  # or heading.data?
        if np.ma.isMaskedArray(pitch):
            pitch = pitch.view(np.ndarray)
        if np.ma.isMaskedArray(roll):
            roll = roll.view(np.ndarray)
        velr = _hpr_rotate(vel, heading, pitch, roll, orientation, gimbal)
        if maskout:
            velr = np.ma.asarray(velr)

    return velr.reshape(velshape)


class Transform:
    def __init__(self, angle=30, geometry='convex'):
        self.angle = angle
        self.geometry = geometry
        beam_angle = angle*np.pi/180
        a = 1/(2*np.sin(beam_angle))
        b = 1/(4*np.cos(beam_angle))
        d = a/np.sqrt(2)

        # We are starting with the Matlab version,
        # then transposing, for ease in writing the code.
        # This may change.
        # The Matlab version is different because of the
        # difference in storage order; in Matlab it is
        # natural to multiply the matrix times the beam
        # velocities, while in numpy the beams are incremented
        # by the last index, and np.dot(vel, matrix) is perfect.

        xyz_mat = np.array([[a, -a,  0,  0],
                            [0,  0, -a,  a],
                            [b,  b,  b,  b],
                            [d,  d, -d, -d]])

        if geometry != 'convex':
            xyz_mat[:2] = -xyz_mat[:2]

        self.to_xyz_mat = xyz_mat.T
        self.to_beam_mat = np.linalg.inv(xyz_mat.T)

    # np.dot operating on masked bvel passes the
    # mask through; we need to change the mask to
    # apply to whole rows instead. Ideally this should
    # all be handled by ma.dot, but as of numpy 1.4,
    # ma.dot is incomplete, and handles only 2-d arrays.
    @staticmethod
    def _propagate_mask(vel):
        if not np.ma.is_masked(vel):
            return vel
        mask = np.ma.getmaskarray(vel)
        rowmask = mask.sum(axis=-1).astype(bool)
        # The following step is needed to generate a new
        # mask for vel; otherwise its mask will be the same
        # array as the mask for the original bvel.
        vel = np.ma.array(vel.data, mask=mask.copy())
        if rowmask.ndim == 0:
            vel[:] = np.ma.masked
        else:
            vel[rowmask,:] = np.ma.masked
        return vel


    def _beam_to_xyz(self, bvel):
        xyze = np.dot(bvel, self.to_xyz_mat)
        return self._propagate_mask(xyze)

    def beam_to_xyz(self, bvel, ibad=None):
        if ibad is None:
            return self._beam_to_xyz(bvel)

        # 3-beam solution: fake the 4th beam, calculate
        # uvw, mask out e if bvel is a masked array
        bvel = bvel.copy()
        m = np.array([-1, -1, 1, 1])
        if ibad >= 2:
            m *= -1
        m[ibad] = 0
        bvel[...,ibad] = np.dot(bvel, m)
        xyze = self._beam_to_xyz(bvel)

        if np.ma.isMA(bvel):
            xyze[..., 3] = np.ma.masked

        return xyze

    def xyz_to_beam(self, vel):
        # If xyze resulted from 3-beam solutions, so e is masked,
        # fill the e values with 0 so that we can recover
        # 4 beam velocities. There is no way to figure out which
        # beam was omitted originally.
        if np.ma.is_masked(vel[..., -1]):
            vel = vel.copy()
            vel[..., -1] = np.ma.filled(vel[..., -1], 0)

        bvel = np.dot(vel, self.to_beam_mat)
        return self._propagate_mask(bvel)

def example():
    tr = Transform()
    v1 = np.zeros((4,), float)
    v1[0] = 0.5
    v1[1] = -0.5
    v1xyz = tr.beam_to_xyz(v1)
    v1xyzm = tr.beam_to_xyz(np.ma.array(v1, mask=[True, False, False, False]))
    print(v1xyz)
    print(v1xyzm)

    v2 = np.ma.ones((5,4), float)
    v2[0,0] = np.ma.masked
    v2xyzm = tr.beam_to_xyz(v2)
    print(v2xyzm)

    v3 = np.ma.ones((6,5,4), float)
    v3[..., 1] *= -1
    v3[0,0,0] = np.ma.masked
    v3xyzm = tr.beam_to_xyz(v3)
    print(v3xyzm)


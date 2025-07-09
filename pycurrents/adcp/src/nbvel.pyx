
import numpy as np
cimport numpy as np
np.import_array()

cdef extern from "nbspeedsubs.h":
    int avg_uv(unsigned char *s, int n, int i0, int i1, double Head,
                double *Uav, double *Vav)
    void unpack_velocity(unsigned char *buf, short int *v, int n)

def unpack_vel(np.ndarray vbuf, nbins):
    """
    vbuf must be a contiguous array.
    For the BT field in the Leader structured array,
    it is the caller's responsibility to use np.ascontiguousarray
    to transform it.
    """
    cdef np.ndarray _vout = np.empty((nbins, 4), dtype=np.int16)
    unpack_velocity(<unsigned char *>vbuf.data, <short int *>_vout.data, nbins)
    return _vout

def unpack_BT_vel(np.ndarray BT_vel):
    """
    We may not need this any more; it differs from unpack_vel
    only in that its input and output must be 1-D, a single set
    of 4 values.
    """
    cdef np.ndarray _vout = np.empty((4,), dtype=np.int16)
    unpack_velocity(<unsigned char *>BT_vel.data, <short int *>_vout.data, 1)
    return _vout

def unpack_leader_BCD(np.ndarray leader):
    """
    Unpack the first 8 bytes of the Leader in place,
    converting binary-coded decimal bytes to unsigned bytes.
    This is for the date and time numbers.
    """

    cdef unsigned char bcd
    cdef unsigned int i
    cdef unsigned char *buf = <unsigned char *> leader.data
    for 0 <= i < 8:
        bcd = buf[i]
        buf[i] = (bcd >> 4) * 10 + (bcd & 15)


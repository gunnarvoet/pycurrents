'''
Support for making masked arrays from ndarrays, using the
CODAS bad value to set the mask.

'''
import numpy as np

badval_dict = {np.int8: 0x7f,
               np.uint8: 0xff,
               np.int16: 0x7fff,
               np.uint16: 0xffff,
               np.int32: 0x7fffffff,
               np.uint32: 0xffffffff,
               np.float32: np.float32(1e38),
               np.float64: 1e38
               }

def masked_codas(a, nancheck=False):
    """
    Given an ndarray, *a*, return a masked array with
    CODAS bad values masked. If *nancheck* is *True*,
    any invalid values (nan or inf) will also be masked.

    The returned array is always a copy.
    """

    if a.dtype.kind == 'f':
        ret = np.ma.masked_greater(a, 1e37, copy=True)
        if nancheck:
            ret = np.ma.masked_invalid(ret, copy=False)
    else:
        ret = np.ma.masked_equal(a, badval_dict[a.dtype.type], copy=True)
    ret.set_fill_value(badval_dict[a.dtype.type])
    return ret



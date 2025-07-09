"""
Use npz format to save and restore masked arrays along with other variables.

The savez and load functions defined here are intended to be used
together as replacements for their numpy counterparts.
"""

import numpy as np

from pycurrents.system import Bunch

mfd_prefix = "__mfd__"
mfm_prefix = "__mfm__"

def savez(fname, **kw):
    """
    Save variables including masked arrays in compressed npz format.

    This is similar to np.savez, but it accepts input arrays only
    as kwargs, and it saves the data and the mask of masked arrays.
    The first argument must be a file name, not an open file or
    file-like object.

    Dictionary instances (such as Bunch) will be saved as plain
    dictionaries (pickled by np.savez) to make them more robust.
    Load will return all dictionaries as Bunch instances, for
    convenience.
    """
    mfiles = {}
    others = {}
    masks = {}
    for k, v in kw.items():
        if np.ma.isMA(v):
            mfiles[mfd_prefix + k] = v.data
            masks[mfm_prefix + k] =  v.mask
        else:
            if isinstance(v, dict):
                v = dict(v)
            others[k] = v

    others.update(mfiles)
    others.update(masks)
    fz = open(fname, "wb")
    np.savez_compressed(fz, **others)
    fz.close()

def load(fname):
    """
    Load an npz file written by savez, rebuilding masked arrays.

    This is similar to np.load, but it accepts only npz files,
    and it does not support memory mapping.  Its only argument
    is a file name; it does not accept a file or file-like object.

    It also unpacks variables that have been saved in zero-dimension
    ndarrays.

    Unlike np.load, which returns a dictionary-like object, this
    returns a Bunch.
    """
    fz = open(fname, "rb")
    z = np.load(fz, mmap_mode=None, encoding='bytes', allow_pickle=True)
    out = Bunch()
    for k, v in z.items():
        if k.startswith(mfd_prefix):
            kma = k[len(mfd_prefix):]
            kmm = mfm_prefix + kma
            out[kma] = np.ma.array(v, mask=z[kmm])
        elif k.startswith(mfm_prefix):
            continue
        else:
            if v.ndim == 0:
                v = v.item()
                if isinstance(v, dict):
                    v = Bunch(v)
            out[k] = v
    fz.close()

    return out


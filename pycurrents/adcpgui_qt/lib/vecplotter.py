# BREADCRUMB: common lib.

from pycurrents.adcp.dataplotter import vecplot as _vecplot


def vecplot(*args, **kw):
    colorblind = kw.pop("colorblind", False)
    vmap = _vecplot(*args, **kw)
    if hasattr(vmap, "mquiver") and colorblind:
        vmap.mquiver.set_cmap("plasma")
    return vmap

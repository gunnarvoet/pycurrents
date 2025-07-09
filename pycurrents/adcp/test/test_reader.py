import os
from pycurrents.adcp.reader import Binsuite
from pycurrents.get_test_data import get_test_data_path
import pytest
from pycurrents.adcp.reader import (
    matread_adcpsect, 
    get_adata, 
    DataGetError,
    timegrid_amp,
    get_dbname,
    calculate_fp,
    uhdasfile,
    vmdas,
    )

from contextlib import contextmanager

@contextmanager
def change_dir(new_dir):
    prev_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(prev_dir)

def test_binsuite_empty_init():
    with pytest.raises(ValueError) as ve:
        Binsuite()
    assert ve

def test_matread_adcpsect():
    fpath = os.path.join(
        get_test_data_path(), "uhdas_data/proc/os150nb/nav/a_hly_uv.mat"
    )
    data = matread_adcpsect("a_hly", os.path.dirname(fpath))

    u_data = data['u']
    v_data = data['v']

    assert data
    assert u_data is not None
    assert v_data is not None

def test_get_adata_matread():
    fpath = os.path.join(
        get_test_data_path(), "uhdas_data/proc/os150nb/nav/a_hly_uv.mat"
    )
    adata = get_adata("a_hly", os.path.dirname(fpath), read_fcn = 'adcpsect_mat')
    u_data = adata['u']
    v_data = adata['v']

    assert adata
    assert u_data is not None
    assert v_data is not None

def test_get_adata_codas():
    fpath = os.path.join(
        get_test_data_path(), "codas_db/os38nb_py"
    )
    adata = get_adata("aship", fpath, read_fcn = 'codasdb')
    u_data = adata.u
    v_data = adata.v

    assert adata
    assert u_data is not None
    assert v_data is not None

def test_get_adata_codas_fail():
    fpath = os.path.join(
        get_test_data_path(), "codas_db/os38nb_py"
    )

    with pytest.raises(DataGetError):
        get_adata("asp", fpath, read_fcn = 'codasdb')

def test_timegrid_amp():
    fpath = os.path.join(
        get_test_data_path(), "codas_db/os38nb_py"
    )
    adata = get_adata("aship", fpath, read_fcn = 'codasdb')
    
    timegrid_amps = timegrid_amp(adata)
    assert timegrid_amps


def test_get_dbname_empty():
    with pytest.raises(ValueError) as ve:
        get_dbname()
    assert ve
    

def test_get_dbname():
    fpath = os.path.join(
        get_test_data_path(), "uhdas_data/proc/os75nb/."
    )
    with change_dir(fpath):
        dbname = get_dbname()

    assert dbname
    assert os.path.basename(dbname) == "a_hly"
    
def test_calculate_fp():
    fpath = os.path.join(
        get_test_data_path(), "codas_db/os38nb_py"
    )
    adata = get_adata("aship", fpath, read_fcn = 'codasdb')
    f, p = calculate_fp(adata.u, adata.v, adata.heading)

    assert f is not None
    assert len(f) == 545
    assert p is not None
    assert len(p) == len(f)

def test_uhdasfile():
    fpath = os.path.join(
        get_test_data_path(), "uhdas_data/raw/os150/hly2018_149_64800.raw"
    )

    # must set beam angle
    try:
        adata = uhdasfile(fpath)
    except SystemExit as se:
        assert se

    # must set instrument
    try:
        adata = uhdasfile(fpath, beamangle=30)
    except SystemExit as se2:
        assert se2

    # must set heading allignment
    instrument = "os150"
    try:
        adata = uhdasfile(fpath,inst = instrument,  beamangle=30)
    except SystemExit as se3:
        assert se3

    #
    heading_align = 20.
    adata = uhdasfile(fpath,inst = instrument, h_align=heading_align , beamangle=30)
    u_data = adata.u
    v_data = adata.v

    assert adata
    assert u_data is not None
    assert v_data is not None

def test_vmdas_missing_attribute_trans():
    fpath = os.path.join(
        get_test_data_path(), "codas_db/os38nb_py"
    )
    adata = get_adata("aship", fpath, read_fcn = 'codasdb')

    vmdas_data = vmdas(adata)
    assert vmdas_data is None
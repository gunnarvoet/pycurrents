import os
from pycurrents.adcp.gbin import Gbinner
from pycurrents.get_test_data import get_test_data_path
import pytest

@pytest.fixture
def test_data_path():
    return get_test_data_path()

def test_gbin_minimal_init(test_data_path):
    fpath = os.path.join(test_data_path, "fake_path")
    gbinner = Gbinner(fpath, 'os150')
    assert gbinner

def test_gbin_with_config(test_data_path):
    class Config:
        pos_inst = "gpsnav"
        pos_msg = "gps"
        hdg_inst = "gyro"
        hdg_msg = "hdg"
        pitch_inst = "posmv"
        pitch_msg = "pmv"
        roll_inst = "posmv"
        roll_msg = "pmv"

    fpath = os.path.join(test_data_path, "fake_path")
    config = Config()
    gbinner = Gbinner(fpath, 'os150', config=config)
    assert gbinner.config == config


def test_gbin_make_best_gbin(test_data_path):
    class Config:
        pos_inst = "gpsnav"
        pos_msg = "gps"
        hdg_inst = "gyro"
        hdg_msg = "hdg"
        pitch_inst = "posmv"
        pitch_msg = "pmv"
        roll_inst = "posmv"
        roll_msg = "pmv"

    fpath = os.path.join(test_data_path, "fake_path")
    config = Config()
    gbinner = Gbinner(fpath, 'os150', config=config)
    try:
        gbinner.make_best_gbin()
    except Exception as e:
        pytest.fail(f"make_best_gbin raised an exception: {e}")

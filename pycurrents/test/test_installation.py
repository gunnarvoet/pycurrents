"""
Tests here are run by "runsetup.py --test" at the start to ensure
topography and test data can be found.
"""
import logging
from pycurrents.data.topo import Etopo_file
from pycurrents import get_test_data_path

def test_topo_dir():
    etopo_path = None
    try:
        etopo_path = Etopo_file()
    except IOError:
        print("Cannot find the ETOPO data for plotting.")
    assert etopo_path is not None

def test_data_dir():
    data_path = get_test_data_path()
    logging.debug(data_path)


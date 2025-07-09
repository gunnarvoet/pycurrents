import pytest
import os
from shutil import copytree
from io import StringIO
import sys
from contextlib import contextmanager

from pycurrents.scripts.plot_beam_cor_amp_vel import plot_beam_cor_amp_vel
from pycurrents.get_test_data import get_test_data_path
import matplotlib

matplotlib.use('Agg')  # Use the non-interactive backend for tests

@pytest.fixture(scope="session")
def uhdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_data')
    copytree(src, dst)
    return dst

@contextmanager
def capture_all_output(out_stream):
    prev_out, prev_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = out_stream
    try:
        yield
    finally:
        sys.stdout, sys.stderr = prev_out, prev_err

def test_plot_beam_cor_amp_vel(uhdas_dir, tmp_path):
    # Setup 
    capture_io_err = StringIO()
    input_raw_dir = os.path.join(uhdas_dir)
    save = True 
    save_file_loc = tmp_path / "test_plot.png" # should self clean
    allow_symbolic_links = False
    title = "Unit Test Title"
    debug_mode = False

    # Test
    with capture_all_output(capture_io_err):
        plot_beam_cor_amp_vel(input_raw_dir, save, save_file_loc, allow_symbolic_links, title, debug_mode)

    # Compare
    output = capture_io_err.getvalue()
    assert "dday range:" in output, "Failed to find expected string"

def test_plot_beam_cor_amp_vel_no_arguments_fail():
    
    with pytest.raises(TypeError) as exc_info:   
        plot_beam_cor_amp_vel()

    assert exc_info, "Type error expected but not thrown"
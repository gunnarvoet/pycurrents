from pycurrents.get_test_data import get_test_data_path
from contextlib import contextmanager
import os
from shutil import copytree
import pytest
from pycurrents.scripts.catxy import cat_xy
import sys
from io import StringIO

@pytest.fixture(scope="session")
def uhdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_data')
    copytree(src, dst)
    return dst

@contextmanager
def change_dir(new_dir):
    prev_dir = os.getcwd()
    os.chdir(new_dir)

    try:
        yield
    finally:
        os.chdir(prev_dir)

@contextmanager
def capture_all_output(out_stream):
    prev_out, prev_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = out_stream
    try:
        yield
    finally:
        sys.stdout, sys.stderr = prev_out, prev_err


def test_cat_wt(uhdas_dir):
    test_cat_wt_dir = os.path.join(uhdas_dir,"proc/os75nb")
    capture_io_err = StringIO()
    with change_dir(test_cat_wt_dir):
        with capture_all_output(capture_io_err):
            cat_xy()

    output = capture_io_err.getvalue()
    assert len(output) > 0, "Expected some output from uhdas_info"
    assert "positions from a_hly.agt" in output
    assert "calculation done at 2018/05/30 22:19:52" in output
    assert "xducer_dx = 5.717552" in output
    assert "xducer_dy = 6.499369" in output
    assert "signal = 498.663199" in output

def test_cat_wt_file_not_found(uhdas_dir):
    test_cat_wt_dir = os.path.join(uhdas_dir,"proc")
    capture_io_err = StringIO()
    with pytest.raises(FileNotFoundError) as exc_info:
        with change_dir(test_cat_wt_dir):
            with capture_all_output(capture_io_err):
                cat_xy()

    assert  "FileNotFound" in str(exc_info)
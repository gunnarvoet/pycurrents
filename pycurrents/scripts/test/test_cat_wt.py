from pycurrents.get_test_data import get_test_data_path
from contextlib import contextmanager
import os
from shutil import copytree
import pytest
from pycurrents.scripts.catwt import cat_wt
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
            cat_wt()

    output = capture_io_err.getvalue()
    assert len(output) > 0, "Expected some output from uhdas_info"
    assert "amplitude   1.0005   0.9985   0.0051" in output, "instead of expected line got something else"
    assert "phase      -0.2155  -0.2175   0.2435" in output, "instead of expected line got something else"

def test_cat_wt_file_not_found(uhdas_dir):
    test_cat_wt_dir = os.path.join(uhdas_dir,"proc")
    capture_io_err = StringIO()
    with pytest.raises(FileNotFoundError) as exc_info:
        with change_dir(test_cat_wt_dir):
            with capture_all_output(capture_io_err):
                cat_wt()

    assert  "FileNotFound" in str(exc_info)
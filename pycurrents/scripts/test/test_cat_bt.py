from pycurrents.get_test_data import get_test_data_path
from contextlib import contextmanager
import os
from shutil import copytree
import pytest
from pycurrents.scripts.catbt import cat_bt
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


def test_cat_bt_file_not_found(uhdas_dir):
    test_cat_wt_dir = os.path.join(uhdas_dir,"proc")
    capture_io_err = StringIO()
    with pytest.raises(FileNotFoundError) as exc_info:
        with change_dir(test_cat_wt_dir):
            with capture_all_output(capture_io_err):
                cat_bt()

    assert  "FileNotFound" in str(exc_info)

# TODO this uhdas test doesnt collect bottom track data.  We need a working example.
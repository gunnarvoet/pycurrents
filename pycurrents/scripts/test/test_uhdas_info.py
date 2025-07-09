# scripts are a pain to test
import subprocess
import pytest
from pathlib import Path
import os
from io import StringIO
from shutil import copytree
import sys
from contextlib import contextmanager
from argparse import Namespace

from pycurrents.scripts.uhdas_info import uhdas_info
from pycurrents.get_test_data import get_test_data_path

@pytest.fixture
def my_script_path():
    return Path("pycurrents/scripts/uhdas_info.py").resolve()

@pytest.fixture(scope="session")
def uhdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_data')
    copytree(src, dst)
    return dst



@contextmanager
def capture_string_io(new_loc):
    prev_dir = sys.stderr
    sys.stderr = new_loc
    try:
        yield
    finally:
        sys.stderr = prev_dir

def test_no_args(my_script_path):
    result = subprocess.run(
        ["python", my_script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )

    assert len(result.stdout) > 0, "This script should produce stdout"
    assert result.returncode == 0, f"Script fails to prints docs on no args: {result.stderr}"

def test_working_script_run(my_script_path, uhdas_dir):
    result = subprocess.run(
        ["python", my_script_path, '--overview', uhdas_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    #loggers by default print to stderr 
    output = result.stderr.splitlines()
    assert len(output) > 0, f"This script should produce stderr. {output}"
    assert result.returncode == 0, f"Script fails to run: {output}"
    assert "149.475 - 149.930 (2018/05/30 to 2018/05/30)" in output[-3]
    assert "end of report" in output[-1]

def test_working_function(uhdas_dir):
    capture_io_err = StringIO()
    with capture_string_io(capture_io_err):
        options = Namespace(
            all=True,
            overview = True,
            settings = True,
            cals = True,
            serial = True,
            time = True,
            rbintimes = True,
            rbincheck = True,
            logfile = None,
            clockcheck = True,
            gaps = True
        ) 
        uhdas_info(options, [uhdas_dir])

    output = capture_io_err.getvalue().splitlines()
    assert len(output) > 0, "Expected some output from uhdas_info"
    assert "$INGGA, $PSXN,20, $PSXN,23" in output[-2]
    assert "end of report" in output[-1]
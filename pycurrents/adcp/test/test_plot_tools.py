import os
import subprocess
import pytest
from shutil import copytree, rmtree, copyfile
from glob import glob
from pycurrents.get_test_data import get_test_data_path
from contextlib import contextmanager

# FIXME: use image comparison or pytest-mpl for the Matplotlib related parts
#        see: https://github.com/matplotlib/pytest-mpl?files=1
#        see: https://matplotlib.org/1.3.0/devel/testing.html

# FIXME: these tools GUI based. Needs qtbot and/or refactoring in order to be tested
#        List of GUI based tools:
#           - txyselect.py
#           - txyzoom.py BROKEN
# FIXME: use pytest-qt and qtbot to really test the GUI/Qt related parts
#        see: http://pytest-qt.readthedocs.io/en/latest/intro.html


### Fixtures ###
OUTPUT_FOLDER = os.path.join(os.getcwd(), 'test_figures')
if os.path.exists(OUTPUT_FOLDER):
    rmtree(OUTPUT_FOLDER)
os.mkdir(OUTPUT_FOLDER)


@ pytest.fixture(scope="session")
def uhdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_data')
    copytree(src, dst)
    return dst


@ pytest.fixture(scope="session")
def vmdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'vmdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('vmdas_data')
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


# Test Units
def test_vmdas_plot_lta(tmpdir, vmdas_dir):
    with change_dir(tmpdir):
        ### LTA
        lta_files = os.path.join(vmdas_dir, "os75", "*.LTA")
        # Running command
        cmd_line = "vmdas_quick_ltaproc.py --cruisename test_lta %s" % lta_files
        subprocess.check_output(cmd_line, shell=True)

        # Collect *.png and save them to OUTPUT_FOLDER/lta/
        images = []
        for dirpath, dirnames, filenames in os.walk(tmpdir, topdown=False):
            for fn in filenames:
                if fn.lower().endswith(".png"):
                    src = os.path.join(os.path.abspath(dirpath), fn)
                    dst = os.path.join(OUTPUT_FOLDER, fn)
                    copyfile(src, dst)
                    images.append(fn)
    # Testing
    assert len(images) == 23


def test_quick_mplplots(uhdas_dir):
    proc_dir = os.path.join(uhdas_dir, "proc", "os150bb")
    rotate_dir = os.path.join(proc_dir, "cal", "rotate")
    water_trk_dir = os.path.join(proc_dir, "cal", "watertrk")
    nav_dir = os.path.join(proc_dir, "nav")
    edit_dir = os.path.join(proc_dir, "edit")
    # Png list beforehand
    png_list = glob(os.path.join(rotate_dir, '*.png'))
    png_list += glob(os.path.join(water_trk_dir, '*.png'))
    png_list += glob(os.path.join(nav_dir, '*.png'))
    png_list += glob(os.path.join(edit_dir, '*.png'))
    assert len(png_list) == 8
    for png in png_list:
        os.remove(png)
    # Run command
    with change_dir(proc_dir):
        cmd_line = "quick_mplplots.py --yearbase 2018 --plots2run all --noshow"
        subprocess.check_output(cmd_line, shell=True)
        # Png list afterwards
        png_list = glob(os.path.join(rotate_dir, '*.png'))
        assert len(png_list) == 1
        assert "ens_hcorr_mpl_149.png" in png_list[0]
        png_list = sorted(glob(os.path.join(water_trk_dir, '*.png')))
        assert len(png_list) == 2
        assert "wtcal1.png" in png_list[0]
        assert "wtcal2.png" in png_list[1]
        png_list = sorted(glob(os.path.join(nav_dir, '*.png')))
        assert len(png_list) == 3
        assert "nav_plot.png" in png_list[0]
        assert "reflayer_149.png" in png_list[1]
        assert "uvship_plot.png" in png_list[2]
        png_list = sorted(glob(os.path.join(edit_dir, '*.png')))
        assert len(png_list) == 2
        assert "nping_plot.png" in png_list[0]
        assert "temp_plot.png" in png_list[1]
        # Copy to output folder
        png_list = glob(os.path.join(rotate_dir, '*.png'))
        png_list += glob(os.path.join(water_trk_dir, '*.png'))
        png_list += glob(os.path.join(nav_dir, '*.png'))
        png_list += glob(os.path.join(edit_dir, '*.png'))
        for png in png_list:
            os.rename(png, os.path.join(
                OUTPUT_FOLDER, os.path.basename(png)))


def test_plot_nav(uhdas_dir):
    nav_dir = os.path.join(uhdas_dir, "proc", "os75nb/nav")
    # Png list beforehand
    png_list = glob(os.path.join(nav_dir, '*.png'))
    assert len(png_list) == 3
    for png in png_list:
        os.remove(png)
    # Run command
    with change_dir(nav_dir):
        # FIXME: no --outfile function here...refactor
        cmd_line = "plot_nav.py a_hly.gps --savefigs"
        subprocess.check_output(cmd_line, shell=True)
        # Png list afterwards
        png_list = glob(os.path.join(nav_dir, '*.png'))
        assert len(png_list) == 1
        assert "navplot_000.png" in png_list[0]
        # Copy to output folder
        os.rename(png_list[0], os.path.join(
            OUTPUT_FOLDER, os.path.basename(png_list[0])))


def test_plot_rnav(uhdas_dir):
    gps_dir = os.path.join(uhdas_dir, "rbin/gpsnav")
    with change_dir(gps_dir):
        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_rnav.py *.gps.rbin --noshow --outfile %s/test1" % OUTPUT_FOLDER
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 2


def test_plot_pashr(uhdas_dir):
    pmv_dir = os.path.join(uhdas_dir, "rbin/posmv")
    with change_dir(pmv_dir):

        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_pashr.py *.pmv.rbin --noshow --outfile %s/test2" % OUTPUT_FOLDER
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 1


def test_plot_posmv(uhdas_dir):
    pmv_dir = os.path.join(uhdas_dir, "rbin/posmv")
    with change_dir(pmv_dir):

        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_posmv.py --outfile %s/test4 --noshow ./" % OUTPUT_FOLDER
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 1


def test_plot_hbin(uhdas_dir):
    with change_dir(uhdas_dir):
        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_hbins.py --outfile %s/test5 --noshow ./" % OUTPUT_FOLDER
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 1


def test_plot_rawadcp(uhdas_dir):
    raw_dir = os.path.join(uhdas_dir, "raw/os75")
    with change_dir(raw_dir):

        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_rawadcp.py --pingtype nb --var amp os --outfile %s/test6 --noshow hly2018_149_72000.raw" % OUTPUT_FOLDER
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 1


def test_plotnav(uhdas_dir):
    nav_dir = os.path.join(uhdas_dir, "proc/os150bb/nav")
    with change_dir(nav_dir):
        pngs = glob(os.path.join(nav_dir, "*.png"))
        for png in pngs:
            os.remove(png)
        assert glob(os.path.join(nav_dir, "*.png")) == []

        # FIXME: no --outfile option here. No can save figures to OUTPUT_FOLDER
        #        without adding lines...refactoring might be more appropriate
        # Remake plots
        cmd_line = "plot_nav.py --savefigs a_hly.gps"
        subprocess.check_output(cmd_line, shell=True)
        assert len(glob(os.path.join(nav_dir, "*.png"))) == 1


def test_plot_reflayer(uhdas_dir):
    with change_dir(uhdas_dir):
        dbpath1 = os.path.join(uhdas_dir, "proc", "os75nb", "adcpdb")
        dbpath2 = os.path.join(uhdas_dir, "proc", "os150nb", "adcpdb")
        cmd_line = "plot_reflayer.py %s %s" % (dbpath1, dbpath2)

        # Baseline
        baseline = len(glob(os.path.join(OUTPUT_FOLDER, "*.png")))

        # Run script no show
        cmd_line = "plot_reflayer.py --outbase %s/test7 %s %s" % (
            OUTPUT_FOLDER, dbpath1, dbpath2)
        subprocess.check_output(cmd_line, shell=True)

        # Testing so created pngs
        pngs = glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        assert len(pngs) == baseline + 1



import os
import subprocess
import pytest
from glob import glob
from shutil import copytree
from netCDF4 import Dataset
from scipy.io import loadmat
from numpy import nanmean
import numpy as np
from numpy.testing import assert_allclose
from pycurrents.codas import get_profiles
from pycurrents.adcp.quick_adcp import get_opts, quick_adcp_core
from pycurrents.adcp.quick_setup import quickFatalError
from pycurrents.get_test_data import get_test_data_path
from pycurrents.adcp.vmdas import VmdasNavInfo
from pycurrents.adcp.vmdas import FakeUHDAS
from contextlib import contextmanager


### Fixtures ###
@ pytest.fixture(scope="session")
def uhdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_data')
    copytree(src, dst)
    return dst


@ pytest.fixture(scope="session")
def codas_db_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'codas_db')
    dst = tmpdir_factory.mktemp('test_data').join('codas_db')
    copytree(src, dst)
    return dst


@ pytest.fixture(scope="session")
def vmdas_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'vmdas_data')
    dst = tmpdir_factory.mktemp('test_data').join('vmdas_data')
    copytree(src, dst)
    return dst


@ pytest.fixture(scope="session")
def uhdas_style_dir(tmpdir_factory):
    src = os.path.join(get_test_data_path(), 'uhdas_style_data')
    dst = tmpdir_factory.mktemp('test_data').join('uhdas_style_data')
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

### Test Units ###
# - Testing command line Tools
# see https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/quick_web/index.html
# FIXME: add 2 legged cruise in pycurrents_test_data in order to
#        def test_link_uhdaslegs()
def test_mk_rbin(tmpdir, uhdas_dir):
    with change_dir(uhdas_dir):
        cmd_line = "mk_rbin.py -d ./ -o %s -y 2018" % (tmpdir)
        subprocess.check_output(cmd_line, shell=True)
        list_dir = sorted(os.listdir(tmpdir))
        assert list_dir == ['abxtwo', 'gpsnav', 'gyro27', 'gyro39', 'posmv', 'seapath']
        posmv_dir = os.path.join(tmpdir, 'posmv')
        seapath_dir = os.path.join(tmpdir, 'seapath')
        gpsnav_dir = os.path.join(tmpdir, 'gpsnav')

        # Testing files number and disk usage
        list_files = sorted(os.listdir(posmv_dir))
        assert len(list_files) == 14
        assert os.stat(os.path.join(posmv_dir, list_files[0])).st_size == 272884
        list_files = sorted(os.listdir(seapath_dir))
        assert len(list_files) == 14
        assert os.stat(os.path.join(seapath_dir, list_files[0])).st_size == 136468
        list_files = sorted(os.listdir(gpsnav_dir))
        assert len(list_files) == 7
        assert os.stat(os.path.join(gpsnav_dir, list_files[0])).st_size == 136468


def test_today_todate():
    cmd_line = "to_day 1970    2015 5 18 8 30 00"
    result = subprocess.check_output(cmd_line, shell=True)
    assert result == b'16573.35416667\n'
    cmd_line = "to_date 2015 137.354"
    result = subprocess.check_output(cmd_line, shell=True)
    assert result == b'2015/05/18  08:29:45.60\n'


# FIXME: move this to a uhdas test suite; that's where showlast.py lives.
def _t_showlast(uhdas_dir, uhdas_style_dir):
    raw_data1 = uhdas_dir
    raw_data2 = os.path.join(uhdas_style_dir, 'uhdas_style_data/ps_ridge_os75')

    cmd_line = "showlast.py -a 1 -l 1 -r 1 -g 1 %s" % raw_data1
    result = subprocess.check_output(cmd_line, shell=True)
    assert b"1493080" in result
    assert b"515062" in result
    assert b"38266" in result
    assert b"17696" in result
    assert b"5323" in result
    assert b"hly2018_149_79200.raw" in result
    assert b"hly2018_149_79200.pmv" in result
    assert b"hly2018_149_79200.hdg.rbin" in result
    assert b"hly2018_149_79200.tim.gbin" in result
    assert b"hly2018_149_79200.hdg.gbin" in result

    cmd_line = "showlast.py -a 1 -l 1 -r 1 -g 1 %s" % raw_data2
    result = subprocess.check_output(cmd_line, shell=True)
    assert b"83604" in result
    assert b"3325140" in result
    assert b"41794" in result
    assert b"27867" in result
    assert b"13941" in result
    assert b"zzz2009_264_83609.raw.log.bin" in result
    assert b"zzz2009_264_83609.raw" in result
    assert b"zzz2009_264_83609.hdg.rbin" in result
    assert b"zzz2009_264_83609.hdg.gbin" in result
    assert b"zzz2009_264_83609.hbin" in result


def test_EA_estimator(uhdas_dir, uhdas_style_dir, vmdas_dir):
    raw_dir1 = os.path.join(
        uhdas_style_dir, 'uhdas_style_data/ps_ridge_os75/raw/os75/*.raw')
    raw_dir2 = os.path.join(uhdas_dir, 'raw/os150/*.raw')
    enr_dir = os.path.join(vmdas_dir, 'os75/*.ENR')

    cmd_line = "EA_estimator.py os %s" % raw_dir1
    result = subprocess.check_output(cmd_line, shell=True)
    assert b"0.77    4.02   463" in result
    assert b"-0.05    2.13   193" in result

    cmd_line = "EA_estimator.py os %s" % raw_dir2
    result = subprocess.check_output(cmd_line, shell=True)
    assert b"29.36    2.84   192" in result
    assert b"no bottom track data found" in result

    cmd_line = "EA_estimator.py os %s" % enr_dir
    result = subprocess.check_output(cmd_line, shell=True)
    assert b"0.77    4.02   463" in result
    assert b"-0.05    2.13   193" in result


# - Testing tools used in post-processing tuto.
def test_make_outputs(uhdas_dir):
    """Testing adcp_nc.py"""
    proc_dir = os.path.join(uhdas_dir, "proc", "os75bb")
    contour_dir = os.path.join(proc_dir, "contour")
    with change_dir(proc_dir):
        # Remove existing Netcdf & Matlab files
        netcdf_list = glob(os.path.join(contour_dir, "*.nc"))
        matfile_list = glob(os.path.join(contour_dir, "*.mat"))
        for netcdf in netcdf_list:
            os.remove(netcdf)
        for matfile in matfile_list:
            os.remove(matfile)
        # - sanity checks
        netcdf_list = glob(os.path.join(contour_dir, "*.nc"))
        matfile_list = glob(os.path.join(contour_dir, "*.mat"))
        assert len(netcdf_list) == 0
        assert len(matfile_list) == 0

        # Making Netcdf products
        cmd_line = "adcp_nc.py adcpdb contour/os75bb test_cruise os75bb --ship_name Healy"
        result = subprocess.check_output(cmd_line, shell=True)
        # - testing file list
        netcdf_list = glob(os.path.join(contour_dir, "*.nc"))
        assert "os75bb.nc" in netcdf_list[0]
        # - testing content
        nc = Dataset(os.path.join(contour_dir, "os75bb.nc"))
        assert list(nc.variables.keys()).sort() == [
            'trajectory', 'time', 'lon', 'lat', 'depth', 'u', 'v', 'amp', 'pg',
            'pflag', 'heading', 'tr_temp', 'num_pings', 'uship', 'vship'].sort()
        assert round(float(nc.variables['u'].data_max), 6) == 0.195715
        assert round(float(nc.variables['u'].data_min), 6) == -0.887673
        assert round(float(nc.variables['v'].data_max), 6) == 0.271348
        assert round(float(nc.variables['v'].data_min), 6) == -0.342139
        assert round(float(nc.variables['heading'].data_max), 6) == 178.823547
        assert round(float(nc.variables['heading'].data_min), 6) == -169.088364

        # Making Matlab products
        cmd_line = "quick_adcp.py --steps2rerun matfiles --auto"
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None
        # - testing file list
        matfile_list = [os.path.basename(f)
                        for f in glob(os.path.join(contour_dir, "*.mat"))]
        assert matfile_list.sort() == [
            'allbins_bt.mat', 'allbins_tseries_stats.mat', 'allbins_pf.mat',
            'allbins_other.mat', 'allbins_resid_stats.mat', 'allbins_u.mat',
            'allbins_v.mat', 'allbins_w.mat', 'contour_uv.mat', 'allbins_depth.mat',
            'allbins_e.mat', 'allbins_tseries_diffstats.mat', 'allbins_sw.mat',
            'allbins_raw_amp.mat', 'allbins_pg.mat', 'contour_xy.mat',
            'allbins_amp.mat'].sort()
        # - testing content
        u_comp = loadmat(os.path.join(contour_dir, "allbins_u.mat"))
        v_comp = loadmat(os.path.join(contour_dir, "allbins_v.mat"))
        assert round(float(nanmean(u_comp['U'])), 6) == 0.161465
        assert round(float(nanmean(v_comp['V'])), 6) == 0.050301


def test_uhdas_info(uhdas_dir):
    with change_dir(uhdas_dir):
        # Overview
        # FIXME: use subprocess consistently
        os.system("uhdas_info.py --overview ./  --logfile ./overview.txt")
        with open("./overview.txt", 'r') as file:
            overview = file.read()
        assert "adcp:  os150    .raw.log.bin     7 files  (hly2018_149_40762 - hly2018_149_79200)" in overview
        assert "proc:     os75bb       149.475 - 149.930 (2018/05/30 to 2018/05/30)" in overview

        # Settings
        os.system("uhdas_info.py --settings ./  --logfile ./settings.txt")
        with open("./settings.txt", 'r') as file:
            settings = file.read()
        assert "0  7    149.471815  149.933244   off   (bb, 80, 4.0, 7.0, 4.0)   (nb, 40, 8.0, 7.0, 8.0)" in settings
        assert "0  7    149.471833  149.933219   off   (bb, 80, 8.0, 8.0, 8.0)   (nb, 40, 16.0, 8.0, 16.0)" in settings

        # Cals.
        os.system("uhdas_info.py --cals ./  --logfile ./cals.txt")
        with open("./cals.txt", 'r') as file:
            cals = file.read()
        assert "cal: os75nb   WT  phase      -0.2155  -0.2175   0.2435" in cals
        assert "cal: os75nb   WT  amplitude   1.0005   0.9985   0.0051" in cals
        assert "cal: os75nb   DXDY  xducer_dy = 6.499369" in cals
        assert "cal: os75nb   DXDY  xducer_dx = 5.717552" in cals
        assert "cal: os150bb   WT  amplitude   1.0240   1.0181   0.0168" in cals
        assert "cal: os150bb   WT  phase       0.3200   0.5880   0.6953" in cals
        assert "cal: os150bb   DXDY  xducer_dx = 6.513306" in cals
        assert "cal: os150bb   DXDY  xducer_dy = 4.468327" in cals

        # Gaps
        os.system("uhdas_info.py --gaps ./  --logfile ./gaps.txt")
        with open("./gaps.txt", 'r') as file:
            gaps = file.read()
        assert "proc:     os75nb       149.475 - 149.930 (2018/05/30 to 2018/05/30)" in gaps

        # Time
        os.system("uhdas_info.py --time ./  --logfile ./time.txt")
        with open("./time.txt", 'r') as file:
            times = file.read()
        assert "clock: os150 last data: clock diff (UTC-PC) = -0.27 sec" in times
        assert "gbin:  os150 gbin-codas UTC starting difference  =  4.9914 min" in times
        assert "gbin:   os75 gbin-codas UTC ending   difference  = -0.4118 min" in times
        assert "gbin:   os75: gbin data and processed data duration differ by 5.39 min" in times

        # rbintimes
        os.system("uhdas_info.py --rbintimes ./  --logfile ./rbintime.txt")
        with open("./rbintime.txt", 'r') as file:
            rbintimes = file.read()
        assert "u_dday   44304    0.90    0.82       1.0       0     0     0     0     0" in rbintimes
        assert "dday     78205    0.50    0.50      45.0      19     0     0     0     0" in rbintimes
        assert "m_dday   78203    0.50    0.14      45.4      19    14     0     0     0" in rbintimes
        assert "m_dday   39869    1.00    0.99       1.0       0     0     0     0     0" in rbintimes

        # rbincheck
        os.system("uhdas_info.py --rbincheck ./  --logfile ./rbincheck.txt")
        with open("./rbincheck.txt", 'r') as file:
            rbincheck = file.read()
        assert "rbin: WARNING    7    seapath files with mismatched messages" in rbincheck
        assert "rbin: INFO    0      posmv files with mismatched messages" in rbincheck
        assert "lines: INFO raw/./raw/seapath/hly2018_149_40762.sea has 7308 pairs" in rbincheck
        assert "lines: INFO raw/./raw/abxtwo/hly2018_149_50400.adu has 21562 pairs" in rbincheck

        # Clock check
        # TODO: fix...this command does not work
        # os.system("uhdas_info.py --clockcheck ./  --logfile ./rbincheck.txt")

        # Serial
        os.system("uhdas_info.py --serial ./  --logfile ./serial.txt")
        with open("./serial.txt", 'r') as file:
            serial = file.read()
        assert "serial:       abxtwo: translated raw serial ($GPGGA, $GPHDT, $PASHR,ATT) into rbins (adu, gps, hdg)" in serial
        assert "serial:       gpsnav: translated raw serial ($GPGGA) into rbins (gps)" in serial
        assert "serial:       gyro27: translated raw serial ($HEHDT) into rbins (hdg)" in serial
        assert "serial:       gyro39: translated raw serial ($INHDT) into rbins (hdg)" in serial
        assert "serial:        posmv: translated raw serial ($INGGA, $PASHR) into rbins (gps, pmv)" in serial
        assert "serial:      seapath: translated raw serial ($INGGA, $PSXN,20, $PSXN,23) into rbins (gps, sea)" in serial


def test_quick_adcp(uhdas_dir):
    import matplotlib
    matplotlib.rcParams['figure.max_open_warning'] = -1

    sonars = [
        'os150nb',
        'os150bb',
        'os75nb',
        'os75bb',
    ]

    orig_amp_lines = [
        "amplitude   1.0080   1.0059   0.0114\n",
        "amplitude   1.0240   1.0181   0.0168\n",
        "amplitude   1.0005   0.9985   0.0051\n",
        "amplitude   1.0030   1.0022   0.0062\n",
    ]
    expt_amp_lines = [
        "amplitude   1.0000   0.9980   0.0114\n",
        "amplitude   1.0160   1.0097   0.0175\n",
        "amplitude   0.9925   0.9910   0.0048\n",
        "amplitude   0.9950   0.9943   0.0056\n",
    ]
    edge_amp_lines = [
        "amplitude      nan      nan  -0.0000\n",
        "amplitude      nan      nan  -0.0000\n",
        "amplitude      nan      nan  -0.0000\n",
        "amplitude      nan      nan  -0.0000\n",
    ]

    orig_phase_lines = [
        "phase       0.0485   0.2507   0.5363\n",
        "phase       0.3200   0.5880   0.6953\n",
        "phase      -0.2155  -0.2175   0.2435\n",
        "phase       0.1820  -0.0708   0.7243\n",
    ]
    expt_phase_lines = [
        "phase      -0.1970   0.0023   0.5336\n",
        "phase       0.0690   0.3411   0.6967\n",
        "phase      -0.4715  -0.4715   0.2387\n",
        "phase      -0.0745  -0.3273   0.7183\n",
    ]
    edge_phase_lines = [
        "phase          nan      nan  -0.0000\n",
        "phase          nan      nan  -0.0000\n",
        "phase          nan      nan  -0.0000\n",
        "phase          nan      nan  -0.0000\n",
    ]

    orig_mean_u = [
        -0.03508,
        -0.03987,
        -0.04315,
        -0.05438,
    ]
    expt_mean_u = [
        -0.03265,
        -0.03712,
        -0.04227,
        -0.05554,
    ]
    edge_mean_u = [
        -1.60463,
        -1.05085,
        -1.17997,
        -2.9723,
    ]

    for (sonar,
         orig_amp, orig_phase, orig_u,
         expt_amp, expt_phase, expt_u,
         edge_amp, edge_phase, edge_u) in zip(
            sonars,
            orig_amp_lines, orig_phase_lines, orig_mean_u,
            expt_amp_lines, expt_phase_lines, expt_mean_u,
            edge_amp_lines, edge_phase_lines, edge_mean_u):
        # Line indexes & block size
        amp_line_index = 12
        phase_line_index = 13
        nb_lines_cal_block = 20

        # - Edge test...from the wrong location
        with change_dir(uhdas_dir):
            with pytest.raises(quickFatalError) as pytest_wrapped_e:
                opts = get_opts(['--steps2rerun', 'calib', '--auto'])
                quick_adcp_core(opts)
            assert "Are you starting in the right directory?" in str(pytest_wrapped_e.value)

            # - Move the right location
            sonar_dir = os.path.join(uhdas_dir, "proc", sonar)
            cals_file = os.path.join(sonar_dir, 'cal/watertrk/adcpcal.out')
            db_path = os.path.join(sonar_dir, 'adcpdb')

        with change_dir(sonar_dir):
            # - check original values
            with open(cals_file, 'r') as file:
                cals = file.readlines()
            #  * in cals
            assert orig_amp == cals[amp_line_index]
            assert orig_phase == cals[phase_line_index]
            #  * in DB
            data = get_profiles(db_path)
            assert round(data.u.mean(), 5) == orig_u
            # - now let's modify the data and check again
            opts = get_opts(['--steps2rerun',  'rotate:apply_edit:navsteps:calib',
                            '--rotate_amplitude', '1.008',
                            '--rotate_angle', '0.25',
                            '--auto'])
            quick_adcp_core(opts)
            with open(cals_file, 'r') as file:
                cals = file.readlines()
            amp_line_index += nb_lines_cal_block
            phase_line_index += nb_lines_cal_block
            #  * in cals
            assert expt_amp == cals[amp_line_index]
            assert expt_phase == cals[phase_line_index]
            #  * in DB
            data = get_profiles(db_path)
            assert round(data.u.mean(), 5) == expt_u
            # - now let's push to the edge and check again
            opts = get_opts(['--steps2rerun', 'rotate:apply_edit:navsteps:calib',
                            '--rotate_amplitude', '50.0',
                            '--rotate_angle', '50.0',
                            '--auto'])
            quick_adcp_core(opts)
            with open(cals_file, 'r') as file:
                cals = file.readlines()
            amp_line_index += nb_lines_cal_block
            phase_line_index += nb_lines_cal_block
            #  * in cals
            assert edge_amp == cals[amp_line_index]
            assert edge_phase == cals[phase_line_index]
            #  * in DB
            data = get_profiles(db_path)
            assert round(data.u.mean(), 5) == edge_u
            # - now let's break it and see if it exits as expected
            with pytest.raises(ValueError) as pytest_wrapped_e:
                opts = get_opts(['--steps2rerun', 'rotate:apply_edit:navsteps:calib',
                                '--rotate_amplitude', 'dghdjhfgj',
                                '--rotate_angle', 'xdgjhdth',
                                '--auto'])
                quick_adcp_core(opts)
            assert 'dghdjhfgj' in str(pytest_wrapped_e.value)


def test_compatibility_mode(uhdas_dir):
    proc_dir = os.path.join(uhdas_dir, "proc", "os75bb")
    dbinfo = os.path.join(proc_dir, "dbinfo.txt")
    with open(dbinfo, 'r') as file:
        orig = file.readlines()
    with change_dir(proc_dir):
        # Remove Control File
        os.remove(dbinfo)
        # Run with missing file
        with pytest.raises(Exception) as pytest_wrapped_e:
            opts = get_opts(['--steps2rerun', 'calib', '--auto'])
            quick_adcp_core(opts)
        assert "quickFatalError" in str(pytest_wrapped_e)
        assert "uhdas, lta, sta, pingdata" in str(pytest_wrapped_e.value)
        # Regenerate dbinfo.txt
        opts = get_opts(['--steps2rerun', 'navsteps:calib',
                        '--datatype', 'uhdas', '--sonar', 'os75bb',
                        '--beamangle', '30', '--yearbase', '2018',
                        '--ens_len', '300', '--cruisename', 'HLY18TA_03',
                        # '--xducer_dx', '-2', '--xducer_dy', '49',
                        '--auto'])
        quick_adcp_core(opts)
        # Compare to original
        with open(dbinfo, 'r') as file:
            regen = file.readlines()
        orig_dict = dict()
        for line in orig:
            try:
                key, val = line.split()
                orig_dict[key] = val
            except ValueError:
                continue
        regen_dict = dict()
        for line in regen:
            try:
                key, val = line.split()
                regen_dict[key] = val
            except ValueError:
                continue
        orig_keys = list(orig_dict.keys())
        orig_keys.sort()
        regen_keys = list(regen_dict.keys())
        regen_keys.sort()
        assert regen_keys == [
            'badbeam', 'beam_order', 'beamangle', 'configtype', 'cruisename',
            'datatype', 'dbname', 'ens_len', 'fixfile', 'pgmin', 'pingpref',
            'proc_engine', 'ref_method', 'refuv_smoothwin', 'refuv_source',
            'sonar', 'txy_file', 'xducer_dx', 'xducer_dy', 'yearbase']

        # FIXME: compare content of orig and regen...harder than it seems as they
        #        are not in a standard config format (e.g. yml, json,...)

        # Rerun with so generated file(s)...smoke test
        opts = get_opts(['--steps2rerun', 'calib', '--auto'])
        quick_adcp_core(opts)


def test_proc_templates():
    commands = [
        'postproc',
        'ltapy',
        'uhdaspy',
        'enrpy',
        'pingdata',
    ]
    expected_lines = [
        "All postprocessing is done with full codas+python",
        "manual loading of LTA data into CODAS database",
        "Process UHDAS data using Python",
        "manual steps to process ENR data",
        "processing pingdata",
    ]

    for command, expected_line in zip(commands, expected_lines):
        cmd_line = "quick_adcp.py --commands %s" % command
        result = subprocess.check_output(cmd_line, shell=True)
        assert expected_line in str(result)

    # Edge test
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        opts = get_opts(['--commands',  "sfdhdgjxfjk"])
        template = quick_adcp_core(opts)
        assert template is not None
    # - Testing exit code
    pytest_wrapped_e.value.code = 1


def test_adcp_tree(tmpdir, uhdas_dir):
    with change_dir(tmpdir):
        # Edge test for inputs
        cmd_line = "adcptree.py test -d uhdas"
        with pytest.raises(Exception) as pytest_wrapped_e:
            result = subprocess.check_output(cmd_line, shell=True)
        assert "CalledProcessError" in str(pytest_wrapped_e)

        # For UHDAS data
        config_path = os.path.join(uhdas_dir, "raw/config")
        cmd_line = "adcptree.py test_1 -d uhdas --cruisename HLY18TA_03 --configpath %s" % config_path
        result = subprocess.check_output(cmd_line, shell=True)
        dir_list = os.listdir(os.path.join(tmpdir, 'test_1'))
        assert dir_list.sort() == ['stick', 'cal', 'grid', 'load', 'edit', 'vector',
                            'adcpdb', 'contour', 'quality', 'ping', 'nav',
                            'config', 'scan'].sort()

        # For VmDAS
        cmd_line = "adcptree.py test_2   --datatype lta"
        result = subprocess.check_output(cmd_line, shell=True)
        dir_list = os.listdir(os.path.join(tmpdir, 'test_2'))
        # Note: 'config' dir is missing
        assert dir_list.sort() == ['stick', 'cal', 'grid', 'load', 'edit', 'vector',
                            'adcpdb', 'contour', 'quality', 'ping', 'nav',
                            'scan'].sort()

        # For UNIX
        cmd_line = "adcptree.py test_3"
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None
        dir_list = os.listdir(os.path.join(tmpdir, 'test_3'))
        # Note: 'config' dir is missing
        assert dir_list.sort() == ['stick', 'cal', 'grid', 'load', 'edit', 'vector',
                            'adcpdb', 'contour', 'quality', 'ping', 'nav',
                            'scan'].sort()


def test_quick_web(uhdas_dir):
    proc_dir = os.path.join(uhdas_dir, "proc")
    sonar_dir = os.path.join(proc_dir, "os150bb")
    webpy_dir = os.path.join(sonar_dir, "webpy")
    orig_list = os.listdir(sonar_dir)
    # Sanity Check
    assert os.path.exists(webpy_dir) is False

    # Make sections
    with change_dir(sonar_dir):
        cmd_line = "quick_web.py --sonar os150bb --auto --cruisename Test"
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None
        dir_list = os.listdir(sonar_dir)
        webpy_list = os.listdir(webpy_dir)

        assert orig_list != dir_list
        assert "webpy" in dir_list
        assert webpy_list.sort() == [
            'os150bb_txy000.html', 'os150bb_latcont000.html', 'sectinfo.txt',
            'os150bb_txy000.png', 'secnames.png', 'os150bb_loncont000.png',
            'os150bb_latcont000.png', 'ADCP_vectoverview.html',
            'os150bb_vect000.png', 'ADCP_vectoverview.png', 'index.html',
            'os150bb_ddaycont000.html', 'os150bb_ddaycont000.png', 'thumbnails',
            'os150bb_vect000.html', 'os150bb_overview.png',
            'os150bb_overview.html', 'os150bb_loncont000.html'].sort()


# - Testing tools used in single-ping-processing tuto.
def test_uhdas_proc_check(uhdas_dir):
    _ = pytest.importorskip("onship")
    with change_dir(uhdas_dir):
        cmd_line = "uhdas_proc_check.py"
        result = subprocess.check_output(cmd_line, shell=True)
        # Test so-generated file
        assert b"acc_heading_cutoff :                                   [0.02]" in result


def test_uhdas_proc(tmpdir):
    _ = pytest.importorskip("onship")
    with change_dir(tmpdir):
        orig_file_list = glob(os.path.join(tmpdir, "*"))
        assert orig_file_list == []
        # Generate "proc file"
        cmd_line = "uhdas_proc_gen.py -s km"
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None
        file_list = glob(os.path.join(tmpdir, "*"))
        # Test so-generated file
        assert len(file_list) == 1
        with open(file_list[0], 'r') as file:
                proc = file.read()
        assert 'shipname = "Kilo Moana"' in proc


# - Testing tools used in VmDAS-processing tuto.
@pytest.mark.parametrize("sonar", ["os75", "wh600"])
def test_reform_vmdas(tmpdir, vmdas_dir, uhdas_style_dir, sonar):
    # Sonar-dependent parameters from pycurrents_test_data:
    # "cruise_name" is used in filenames in uhdas_style_data/config/*, and
    # as the directory name in uhdas_style_data/uhdas_style_data/.
    yearbase, cruise_name = {
        "os75": (2009, 'ps_ridge_os75'),
        "wh600": (2021, 'smhi_mars_wh600')
        }[sonar]
    with change_dir(tmpdir):
        uhdas_dir = os.path.join(tmpdir, "uhdas_style")
        sonar_dir = os.path.join(vmdas_dir, sonar)

        # Run command
        # FIXME: pops up a window even when all options are given.
        # FIXME: ...fix this. Perhaps add --noshow options
        # cmd_line = "reform_vmdas.py --project_dir_path ./ --vmdas_dir_path %s --uhdas_style_dir ./uhdas_style_data  --cruisename test_cruise" % sonar_dir
        # result = subprocess.check_output(cmd_line, shell=True)

        # FIXME: ...meanwhile, I'll test the back-end
        # Run back-end
        VM = VmdasNavInfo(sonar_dir)
        navinfo = []
        for nnn in VM.navinfo:
            if nnn not in navinfo:
                navinfo.append(nnn)
        dt_factor = 3  # median(dt) * dt_factor = when to break the files in to parts
        F = FakeUHDAS(yearbase=yearbase,
                    sourcedir=sonar_dir,
                    destdir=uhdas_dir,
                    sonar=sonar,
                    dt_factor=dt_factor,
                    navinfo=navinfo,
                    ship='zzz')
        F()

        # Testing directory structure.
        dir_list = os.listdir(tmpdir)
        assert dir_list == ['uhdas_style']
        dir_list = os.listdir(uhdas_dir)
        assert dir_list.sort() == ['rbin', 'raw'].sort()
        dir_list_expected = os.listdir(
            os.path.join(uhdas_style_dir, 'uhdas_style_data', cruise_name,
                        'raw', sonar))
        dir_list_expected = [name for name in dir_list_expected if not name.endswith("cache")]
        dir_list = os.listdir(
            os.path.join(uhdas_dir, 'raw', sonar))
        assert dir_list == dir_list_expected


def test_vmdas_info(vmdas_dir):
    sonar_dir = os.path.join(vmdas_dir, "os75")
    with change_dir(sonar_dir):

        # Making info files
        cmd_line = "vmdas_info.py --logfile lta_info.txt *.LTA"
        result = subprocess.check_output(cmd_line, shell=True)
        cmd_line = "vmdas_info.py --logfile sta_info.txt *.STA"
        result = subprocess.check_output(cmd_line, shell=True)
        cmd_line = "vmdas_info.py --logfile enr_info.txt *.ENR"
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None

        # Testing against files content
        with open("./lta_info.txt", 'r') as file:
            lta_info = file.read()
        with open("./sta_info.txt", 'r') as file:
            sta_info = file.read()
        with open("./enr_info.txt", 'r') as file:
            enr_info = file.read()

        assert "transducer angle (EA) was set as 1.180" in lta_info
        assert "HeadingSource(0:adcp,1:navHDT,2:navHDG,3:navPRDID,4:manual)=1" in lta_info
        assert "BackupHeadingSource(0:adcp,1:navHDT,2:navHDG,3:navPRDID,4:manual,5:PASHR,6:PASHR,ATT,7:PASHR,AT2)=8" in lta_info
#     assert """N2R files had multiple matches (possible problem):
# $GPGGA, $GPHDT, $PASHR,AT2, $PASHR,ATT, $PASHR,POS
# $GPGGA, $GPHDT, $PASHR,AT2, $PASHR,ATT, $PASHR,NO CHECKSUM, $PASHR,POS""" in
# lta_info
### The assertion above resulted from lack of adequate handling of the embedded
# $PADCP when looking for nav messages.  This was fixed on 2025-01-02.

    assert """N1R files include these messages:
[['$HEHDT']]

N2R files include these messages:
[['$GPGGA', '$GPHDT', '$PASHR,AT2', '$PASHR,ATT', '$PASHR,POS']]

N3R files include these messages:
[['$GPGGA', '$GPGLL']]""" in lta_info


    assert """  #filename                  datestr         startdd     enddd     gapsecs   bin   blank   Nbins   ping    medens PingsPerProf numprofs
   Collins_PtSur_Ridge005_000000.STA 2009/09/22 14:35:58   264.6083   264.7125       0s     8m     8m      80   bb  /bt    30.61s        9     301
   Collins_PtSur_Ridge006_000000.STA 2009/09/22 17:07:45   264.7137   264.9672     106s     8m     8m      80   bb  /--    29.55s       17     731
   Collins_PtSur_Ridge007_000000.STA 2009/09/22 23:13:33   264.9677   265.0376      47s     8m     8m      80   bb  /bt    31.21s        9     202""" in sta_info
    assert """N3R files include these messages:
[['$GPGGA', '$GPGLL']]""" in sta_info

    assert """  #filename                  datestr         startdd     enddd     gapsecs   bin   blank   Nbins   ping    medens PingsPerProf numprofs
   Collins_PtSur_Ridge005_000000.ENR 2009/09/22 14:35:54   264.6083   264.7125       0s     8m     8m      80   bb  /bt     3.47s        1    2441
   Collins_PtSur_Ridge006_000000.ENR 2009/09/22 17:07:43   264.7137   264.7758     103s     8m     8m      80   bb  /--     1.84s        1    2907
   Collins_PtSur_Ridge006_000001.ENR 2009/09/22 18:37:13   264.7758   264.8379       2s     8m     8m      80   bb  /--     1.84s        1    2907
   Collins_PtSur_Ridge006_000002.ENR 2009/09/22 20:06:40   264.8380   264.9000       2s     8m     8m      80   bb  /--     1.84s        1    2907
   Collins_PtSur_Ridge006_000003.ENR 2009/09/22 21:36:06   264.9001   264.9622       2s     8m     8m      80   bb  /--     1.84s        1    2907
   Collins_PtSur_Ridge006_000004.ENR 2009/09/22 23:05:36   264.9622   264.9673       2s     8m     8m      80   bb  /--     1.84s        1     238
   Collins_PtSur_Ridge007_000000.ENR 2009/09/22 23:13:29   264.9677   265.0376      36s     8m     8m      80   bb  /bt     3.47s        1    1740""" in enr_info
    # assert """WARNING: no N2R data""" in enr_info
    ## Above was bogus for the same reason.
    assert """EnableGGASource=TRUE
NmeaPortForGGASource=3""" in enr_info


def test_vmdas_quick_ltaproc(tmpdir, vmdas_dir):
    with change_dir(tmpdir):

        ### LTA
        lta_files = os.path.join(vmdas_dir, "os75", "*.LTA")
        # Running command
        cmd_line = "vmdas_quick_ltaproc.py --cruisename test_lta %s" % lta_files
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None

        # Testing directory structure.
        # TODO: here and elsewhere, use a more exhaustive test of content.
        dir_list = os.listdir(tmpdir)
        assert dir_list == ['test_lta_proc']
        dir_list = os.listdir(os.path.join(tmpdir, 'test_lta_proc'))
        assert dir_list.sort() == [
            'test_lta_os75bb_LTA_info.txt', 'test_lta_os75bb_LTA_proc.txt',
            'os75bb_LTA'].sort()
        dir_list = os.listdir(os.path.join(tmpdir, 'test_lta_proc', 'os75bb_LTA'))
        assert dir_list.sort() == [
            'stick', 'cal', 'grid', 'load', 'dbinfo.txt', 'quick_run.log', 'edit',
            'vector', 'q_py.cnt', 'cruise_info.txt', 'adcpdb', 'contour',
            'quality', 'ping', 'cals.txt', 'nav', 'scan', 'webpy'].sort()

        # Testing generated data
        db_path = os.path.join(tmpdir, 'test_lta_proc', 'os75bb_LTA', 'adcpdb')
        data = get_profiles(db_path)
        assert round(float(data.u.mean()), 5) == -0.02475
        assert round(float(data.v.mean()), 5) == 0.09241
        assert round(float(data.heading.mean()), 5) == 166.56129


def test_vmdas_quick_staproc(tmpdir, vmdas_dir):
    with change_dir(tmpdir):

        ### STA
        sta_files = os.path.join(vmdas_dir, "os75", "*.STA")
        # Running command
        cmd_line = "vmdas_quick_ltaproc.py --cruisename test_sta %s" % sta_files
        result = subprocess.check_output(cmd_line, shell=True)
        assert result is not None

        # Testing folder archi.
        dir_list = os.listdir(tmpdir)
        assert dir_list == ['test_sta_proc']
        dir_list = os.listdir(os.path.join(tmpdir, 'test_sta_proc'))
        assert dir_list.sort() == [
            'test_sta_os75bb_STA_info.txt', 'test_sta_os75bb_STA_proc.txt',
            'os75bb_STA'].sort()
        dir_list = os.listdir(os.path.join(tmpdir, 'test_sta_proc', 'os75bb_STA'))
        assert dir_list.sort() == [
            'stick', 'cal', 'grid', 'load', 'dbinfo.txt', 'quick_run.log', 'edit',
            'vector', 'q_py.cnt', 'cruise_info.txt', 'adcpdb', 'contour',
            'quality', 'ping', 'cals.txt', 'nav', 'scan', 'webpy'].sort()

        # Testing generated data
        db_path = os.path.join(tmpdir, 'test_sta_proc', 'os75bb_STA', 'adcpdb')
        data = get_profiles(db_path)
        assert round(float(data.u.mean()), 5) == -0.0299
        assert round(float(data.v.mean()), 5) == 0.08679
        assert round(float(data.heading.mean()), 5) == 164.18018


def test_hundredths_fixer():
    # Test components of a work-around for a VMDAS bug (fixed in some later
    # versions of VMDAS).
    tenths = np.repeat(np.arange(10), 10)
    hundredths = np.tile(np.arange(10), (1, 10)).ravel()
    dday0 = 350
    dday_real = dday0 + (tenths / 10.0 + hundredths / 100.0) / 86400
    dday_bug = dday0 + (tenths / 100.0) / 86400
    dday_trunc = dday0 + (tenths / 10.0) / 86400
    tols = {"rtol": 0, "atol":1e-12}
    assert_allclose(FakeUHDAS._fix_hundredths_enr(dday_bug), dday_trunc, **tols)
    assert_allclose(FakeUHDAS._fix_hundredths_nav(dday_real), dday_trunc, **tols)

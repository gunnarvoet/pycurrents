#!/usr/bin/env python3

from optparse import OptionParser

from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common lib.
from pycurrents.adcp.adcp_specs import codas_editparams  # BREADCRUMB: common lib
from pycurrents.system.misc import Bunch   # BREADCRUMB: common library
from pycurrents.adcpgui_qt.argument_parsers import dataviewer_option_parser
from pycurrents.adcpgui_qt.presenter.intercommunication import get_dbpath
from pycurrents.adcpgui_qt.model.thresholds_models import (
    Thresholds, ThresholdsCompare)
from pycurrents.adcpgui_qt.model.ascii_files_models import (
    ASCIIandPathContainer, ASCIIandPathContainerCompareMode)
from pycurrents.adcpgui_qt.model.display_features_models import (
    displayFeatures, displayFeaturesEdit, displayFeaturesCompare)
from pycurrents.adcpgui_qt.model.codas_data_models import (
    CData, CDataEdit, CDataCompare)


def test_view_model_display_features():
    display_feat = displayFeatures()
    assert(display_feat.year_base is None)


def test_view_model_display_features_edit():
    display_feat = displayFeaturesEdit()
    assert(display_feat.year_base is None)
    assert(display_feat.show_threshold is True)


def test_view_model_display_features_compare():
    display_feat = displayFeaturesCompare(['os75nb', 'os150nb'])
    assert(display_feat.sonars == ['os75nb', 'os150nb'])
    assert(display_feat.sonar == 'Comparison between sonars')
    assert(display_feat.autoscale is False)


def test_ascii_container():
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os75nb'
    dbpath = get_dbpath(path)
    asciiC = ASCIIandPathContainer('edit', dbpath)
    check = {'badbin': 'abadbin.asclog',
             'badprf': 'abadprf.asclog',
             'bottom': 'abottom.asclog'}
    assert(asciiC.log_edit_filename == check)


def test_ascii_container_compare():
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/'
    check = {'badbin': 'abadbin.asclog',
             'badprf': 'abadprf.asclog',
             'bottom': 'abottom.asclog'}
    proc_path = path + 'proc/'
    # Compare mode
    asciiC = ASCIIandPathContainerCompareMode(
        [proc_path + 'os75bb', proc_path + 'os150bb'])
    assert (asciiC['os75bb'].log_edit_filename == check)
    assert (asciiC['os150bb'].log_edit_filename == check)


def test_cdata():
    test_data_path = get_test_data_path()
    path2data = test_data_path + '/codas_db/os38nb_py'
    (options, args) = OptionParser().parse_args([''])
    options.mode = 'view'
    options.netcdf = False
    dbpath = get_dbpath(path2data)
    CD = CData(dbpath, options)
    assert(CD.startdd == 29.740405092592592)
    CD.ddstep = 0.8
    CD.get_data(newdata=True)
    CD.set_grid()
    CD.set_grid1D()


def test_cdata_edit():
    test_data_path = get_test_data_path()
    path = test_data_path + '/uhdas_data/proc/os75bb'
    arglist = ['--dbname', path, '-e']
    options = dataviewer_option_parser(arglist)
    thresholds = Thresholds()
    dbpath = get_dbpath(path)
    CD = CDataEdit(thresholds, dbpath, options)
    assert(CD.startdd == 149.47528935185184)
    CD.ddstep = 0.8
    CD.get_data(newdata=True)
    CD.set_grid()
    CD.set_grid1D()


def test_cdata_compare():
    test_folder_path = get_test_data_path()
    test_data_path = test_folder_path + '/uhdas_data/proc'
    arglist = ['--dbname', test_data_path,
               '-c', 'os75nb', 'os75bb', 'os150nb', 'os150bb']
    options = dataviewer_option_parser(arglist)
    paths = options.compare
    asciiNpaths = ASCIIandPathContainerCompareMode(paths)
    sonars = list(asciiNpaths.keys())
    thresholds = ThresholdsCompare(sonars, asciiNpaths.edit_dir_paths)
    CD = CDataCompare(sonars, thresholds, asciiNpaths.db_paths, options)
    assert(CD.startdd == 149.47528935185184)
    CD.ddstep = 0.8
    CD.get_data(newdata=True)
    CD.set_grid()


def test_thresholds():
    thresholds = Thresholds()
    assert(thresholds.default_values == Bunch(codas_editparams))
    assert (thresholds.default_values.bigtarget_ampthresh == 40)
    assert (thresholds.default_values.shipspeed_cutoff == 4)


def test_thresholds_compare():
    test_folder_path = get_test_data_path()
    test_data_path = test_folder_path + '/uhdas_data/proc'
    arglist = ['--dbname', test_data_path,
               '-c', 'os75nb', 'os75bb', 'os150nb', 'os150bb']
    options = dataviewer_option_parser(arglist)
    paths = options.compare
    asciiNpaths = ASCIIandPathContainerCompareMode(paths)
    sonars = list(asciiNpaths.keys())
    thresholds = ThresholdsCompare(sonars, asciiNpaths.edit_dir_paths)
    assert (thresholds['os75nb'].default_values.bigtarget_ampthresh == 500)
    assert (thresholds['os75bb'].default_values.shipspeed_cutoff == 100)
    assert (thresholds['os150nb'].default_values.bigtarget_ampthresh == 500)
    assert (thresholds['os150bb'].default_values.shipspeed_cutoff == 100)

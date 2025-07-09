#!/usr/bin/env python3
import sys
import os
import logging

# Standard imports
from numpy import ma
import numpy as np
from glob import glob

# Matplotlib imports
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.widgets import MultiCursor

# Local imports
# BREADCRUMB: common lib starts here...
from pycurrents.num import interp1, Runstats, cleaner
from pycurrents.num.nptools import rangeslice
from pycurrents.num.nptools import loadtxt_
from pycurrents.system.misc import Bunch, guess_comment, Cachefile
from pycurrents.plot.mpltools import savepngs
# BREADCRUMB: ...common lib finishes here
from pycurrents.adcpgui_qt.lib.miscellaneous import reset_artist
from pycurrents.adcpgui_qt.lib.plotting_parameters import (
    ScalarFormatter, tickerHd, FORMATTER)
from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    QApplication, globalStyle, make_busy_cursor, restore_cursor,
    CustomDialogBox, CustomInfoBox)
from pycurrents.adcpgui_qt.lib.panel_plotter import START_Y, X0, TOTAL_HEIGHT
from pycurrents.adcpgui_qt.lib.miscellaneous import (
    nowstr, run_command)
from pycurrents.adcpgui_qt.view.control_window import ControlWindow
from pycurrents.adcpgui_qt.model.display_features_models import DisplayFeaturesSingleton
from pycurrents.adcpgui_qt.apps.generic_app_components import (
    GenericPlotWindow, GenericZapperWindow)

# Standard logging
_log = logging.getLogger(__name__)


# Global parameters
# - plotting parameters
GREY = [.5, .5, .5]
MARKER_SIZE = 3
# - templates
REROTATE_STR = '''

           DB_NAME:       %(dbname)s
           LOG_FILE:      rotate.log
           TIME_RANGE:    all

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          %(year_base)s
                time_angle_file:  newhcorr.ang
                amplitude=          1.0
                angle_0=            0.0
                end
              end
'''
UNROTATE_STR = '''

           DB_NAME:       %(dbname)s
           LOG_FILE:      rotate.log
           TIME_RANGE:    all

           OPTION_LIST:
              water_and_bottom_track:
                year_base=          %(year_base)s
                unrotate!
                amplitude=          1.0
                angle_0=            0.0
                end
              end
'''


### Frontend
# App class
class PatchHcorrApp:
    def __init__(self, working_dir=os.getcwd(), ens_hcorr_path='',
                 sonar=None, yearbase=None, test=False):
        """
        patch_hcorr app's framework

        Args:
            working_dir: directory path to work from, str.
            ens_hcorr_path: absolute path to ens_hcorr.* files
            test: boolean switch

        N.B.: 'sonar' and 'yearbase' options are for experts silling to
              generate new *.ang and *.asc files but ont apply them
        """
        if test:
            self.app = test
        else:
            self.app = QApplication(sys.argv)
            try:
                self.app.setStyle(globalStyle)
            except RuntimeError:  # in case chosen style not available
                pass
        make_busy_cursor()
        self.working_dir = os.path.abspath(working_dir)
        # Logging stuff
        self.patch_log = os.path.join(self.working_dir, 'patch_hcorr_app.log')

        ### Models ###
        # - ens_hcorr.asc
        if not ens_hcorr_path:
            for root, dirs, files in os.walk(self.working_dir):
                for file in files:
                    filename = os.path.join(root, file)
                    if '/ens_hcorr.asc' in filename:
                        self.ens_hcorr_path = filename
                        break
        else:
            self.ens_hcorr_path = os.path.abspath(ens_hcorr_path)
        #  * sanity checks
        msg = 'ens_hcorr.asc COULD NOT BE FOUND !'
        msg += '\nTry to specify its location with'
        msg += '\nthe --ens_hcorr_path option'
        if not hasattr(self, 'ens_hcorr_path'):
            _log.error(msg)
            sys.exit(1)
        if not os.path.exists(self.ens_hcorr_path):
            _log.error(msg)
            sys.exit(1)
        self.rotate_dir = os.path.dirname(self.ens_hcorr_path)
        new_hcorr_path = os.path.join(self.rotate_dir, 'newhcorr.asc')
        if os.path.exists(new_hcorr_path):
            msg = '%s ALREADY EXISTS !' % new_hcorr_path
            msg += '\nDelete, move or rename it and try again'
            _log.error(msg)
            sys.exit(1)
        #  * mining data from dbinfo.txt
        cruise_dir = '/'.join(self.rotate_dir.split('/')[:-2])
        dbinfo_path = os.path.join(cruise_dir, 'dbinfo.txt')
        if sonar and yearbase:
            db_params = Bunch({"sonar": sonar, "yearbase": int(yearbase)})
        elif os.path.exists(dbinfo_path):
            cf = Cachefile(dbinfo_path)
            cf.read()
            db_params = Bunch(cf.cachedict)
        else:
            msg = str(
                '---dbinfo.txt COULD NOT BE FOUND !---'
                + "\nAre you running from the right place?"
                + "\nIs this an old database (prior to 2012)?"
                + '\nOtherwise follow this instructions provided in the '
                + 'link and try again:'
                + '\nhttps://currents.soest.hawaii.edu/docs/adcp_doc/'
                + 'codas_doc/python_compatibility.html')
            _log.error(msg)
            sys.exit(1)
        # - EnsHcorr_Plot object
        self.E = EnsHcorr_Plot(
            filename=self.ens_hcorr_path,
            sonar=db_params.sonar,
            parent=self)
        # - Default parameters container
        global DEFAULT_PARAMS
        DEFAULT_PARAMS = PatchDefaultParams(
            self.E.dday[0], self.E.dday[-1], db_params.yearbase)
        DISPLAY_FEAT = DisplayFeaturesSingleton(DEFAULT_PARAMS)
        # N.B.: DISPLAY_FEAT needs to be instantiated even if not explicitly
        #       use afterwords, hence the follwoing assertion for
        #       pyflakes compatibility
        assert DISPLAY_FEAT

        ### Views ###
        # Start up views
        self.controlWindow = ControlWindow(self.patch_log, mode='patch')
        # N.B.: I don't really like the following line but considering
        #       the present architecture, it seems like the obvious option
        self.colorPlot = GenericPlotWindow(
            self.E.panelsFig, title='Plotting Window',
            yearbase=db_params.yearbase,
            ref_axis=self.E.ax4_dhfinal, with_toolbar=True,
            parent=self.controlWindow)
        self.zapperPlot = GenericZapperWindow(
            self.E.dday, self.E.hcorr[:, 3], self.E.zapperFig,
            title='Editing Window',
            yearbase=db_params.yearbase, shared_axis=self.E.ax_zapper,
            parent=self.controlWindow, parent_app=self)
        # Adding custom ty cursors
        self.multiCursor = MultiCursor(
            self.colorPlot.canvas, self.E.panelsFig.axes, horizOn=False,
            color='r')
        self.multiCursor.set_active(True)

        ### Presenter ###
        # - connection to slots
        self.controlWindow.patchBar.buttonEdit.clicked.connect(
            self.zapperPlot.show)
        self.controlWindow.patchBar.buttonSave.clicked.connect(self.on_save)
        self.controlWindow.patchBar.buttonApply.clicked.connect(
            self.on_apply_n_quit)
        # - connection to callback/refresh
        self.controlWindow.checkboxUtcDate.clicked.connect(self.refresh)
        patchTab = self.controlWindow.tabsContainer.patchTab
        patchTab.checkboxDeglitching.clicked.connect(self.refresh)
        patchTab.checkboxBoxfilt.clicked.connect(self.refresh)
        patchTab.spinboxHalfwidth.valueChanged.connect(self.refresh)
        patchTab.spinboxBoxfilt.valueChanged.connect(self.refresh)
        #  * refresh on return
        patchTab.entryCutoff.returnPressed.connect(self.refresh)
        patchTab.entryStdCutoff.returnPressed.connect(self.refresh)
        patchTab.entryNbGoodCutoff.returnPressed.connect(self.refresh)
        # - custom callbacks
        #  * between "home" zoom buttons
        self.zapperPlot.toolbar.actions()[0].triggered.connect(
            self.colorPlot.toolbar.home)
        self.colorPlot.toolbar.actions()[0].triggered.connect(
            self.zapperPlot.toolbar.home)
        # Kick start application
        restore_cursor()
        if not test:
            self.write_to_log("\n\n=== %s: Starting patch_hcorr_app ===" %
                              nowstr())
            self.write_to_log("\nWorking with: %s" % self.ens_hcorr_path)
            # - kick start EnsCorr module
            self.E.draw_top_panels()
            self.E.update(mask=DEFAULT_PARAMS.mask,
                          medfilt_win=DEFAULT_PARAMS.medfilt_win,
                          medcutoff=DEFAULT_PARAMS.medcutoff,
                          deglitch=DEFAULT_PARAMS.deglitch,
                          stdcutoff=DEFAULT_PARAMS.stdcutoff,
                          goodcutoff=DEFAULT_PARAMS.goodcutoff,
                          run_boxfilt=DEFAULT_PARAMS.run_boxfilt,
                          smboxwidth=DEFAULT_PARAMS.smboxwidth)
            # - refresh plots
            self.zapperPlot.refresh()
            self.colorPlot.refresh()
            # - Show GUI components
            self.colorPlot.show()
            self.controlWindow.show()
            # - Force click "Refresh"
            # self.controlWindow.
            # - Exit when done
            sys.exit(self.app.exec_())

    # Slots
    def on_save(self):
        make_busy_cursor()
        self.controlWindow.patchBar.setDisabled(True)
        # sanity check
        newhcorr_files = os.path.join(self.rotate_dir, 'newhcorr*')
        if glob(newhcorr_files):
            arglist = ['rm', '-f', newhcorr_files]
            run_command(arglist)
            arglist = ['rm', '-f',
                       os.path.join(self.rotate_dir, 'patch_hcorr.png')]
            run_command(arglist)
        # write new_hcorr.asc
        numlines = self.E.write_files()
        self.write_to_log('\nwrote %d lines of "newhcorr.asc"' % (numlines))
        # Switching to Log tab
        self.controlWindow.tabsContainer.setCurrentIndex(1)
        self.controlWindow.tabsContainer.repaint()  # refresh log tab
        # make plots from newhcorr.asc
        outfilebase = os.path.join(self.rotate_dir, 'newhcorr')
        Hcorrplot(hcorr_filename=self.E.ascfile,
                  titlestr='ADCP: New Heading Correction',
                  outfilebase=outfilebase,
                  printformats='png', dpi=90)
        # Zoom back to home
        self.colorPlot.toolbar.home()
        # Save png
        savepngs(self.rotate_dir + '/patch_hcorr',
                 dpi=90, fig=self.E.panelsFig)
        self.write_to_log('\nview files "*.png"')
        self.write_to_log('\ndone plotting"')
        self.write_to_log(
            '\n\n===INSPECT THE newhcorr*.png FILES AND CLOSE FigView===')
        self.write_to_log('\n===PRIOR TO APPLY THE EDITING===')
        # force print in log tab
        self.controlWindow.tabsContainer.logTab._set_text()
        arglist = ['figview.py']
        # Custom sorting for Jules
        listEnsPNG = glob(self.rotate_dir + "/ens_hcorr_*.png")
        listNewPNG = glob(self.rotate_dir + "/newhcorr_*.png")
        listPNG = []
        try:
            def key_sort(x):
                return int(x.split("_")[-1].split('.')[0])
            listEnsPNG.sort(key=key_sort)
            listNewPNG.sort(key=key_sort)
        except ValueError:
            # file name does not comply to newhcorr_*NUMBER*.png
            # or ens_hcorr_*NUMBER*.png
            pass
        for ens, new in zip(listEnsPNG, listNewPNG):
            listPNG.append(ens)
            listPNG.append(new)
        arglist.extend(listPNG)
        run_command(arglist)
        # Restore mouse control
        self.controlWindow.patchBar.setEnabled(True)
        restore_cursor()

    def on_apply_n_quit(self):
        make_busy_cursor()
        # Switching to Log tab
        self.controlWindow.tabsContainer.setCurrentIndex(1)
        self.controlWindow.tabsContainer.repaint()  # refresh log tab
        # Sanity check
        newhcorr_files = os.path.join(self.rotate_dir, 'newhcorr*')
        if not glob(newhcorr_files):
            self.write_to_log('\n\n=NO newhcorr_* FILES WERE FOUND !=')
            self.write_to_log('\n Click "Save" first and try again.')
            restore_cursor()
            return
        # Ask confirmation
        message = str(
            "This operation will overwrite the original heading correction.\n"
            + "If you have already applied a constant rotation to\n"
            + "the database you will have to apply that AGAIN after this step\n"
            + ".. Check calibrations.\n"
            + "        Are you sure you want to continue?")
        question = CustomDialogBox(message)
        if question.answer is False:
            restore_cursor()
            return
        # Get calibration prior to change
        cal_dir = '/'.join(self.rotate_dir.split('/')[:-1])
        watertrack_outfile = os.path.join(cal_dir, 'watertrk/adcpcal.out')
        before_cal_str = self.get_last_calibration(watertrack_outfile, cal_dir)
        # Print info & run commands
        msg = "The following commands were run:\n"
        msg += "-------------------------------"
        self.write_to_log(
            '\n\nRemoving earlier time-dependent heading correction...')
        arglist = ['cd', self.rotate_dir, ';', 'rotate', 'unrotate.tmp']
        self.write_to_log(
            "\n...running 'rotate unrotate.tmp' in .../cal/rotate")
        msg += "\n" + " ".join(arglist)
        run_command(arglist)
        self.write_to_log('\n\nApplying new heading correction...')
        arglist = ['cd', self.rotate_dir, ';', 'rotate', 'rotate_fixed.tmp']
        msg += "\n" + " ".join(arglist)
        run_command(arglist)
        self.write_to_log(
            "\n...running 'rotate rotate_fixed.tmp' in .../cal/rotate")
        self.write_to_log(
            '\n\nRunnning navigation steps and inspect calibrations..')
        cruise_dir = os.path.abspath(os.path.join(self.rotate_dir, "../.."))
        arglist = ['cd', cruise_dir, ';', 'quick_adcp.py', '--steps2rerun',
                   'navsteps:calib', '--auto']
        msg += "\n" + " ".join(arglist) + "\n"
        run_command(arglist)
        self.write_to_log(
            "\n...running 'quick_adcp.py --steps2rerun navsteps:calib" +
            " --auto' in .../cruise_dir")
        print(msg)
        # Print out water and bottom track in a pop-up window before closing
        after_cal_str = self.get_last_calibration(watertrack_outfile, cal_dir)
        msg = "---Original Calibration---\n"
        msg += before_cal_str
        msg += "\n\n---New Calibration---\n"
        msg += after_cal_str
        restore_cursor()
        if msg:
            CustomInfoBox(msg)
            print(msg)
        # Print some more guidance
        msg = """
You can now apply the final calibration by running:
    quick_adcp.py --steps2rerun rotate:apply_edit:navsteps:calib --rotate_amplitude AMP --rotate_angle PHASE  --auto
Where AMP and PHASE are the values indicated in the watertrack (or bottomtrack) calibration output.
See https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/calibration/index.html
        """
        print(msg)
        sys.exit(0)

    # Local lib
    def refresh(self):
        make_busy_cursor()
        params = self._get_entries()
        self.E.update(**params)
        flag = self.controlWindow.checkboxUtcDate.isChecked()
        self.colorPlot.utc_date = flag
        self.zapperPlot.utc_date = flag
        self.colorPlot.refresh()
        self.zapperPlot.refresh()
        # make windows visible
        if not self.colorPlot.isVisible():
            self.colorPlot.setVisible(True)
        # if not self.zapperPlot.isVisible():
        #     self.zapperPlot.setVisible(True)
        restore_cursor()

    def write_to_log(self, message):
        """Write given message to log file"""
        # Log in ascii file
        with open(self.patch_log, 'a') as file:
            file.write(message)

    # TODO: move to lib/miscellaneous.py
    @staticmethod
    def get_last_calibration(watertrack_outfile, cal_dir):
        msg = ''
        if os.path.exists(watertrack_outfile):
            msg += '- Water Track Calibration:\n'
            with open(watertrack_outfile) as newreadf:
                lines = newreadf.readlines()
            # index of the last calibration numbers
            for ii, line in enumerate(lines):
                if set(['median', 'mean', 'std']).issubset(line.split()):
                    start_index = ii
            # Read only the next 3 lines
            end_index = start_index + 3
            for line in lines[start_index:end_index]:
                msg += line
            msg += '\n'
        bottom_outfile = os.path.join(cal_dir, 'botmtrk/btcaluv.out')
        if os.path.exists(bottom_outfile):
            msg += '- Bottom Track Calibration:\n'
            with open(bottom_outfile) as newreadf:
                lines = newreadf.readlines()
            # index of the last calibration numbers
            for ii, line in enumerate(lines):
                if set(['median', 'mean', 'std']).issubset(line.split()):
                    start_index = ii
            # Read only the next 3 lines
            end_index = start_index + 3
            for line in lines[start_index:end_index]:
                msg += line
        return msg

    def _get_entries(self):
        global DEFAULT_PARAMS
        params = {}
        # From zapper
        params["mask"] = self.zapperPlot.mask
        # From control window
        tab = self.controlWindow.tabsContainer.patchTab
        try:
            params["medcutoff"] = float(tab.entryCutoff.text())
            params["stdcutoff"] = float(tab.entryStdCutoff.text())
            params["goodcutoff"] = float(tab.entryNbGoodCutoff.text())
        except ValueError:  # not a proper entry
            params["medcutoff"] = DEFAULT_PARAMS.medcutoff
            params["stdcutoff"] = DEFAULT_PARAMS.stdcutoff
            params["goodcutoff"] = DEFAULT_PARAMS.goodcutoff
        params["deglitch"] = tab.checkboxDeglitching.isChecked()
        params["medfilt_win"] = float(tab.spinboxHalfwidth.text())
        params["run_boxfilt"] = tab.checkboxBoxfilt.isChecked()
        params["smboxwidth"] = float(tab.spinboxBoxfilt.text())
        _log.debug("params: ", params)
        return params


### Backend ###
def PatchDefaultParams(start_day, end_day, yearbase):
    """
    Return a parameters container for patch_hcorr App.

    Args:
        start_day: decimal day, float
        end_day: decimal day, float
        yearbase: year base, int.

    Returns: Bunch
    """""
    container = Bunch(
        {'mode': 'patch',
         'advanced': False,
         'year_base': yearbase,
         'day_range': [start_day, end_day],
         'medfilt_win': 31,
         'smboxwidth': 3,
         'medcutoff': 3.0,
         'stdcutoff': 1.0,
         'goodcutoff': 20.0,
         'deglitch': False,
         'run_boxfilt': False,
         'mask': None})
    return container


#   The Hcorrplot class (next) is a "class-y-fied" version
#   of the Scripter method in quick_mpl.py
#   It is extracted here for illustration
# FIXME - BREADCRUMBS:  move to lib (Hcorrplot also used somewhere else like quick_mpl and in process_tarball.py in uhdas)
class Hcorrplot:
    # N.B.: based on legacy code, original design by Jules
    def __init__(self,
                 hcorr_filename='ens_hcorr.asc',
                 proc_yearbase=None,
                 dbname=None,
                 titlestr=None,
                 incremental=False,
                 printformats='pdf',
                 dpi=100,
                 days_per_panel=1,
                 panels_per_page=4,
                 max_yscale=10,
                 outfilebase='ens_hcorr_mpl'):
        """
        Heading correction plotter

        Args:
            hcorr_filename: absolute path to *.asc file, str.
                            (usually ens_hcorr.asc)
            proc_yearbase: processing year base, int.
            dbname: database name (usually starts with "a", like "aship"), str.
            titlestr: plot title, str.
            incremental: boolean switch
            printformats: print format (e.g.: 'png', 'pdf',...), str.
            dpi: dots per inch, int.
            days_per_panel: int.
            panels_per_page: int.
            max_yscale: max. value on y axis, float.
            outfilebase: prefix for output plots, str.
        """
        self.hcorr_filename = hcorr_filename
        self.proc_yearbase = proc_yearbase
        self.dbname = dbname
        self.titlestr = titlestr
        self.incremental = incremental
        self.printformats = printformats
        self.dpi = dpi
        self.days_per_panel = days_per_panel
        self.panels_per_page = panels_per_page
        self.max_yscale = max_yscale
        self.outfilebase = outfilebase
        # Initialize data
        self.data, self.hcoor = self.get_data()
        if len(self.data) < 2:
            _log.warning('Not enough hcorr data available')
            return
        ymin = np.nanmin(self.data['dh_mean'])
        ymax = np.nanmax(self.data['dh_mean'])
        ymin = max(ymin, -self.max_yscale)
        ymax = min(ymax, self.max_yscale)
        self.yrange = [ymin, ymax]

        dday = self.data['dday']
        startdd = np.floor(dday[0])
        minspan = dday[-1] - startdd
        dt = self.panels_per_page * self.days_per_panel
        numpages = int(np.ceil((minspan)/dt))
        _log.debug('found %f days of data',
                    self.data['dday'][-1] - self.data['dday'][0])
        _log.debug('figures with %d panels per page, %f days per panel',
                                self.panels_per_page, self.days_per_panel)
        _log.debug('printing %d pages', numpages)
        # Plot figures to PNGs
        pages = list(range(numpages))
        if self.incremental:
            pages = pages[-2:]
        for pagenum in pages:
            fig = self.plot_hcorr(startdd + pagenum*dt)
            if self.printformats:
                for pf in self.printformats.split(':'):
                    fname = '%s_%03d.%s' % (self.outfilebase,
                                         startdd+pagenum*dt, pf)
                    fig.savefig(fname, dpi=self.dpi)

    def get_data(self):
        names = ['dday', 'hd_mean', 'hd_last', 'dh_mean', 'dh_std',
                 'n_used', 'badmask', 'Npersist']
        dtype = np.dtype({'names': names, 'formats': [np.float64]*8})
        comment = guess_comment(self.hcorr_filename)
        _hcorr = loadtxt_(self.hcorr_filename, comments=comment, ndmin=2)
        nr, nc = _hcorr.shape
        if nc == 7:
            hcorr = np.zeros((nr, 8), dtype=np.float64)
            hcorr[:, :7] = _hcorr
        else:
            hcorr = _hcorr

        hcorr = hcorr.view(dtype).ravel()
        sl = rangeslice(hcorr['dday'], 'all')
        data = hcorr[sl]
        return data, hcorr

    def plot_hcorr(self, startdd):
        from pycurrents.adcpgui_qt.apps.generic_app_components import GenericPlotMplCanvas
        fig = Figure(figsize=(8, 6), dpi=self.dpi)
        GenericPlotMplCanvas(fig)
        dday = self.data['dday']
        mask = self.data['badmask'].astype(bool)
        dh_mean = ma.array(self.data['dh_mean'], mask=mask)
        dh_mean_bad = ma.array(self.data['dh_mean'], mask=~mask)
        for plotnum in range(self.panels_per_page):
            ax = fig.add_subplot(self.panels_per_page, 1, plotnum+1)
            ddmin = startdd + plotnum*self.days_per_panel
            ddmax = ddmin + self.days_per_panel
            ii = rangeslice(dday, [ddmin, ddmax])
            ax.plot(dday[ii], dh_mean[ii], 'g.', ms=MARKER_SIZE)
            ax.plot(dday[ii], dh_mean_bad[ii], 'r.', ms=MARKER_SIZE)
            ax.set_ylabel('deg')
            ax.set_xlim([ddmin, ddmax])
            ax.yaxis.set_major_locator(MaxNLocator(5, prune='both'))
            ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
            ax.set_ylim(self.yrange)
            ax.tick_params(direction='in')
        if self.proc_yearbase is None:
            ax.set_xlabel('decimal day')
        else:
            ax.set_xlabel('decimal day, year=%d' % (self.proc_yearbase,))
        fig.suptitle(self.titlestr)
        return fig


#  The EnsHcorr_Plot class below is a non-GUI modificatio
#  of patch_hcorr, illustrating what the buttons are
#  connected to.
class EnsHcorr_Plot():
    def __init__(self, filename='ens_hcorr.asc', sonar='', parent=None):
        """
        Read and filter the data. Make axes and plot figures

        Args:
            filename: absolute path to *.asc file, str. (usually ens_hcorr.asc)
            title: Window title, str.
            parent: PyQt parent Widget
        """
        # N.B.: based on legacy code, original design by Jules
        # Retrieving data
        # TR: Cannot remember why I wrote that line
        # names = ['dday', 'hd_mean', 'hd_last', 'dh_mean', 'dh_std',
        #          'n_used', 'badmask', 'Npersist']
        # dtype = np.dtype({'names': names, 'formats': [np.float64]*8})
        comment = guess_comment(filename)
        _hcorr = loadtxt_(filename, comments=comment, ndmin=2)
        nr, nc = _hcorr.shape
        if nc == 7:
            hcorr = np.zeros((nr, 8), dtype=np.float64)
            hcorr[:, :7] = _hcorr
        else:
            hcorr = _hcorr
            # hcorr = hcorr.view(dtype).ravel()  # TR: Cannot remember why I wrote that line
        # Attributes
        # - data
        self.sonar = sonar
        self.hcorr = hcorr
        self.hdict = {'idday': 0, 'ihead_m': 1, 'ihead_l': 2, 'idh': 3,
                      'istd': 4, 'indh': 5, 'ibad': 6}
        self.badflags = hcorr[:, self.hdict['ibad']]
        self.dday = hcorr[:, self.hdict['idday']]
        self.xlim = [self.dday[0], self.dday[-1]]
        self.gaps = np.ma.masked_where(
            self.badflags == 0, hcorr[:, self.hdict['idh']])
        self.orig_hcorr = np.ma.masked_where(
            self.badflags == 1, hcorr[:, self.hdict['idh']])
        self.last_heading = np.ma.masked_where(
            self.badflags == 1, hcorr[:, self.hdict['ihead_l']])
        self.mean_heading = np.ma.masked_where(
            self.badflags == 1, hcorr[:, self.hdict['ihead_m']])
        self.number_good = np.ma.masked_where(
            self.badflags == 1, hcorr[:, self.hdict['indh']])
        self.orig_stddev = np.ma.masked_where(
            self.badflags == 1, hcorr[:, self.hdict['istd']])
        # - masked data
        self.median_hcorr = np.ma.copy(self.orig_hcorr)
        self.cutoff_stddev = np.ma.copy(self.orig_stddev)
        self.cutoff_number = np.ma.copy(self.number_good)
        self.filtered_hcorr = np.ma.copy(self.orig_hcorr)
        self.final_hcorr = np.ma.copy(self.orig_hcorr)
        # - mask
        self.zapperMask = np.zeros(self.dday.shape, dtype=bool)
        # - paths
        self.rotate_path = os.path.dirname(filename)
        self.ascfile = os.path.join(self.rotate_path, 'newhcorr.asc')
        self.angfile = os.path.join(self.rotate_path, 'newhcorr.ang')
        # - plotting artists
        #   * data plots
        #     + top panel
        self.nbGoodPlot = None
        self.meanHeadingPlot = None
        self.lastHeadingPlot = None
        self.nbGoodHLine = None
        #     + second panel
        self.origStddevPlot = None
        self.cutoffStddevPlot = None
        self.cutoffStddevHLine = None
        #     + third panel
        self.origHCorrPlot1 = None
        self.medianHCorrPlot = None
        #     + bottom panel
        self.origHCorrPlot2 = None
        self.finalHCorrPlot = None
        self.gapsPlot = None
        #   * zapper plots
        self.discardedPtsPlot = None
        self.filteredHCorrPlot = None
        self.finalHCorrPlot2 = None
        self.gapsPlot2 = None
        #   * general
        self.data_artist_list = [
            'nbGoodPlot', 'meanHeadingPlot', 'lastHeadingPlot', 'nbGoodHLine',
            'origStddevPlot', 'cutoffStddevPlot', 'cutoffStddevHLine',
            'origHCorrPlot1', 'medianHCorrPlot', 'origHCorrPlot2',
            'finalHCorrPlot', 'gapsPlot']
        self.zapper_artist_list = [
            'discardedPtsPlot', 'filteredHCorrPlot', 'finalHCorrPlot2',
            'gapsPlot2']
        # - special attributes
        self.set_parent(parent)
        # Initialization
        self.set_up_plots()
        self.update()
        self.make_legend()
        # self.panelsFig.legend(loc='center right', fontsize='small')
        self.zapperFig.legend(fontsize='small')
        self.ax0_heading.set_xlim(self.xlim)

    def run_filters(self, medcutoff=3, medfilt_win=31, stdcutoff=3.0,
                    goodcutoff=20, smboxwidth=3, mask=None,
                    deglitch=False, run_boxfilt=False):
        """
        Run filters

        Args:
            medcutoff: median cut-off, int.
            medfilt_win: median filter window, int.
            stdcutoff: standard deviation cut-off, float
            goodcutoff: "number good" cut-off, int.
            smboxwidth: smooth box width, int.
            mask: zapper mask, masked array
            deglitch: boolean switch
            run_boxfilt: boolean switch
        """
        msg = "=Applying Filters="
        _log.debug(msg)
        self._print("\n" + msg)
        # filter by median cutoff
        medfilt_win = int((2 * medfilt_win) - 1)
        S = Runstats(np.ma.copy(self.orig_hcorr), medfilt_win)
        self.median_hcorr = S.medfilt(tol=float(medcutoff))
        self._print('\n- Runstats median filter: ')
        self._print('\n  * window is %d points' % medfilt_win)
        self._print('\n  * tolerance is  %2.1f' % medcutoff)
        # filter by median cutoff
        self.cutoff_stddev = np.ma.masked_where(
            self.orig_stddev.data > stdcutoff, np.ma.copy(self.orig_stddev))
        self._print('\n- Runstats stddev cutoff filter: ')
        self._print('\n  * cutoff is  %2.1f' % stdcutoff)
        self._print('\n  * %s points were masked' %
                    self.cutoff_stddev.mask.sum())
        # filter by number-good cutoff
        self.cutoff_number = np.ma.masked_where(
            self.number_good.data < goodcutoff, np.ma.copy(self.number_good))
        self._print('\n- Runstats number-good cutoff filter: ')
        self._print('\n  * cutoff is  %2.1f' % goodcutoff)
        self._print('\n  * %s points were masked' %
                    self.cutoff_number.mask.sum())
        # merge filtering masks
        self.filtered_hcorr = np.ma.copy(self.median_hcorr)
        self.filtered_hcorr.mask = np.ma.mask_or(
            self.filtered_hcorr.mask, self.cutoff_stddev.mask)
        self.filtered_hcorr.mask = np.ma.mask_or(
            self.filtered_hcorr.mask, self.cutoff_number.mask)
        # Smoothing
        if run_boxfilt:
            self._print('\nRunning boxfilt: ')
            smboxwidth = 2 * int(smboxwidth) - 1
            self._print('\n  runstats with %d points' % smboxwidth)
            R = Runstats(self.filtered_hcorr[:], smboxwidth)
            self.filtered_hcorr = R.mean
        # Deglitching
        if deglitch:
            self._print('\nDeglitching')
            deglitched = np.ma.masked_where(
                cleaner.multiglitch(self.orig_hcorr.data) == 1,
                np.ma.copy(self.orig_hcorr))
            self.filtered_hcorr.mask = np.ma.mask_or(
                self.filtered_hcorr.mask, deglitched.mask)
        # zapper masking
        self.final_hcorr = np.ma.copy(self.filtered_hcorr)
        if mask is not None:
            self.final_hcorr.mask = np.ma.mask_or(
            self.final_hcorr.mask, mask)
            self._print('\nMasking:')
            self._print('\n  adding (up to) %d points to mask' % mask.sum())
            self._print('\n  total masked = %d points' % self.final_hcorr.mask.sum())
        # Some of Jules' magic (notes: these indices might be off by one)
        firstlast = np.ma.flatnotmasked_edges(self.final_hcorr)
        if firstlast is not None:
            i0, i1 = firstlast
            self.final_hcorr.data[:i0] = self.final_hcorr.data[i0]
            self.final_hcorr.mask[:i0] = False
            self.final_hcorr.data[i1:] = self.final_hcorr.data[i1]
            self.final_hcorr.mask[i1:] = False
            mask = self.final_hcorr.mask
            data = self.final_hcorr.data
            interp_data = interp1(
                self.dday[~mask], data[~mask], self.dday)
            # EF: The interpolated points are being masked out--is this intentional?
            self.final_hcorr = np.ma.array(interp_data, mask=mask)

    def write_files(self):
        """
        Write newhcorr.asc, newhcorr.ang, rotate_fixed.tmp, unrotate.tmp
        and lst_hdg.tmp
        """
        _log.debug("=Writing Files=")
        # Sanity checks
        for ff in (self.ascfile, self.angfile):
            if os.path.exists(ff):
                self._print("\nWARNING")
                self._print('\n  %s exists: not overwriting' % ff)
                self._print('\n  ----> delete %s, then try again' % ff)
                return 0
        # Writing newhcorr.asc
        ibad = self.hdict['ibad']
        idh = self.hdict['idh']
        numlines = len(self.dday)
        fid = open(self.ascfile, 'w')
        mask = np.ma.copy(self.final_hcorr).mask
        for iline in range(numlines):
            line = self.hcorr[iline, :]
            line[idh] = self.final_hcorr.data[iline]
            if mask[iline] is True:
                line[ibad] = 1
            else:
                line[ibad] = 0
            fid.write('%15.7f %10.2f %10.2f %10.2f %10.2f %10d %10d\n' %
                      (line[0], line[1], line[2], line[3], line[4], line[5],
                       int(line[6])))
        fid.close()
        # Writing newhcorr.ang
        fid = open(self.angfile, 'w')
        for iline in range(numlines):
            line = self.hcorr[iline, :]
            line[idh] = self.final_hcorr.data[iline]  # N.B. Warning: converting a masked element to nan.
            fid.write('%15.7f %10.2f \n' % (line[0], line[3]))
        fid.close()
        # Writing rotate_fixed.tmp, unrotate.tmp and lst_hdg.tmp
        outfile = os.path.join(self.rotate_path, 'rotate_fixed.tmp')
        unrotatefile = os.path.join(self.rotate_path, 'unrotate.tmp')
        lst_hdgfile = os.path.join(self.rotate_path, 'lst_hdg.tmp')
        # Sanity check
        if os.path.exists(outfile):
            self._print("\nWARNING")
            self._print('\n  rotate_fixed.tmp exists -- not writing')
            return numlines
        else:
            # use lst_hdg.tmp to get info because it is most likely
            # to exist (other possibilities include ../../dbinfo.txt)
            self._print(
                '\n--> "rotate_fixed.tmp" can be used to apply the new data')
            vars = Bunch()
            if os.path.exists(lst_hdgfile):
                with open(lst_hdgfile, 'r') as newreadf:
                    lines = newreadf.readlines()
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        if 'dbname:' == parts[0]:
                            vars.dbname = parts[1]
                        if 'year_base=' == parts[0]:
                            vars.year_base = parts[1]
            else:
                vars.dbname = '../../adcpdb/________'
                vars.year_base = 'YYYY'
                self._print('\nEDIT %s and fix dbname, year_base' % outfile)
            with open(outfile, 'w') as file:
                file.write(REROTATE_STR % vars)
            with open(unrotatefile, 'w') as file:
                file.write(UNROTATE_STR % vars)
            self._print('\nWrote "unrotate.tmp"')

        return numlines

    def update(self, mask=None, medfilt_win=31,
               medcutoff=3, deglitch=False, stdcutoff=3.0,
               goodcutoff=20, run_boxfilt=False, smboxwidth=3):
        """
        Run filters, merge zapper mask and update plots
        Args:
            mask: zapper mask, masked array
            medfilt_win: median filter window, int.
            medcutoff: median cut-off, int.
            deglitch: boolean switch
            stdcutoff: standard deviation cut-off, float
            goodcutoff: "number good" cut-off, int.
            run_boxfilt: boolean switch
            smboxwidth: smooth box width, int.
        """
        _log.debug('=Updating=')
        self.run_filters(medcutoff=medcutoff, medfilt_win=medfilt_win,
                         stdcutoff=stdcutoff, goodcutoff=goodcutoff,
                         smboxwidth=smboxwidth, mask=mask,
                         run_boxfilt=run_boxfilt, deglitch=deglitch)
        self.draw_top_panels(stdcutoff=stdcutoff, goodcutoff=goodcutoff,
                             run_boxfilt=run_boxfilt)
        self.draw_zapper_panel()

    def set_parent(self, parent):
        # N.B.: function required for PatchHcorrApp
        self.parent = parent
        if self.parent:
            self._print = self.parent.write_to_log
        else:
            self._print = lambda x: print(x)

    def set_up_plots(self):
        # Panels
        # - data figure
        self.panelsFig = Figure()
        # - zapper figure
        self.zapperFig = Figure()
        # Axes
        left = X0
        bottom = START_Y
        width = 0.9  # pax_width
        height = TOTAL_HEIGHT
        # - data's axes
        self.panelsFig.subplots(nrows=5, sharex=True)
        self.panelsFig.subplots_adjust(
            left=0.1, bottom=0.1, right=0.95, top=0.95, hspace=0.25)
        #  * headings
        self.ax0_heading = self.panelsFig.axes[0]
        self.ax0_heading.grid(True)
        self.ax0_heading.yaxis.set_major_locator(tickerHd)
        self.ax0_heading.tick_params(axis='y')
        self.ax0_heading.set_ylabel('deg.')
        self.ax0_heading.set_ylim(-5, 365)
        self.ax0_heading.title.set_text(
            "Heading feed for the %s" % self.sonar)
        self.ax0_heading.title.set_weight('bold')
        #  * number good
        self.ax1_ndh = self.panelsFig.axes[1]
        self.ax1_ndh.grid(True)
        self.ax1_ndh.yaxis.set_major_formatter(FORMATTER)
        self.ax1_ndh.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        self.ax1_ndh.tick_params(axis='y')
        self.ax1_ndh.set_ylabel('count')
        self.ax1_ndh.title.set_text('Number Good')
        #  * std. dev.
        self.ax2_stddh = self.panelsFig.axes[2]
        self.ax2_stddh.grid(True)
        self.ax2_stddh.yaxis.set_major_formatter(FORMATTER)
        self.ax2_stddh.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        # self.ax2_stddh.set_ylabel('-')
        self.ax2_stddh.title.set_text('Standard Deviation')
        #  * median filter
        self.ax3_medfilt_parts = self.panelsFig.axes[3]
        self.ax3_medfilt_parts.grid(True)
        self.ax3_medfilt_parts.yaxis.set_major_formatter(FORMATTER)
        self.ax3_medfilt_parts.yaxis.set_major_locator(
            MaxNLocator(4, prune='both'))
        self.ax3_medfilt_parts.tick_params(axis='y')
        self.ax3_medfilt_parts.set_ylabel('deg.')
        self.ax3_medfilt_parts.title.set_text('Heading Correction')
        #  * resulting heading correction
        self.ax4_dhfinal = self.panelsFig.axes[4]
        self.ax4_dhfinal.titlesize = 'small'
        self.ax4_dhfinal.grid(True)
        self.ax4_dhfinal.yaxis.set_major_formatter(FORMATTER)
        self.ax4_dhfinal.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        self.ax4_dhfinal.set_ylabel('deg.')
        self.ax4_dhfinal.title.set_text("Resulting heading correction")
        self.ax4_dhfinal.title.set_weight('bold')
        # - zapper's axes
        self.ax_zapper = self.zapperFig.add_axes(
            [left, bottom, width, height],
            sharex=self.ax4_dhfinal, sharey=self.ax4_dhfinal)
        self.ax_zapper.grid(True)
        self.ax_zapper.yaxis.set_major_formatter(FORMATTER)
        self.ax_zapper.yaxis.set_major_locator(MaxNLocator(4, prune='both'))
        self.ax_zapper.set_ylabel('deg.')

    def draw_top_panels(self, stdcutoff=3.0, goodcutoff=20, run_boxfilt=False):
        """
        (re)draw top 2 panels
        """
        _log.debug('=Drawing Top Panels=')
        # clean-up
        for artist_name in self.data_artist_list:
            artist = getattr(self, artist_name)
            reset_artist(artist)
        # Draw plots
        # mean heading
        color = 'k'
        self.meanHeadingPlot = self.ax0_heading.plot(
            self.dday, np.remainder(self.mean_heading, 360), color + '.',
            ms=MARKER_SIZE, label='Mean')
        # last heading
        color = 'b'
        self.lastHeadingPlot = self.ax0_heading.plot(
            self.dday, np.remainder(self.last_heading, 360), color + '.',
            ms=MARKER_SIZE, label='Last')
        # original number good
        self.nbGoodPlot = self.ax1_ndh.plot(self.dday, self.number_good,
                                            '.', color=GREY, ms=MARKER_SIZE,
                                            label='Original')
        # number good cut-off
        color = 'm'
        self.nbGoodHLine = self.ax1_ndh.axhline(
            goodcutoff, color=color, linewidth=1, label='Cutoff')
        self.nbGoodPlot = self.ax1_ndh.plot(self.dday, self.cutoff_number,
                                            '.', color=color, ms=MARKER_SIZE,
                                            label='Filtered')
        # original standard deviation
        color = 'g'
        self.origStddevPlot = self.ax2_stddh.plot(
            self.dday, self.orig_stddev, color + '.',
            ms=MARKER_SIZE, label='Original')
        # cutoff std. dev.
        color = 'orange'
        self.cutoffStddevHLine = self.ax2_stddh.axhline(
            stdcutoff, color=color, linewidth=1, label='Cutoff')
        self.cutoffStddevPlot = self.ax2_stddh.plot(
            self.dday, self.cutoff_stddev, '.', color=color,
            ms=MARKER_SIZE, label='Filtered')
        # median cutoff filter
        color = 'c'
        self.origHCorrPlot1 = self.ax3_medfilt_parts.plot(
            self.dday, self.orig_hcorr,
            '.', ms=MARKER_SIZE, color=GREY,
            label='Original')
        self.medianHCorrPlot = self.ax3_medfilt_parts.plot(
            self.dday, self.median_hcorr, color + '.',
            ms=MARKER_SIZE, label='Median filtered')
        # Resulting heading correction
        orig_goodmask = ~np.ma.getmaskarray(self.orig_hcorr)
        self.origHCorrPlot2 = self.ax4_dhfinal.plot(
            self.dday[orig_goodmask],
            self.orig_hcorr[orig_goodmask],
            '-', color=GREY, ms=MARKER_SIZE,
            label='Original')
        self.finalHCorrPlot = self.ax4_dhfinal.plot(
            self.dday, self.final_hcorr.data,
            color='g', marker='o', linestyle='-', ms=MARKER_SIZE,
            label='Resulting')
        self.gapsPlot = self.ax4_dhfinal.plot(
            self.dday, self.gaps,
            '+', color='r', ms=MARKER_SIZE + 2, label='Gaps')

    def draw_zapper_panel(self):
        """
        Draw zapper panel
        """
        _log.debug('=Drawing Selector Panel=')
        # Clean-up
        for artist_name in self.zapper_artist_list:
            artist = getattr(self, artist_name)
            reset_artist(artist)
        # Draw plots
        # - filtered points
        filteredPts = np.ma.copy(self.filtered_hcorr).data[:]
        filtered_mask = np.ma.copy(self.filtered_hcorr).mask[:]
        filtered_mask[self.badflags == 1] = False
        self.filteredHCorrPlot = self.ax_zapper.plot(
            self.dday[filtered_mask],
            filteredPts[filtered_mask],
            '.', ms=MARKER_SIZE, color='orange',
            label="Filtered points")
        # - Manually discarded points
        x = []
        y = []
        if hasattr(self, 'parent'):
            if hasattr(self.parent, 'zapperPlot'):
                discardedPts = np.ma.copy(self.orig_hcorr).data[:]
                x = self.dday[self.parent.zapperPlot.mask]
                y = discardedPts[self.parent.zapperPlot.mask]
        self.discardedPtsPlot = self.ax_zapper.plot(
            x, y,
            '.', color='purple', ms=MARKER_SIZE,
            label='Manually discarded points')
        # - Gaps in heading
        self.gapsPlot2 = self.ax_zapper.plot(
            self.dday, self.gaps, '+', color='r', ms=MARKER_SIZE + 2,
            label='Gaps in heading feed')
        # - Resulting plot
        self.finalHCorrPlot2 = self.ax_zapper.plot(
            self.dday[~self.final_hcorr.mask],
            self.final_hcorr[~self.final_hcorr.mask],
            color='g', marker='o', linestyle='-', ms=MARKER_SIZE,
            label="Resulting heading correction")

    def make_legend(self):
        kwargs = {'fontsize': 'small', 'loc': 1} # , 'bbox_to_anchor': (1.01, 1)}
        self.ax0_heading.legend(ncol=2, **kwargs)
        self.ax1_ndh.legend(ncol=3, **kwargs)
        self.ax2_stddh.legend(ncol=3, **kwargs)
        self.ax3_medfilt_parts.legend(ncol=2, **kwargs)
        self.ax4_dhfinal.legend(ncol=3, **kwargs)
        # self.ax_zapper.legend(**kwargs)


if __name__ == '__main__':
    from pycurrents.get_test_data import get_test_data_path  # BREADCRUMB: common library
    test_folder_path = get_test_data_path()
    test_path = test_folder_path + '/uhdas_data/proc/os75nb/'
    pathcHcorr = PatchHcorrApp(working_dir=test_path)

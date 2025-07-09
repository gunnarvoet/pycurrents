#!/usr/bin/env python3
import sys
import os
import logging

# Standard imports
import numpy as np

from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter

from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import (
    QMainWindow,
    QRadioButton,
    QCheckBox,
    QWidget,
    QHBoxLayout,
    QApplication,
)
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIcon

from pycurrents.adcpgui_qt.lib.qtpy_widgets import (
    CustomLabel,
    CustomPushButton,
    iconUHDAS,
    CustomPanelVLayout,
)
from pycurrents.adcpgui_qt.lib.qtpy_widgets import green, backGroundKey, globalStyle
from pycurrents.adcpgui_qt.apps.generic_app_components import GenericPlotWindow

from pycurrents.data.nmea.qc_rbin import RbinSet  #qc_rbin
from pycurrents.data import navcalc
from pycurrents.file.binfile_n import BinfileSet  # concatenated rbins
from pycurrents.num import Stats
from pycurrents.num.int1 import interp1, NonuniformError

# Standard logging
_log = logging.getLogger(__name__)


class PlotRbinApp(QMainWindow):
    def __init__(self, uhdas_dir='./', rname1='', rname2='', step=1, shift=0,
                 splitchar=':', stathrs = 4.0,  # not implemented yet
                 marker_size=2, max_dx=None, masked=False, ddrange=None,
                 parent=None, test=False):
        # Starting up application
        if test:
            self.app = test
        else:
            self.app = QApplication(sys.argv)
            try:
                self.app.setStyle(globalStyle)
            except RuntimeError:  # in case chosen style not available
                pass

        # Inheritance
        super().__init__(parent)

        # Attributes
        self.uhdas_dir = uhdas_dir
        self.work_dir = os.path.relpath(self.uhdas_dir, os.getcwd())
        self.serial1 = rname1
        self.serial2 = rname2
        self.splitchar = splitchar
        self.ddrange = ddrange
        self.step = step
        self.shift = shift
        self.ms = marker_size
        self.max_dx = max_dx
        self.masked = masked
        self.data1 = None
        self.data2 = None
        self.abscissa = []
        self.color1 = 'blue'
        self.color2 = 'red'
        # - plotting attr.
        self.ledg_handle_diff = False
        self.ledg_handle_ser1 = False
        self.ledg_handle_ser2 = False

        # Data
        self.fetch_data()

        # Widgets
        widgets = []
        # - Labels
        self.label_title = CustomLabel("rbin Plotting", style='h1')
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_sub_title = CustomLabel("Variables to plot:", style='h2')
        self.label_abscissa = CustomLabel("Abscissa", style='h3')
        self.label_serial1 = CustomLabel(rname1, style='h3', color=self.color1)
        self.label_workdir = CustomLabel("Work. dir.:%s" % self.work_dir, style='h3')
        widgets.append(self.label_title)
        widgets.append(self.label_sub_title)
        if self.serial2:
            self.label_serial2 = CustomLabel(rname2, style='h3', color=self.color2)
        # - Radio buttons
        self.radio_buttons = {}
        for ci in range(len(self.abscissa))[::-1]: # do it backwards to get u_dday as abcissa
            absci = self.abscissa[ci]
            _log.debug("Abscissa name %s: %s", ci, absci)
            self.radio_buttons[absci] = QRadioButton(absci)

        self.radio_buttons[absci].setChecked(True)
        # - Check boxes
        self.check_boxes_serial1 = {}
        self.check_boxes_serial2 = {}
        for cname in self.data1.columns:
            self.check_boxes_serial1[cname] = QCheckBox(cname)
        if self.data2:
            for cname in self.data2.columns:
                self.check_boxes_serial2[cname] = QCheckBox(cname)
        # - Plot Button
        self.button_plot = CustomPushButton('Plot')
        self.button_plot.setStyleSheet(backGroundKey + green)

        # Layout
        # - radio buttons container
        self.radio_buttons_container = QWidget(self)
        CustomPanelVLayout(
            [self.label_abscissa] + list(self.radio_buttons.values()),
            self.radio_buttons_container
        )
        # - serial 1 check boxes container
        self.serial1_checkboxes_container = QWidget(self)
        CustomPanelVLayout(
            [self.label_serial1] + list(self.check_boxes_serial1.values()),
            self.serial1_checkboxes_container
        )
        # - serial 2 check boxes container
        if self.serial2:
            self.serial2_checkboxes_container = QWidget(self)
            CustomPanelVLayout(
                [self.label_serial2] + list(self.check_boxes_serial2.values()),
                self.serial2_checkboxes_container
            )
        # - radio buttons and checkboxes container
        self.mix_container = QWidget(self)
        hlayout = QHBoxLayout(self.mix_container)
        hlayout.addWidget(self.radio_buttons_container)
        hlayout.addWidget(self.serial1_checkboxes_container)
        if self.serial2:
            hlayout.addWidget(self.serial2_checkboxes_container)
        widgets.append(self.mix_container)
        widgets.append(self.button_plot)
        widgets.append(self.label_workdir)
        # - central layout
        self.central_box = QWidget(self)
        CustomPanelVLayout(widgets, self.central_box)
        self.setCentralWidget(self.central_box)

        # Style
        self.setWindowTitle("rbin plotting control Window")
        self.setWindowIcon(QIcon(iconUHDAS))

        # Connect
        self.button_plot.clicked.connect(self.plot)

        # Kick start application
        self.show()
        # - Exit when done
        if not test:
            sys.exit(self.app.exec_())

    def fetch_data(self):
        # Fetch data for first serial
        ser1, msg1 = get_inst_msg(self.serial1, self.uhdas_dir,
                                  splitchar=self.splitchar)
        rstr1 = os.path.join(self.uhdas_dir, 'rbin', ser1, '*.%s.rbin' % (msg1))
        _log.debug("Serial 1 rbin str:%s", rstr1)

        if self.masked:
            self.data1 = RbinSet(rstr1, step=int(self.step))
        else:
            self.data1 = BinfileSet(rstr1, step=int(self.step))
        if 'lat' in self.data1.columns:
            self.data1.hy, self.data1.hx = navcalc.lonlat_metrics(self.data1.lat)

        # Fetch data for second serial
        if self.serial2:
            ser2, msg2 = get_inst_msg(self.serial2, self.uhdas_dir,
                                      splitchar=self.splitchar)
            rstr2 = os.path.join(self.uhdas_dir,'rbin', ser2, '*.%s.rbin' % (msg2))
            _log.debug("Serial 2 rbin str:%s", rstr2)

            if self.masked:
                self.data2 = RbinSet(rstr2, step=int(self.step))
            else:
                self.data2 = BinfileSet(rstr2, step=int(self.step))
            if 'lat' in self.data2.columns:
                self.data2.hy, self.data2.hx = navcalc.lonlat_metrics(self.data2.lat)

        # Get overlapping abcissa
        if self.data2 is None:
            columns = self.data1.columns
        else:
            columns = []
            for cname in self.data1.columns:
                if cname in self.data2.columns:
                    columns.append(cname)
        self.abscissa = columns

        # Slice data
        if self.ddrange is not None:
            parts = self.ddrange.split(':')
            _range = [int(parts[0]), int(parts[-1])+1]
            self.data1.set_range(ddrange=_range, cname='u_dday')
            if self.data2 is not None:
                self.data2.set_range(ddrange=_range, cname='u_dday')

    def plot(self):
        self.ledg_handle_diff = False
        self.ledg_handle_ser1 = False
        self.ledg_handle_ser2 = False
        # Collect user choices
        # - abscissa
        for chosenX, widget in self.radio_buttons.items():
            if widget.isChecked():
                break
        _log.debug("Abscissa: %s", chosenX)
        # - serial 1
        chosenY1 = []
        for vv, widget in self.check_boxes_serial1.items():
            if widget.isChecked():
                chosenY1.append(vv)
        _log.debug("chosenY1: %s", chosenY1)
        # - serial 2
        chosenY2 = []
        chosenYall = chosenY1.copy()
        if self.serial2:
            for vv, widget in self.check_boxes_serial2.items():
                if widget.isChecked():
                    chosenY2.append(vv)
                    if vv not in chosenYall:
                        chosenYall.append(vv)
            _log.debug("chosenY2: %s", chosenY2)
            _log.debug("chosenYall: %s", chosenYall)

        ### Legacy code ###
        ## look at duplicated and singles separately
        singley = []
        duply = []
        for cname in chosenYall:
            if ((cname in chosenY1) and (cname not in chosenY2)) or \
                    ((cname in chosenY2) and (cname not in chosenY1)):
                singley.append(cname)
            else:
                duply.append(cname)

        # FIXME: defining attr. outside of --init-- is bad practise
        self.chosenY1 = chosenY1
        self.chosenY2 = chosenY2
        self.chosenYall = chosenYall
        self.chosenX = chosenX
        self.duply = duply

        ax = None
        spnum = 1
        for cname in singley:
            ax1 = self.plotdata(ax, spnum=spnum, cname=cname, diff=False,
                                shift=self.shift, max_dx=self.max_dx)
            # Success?
            if ax1:
                spnum += 1
                ax = ax1
                ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
                ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        for cname in duply:
            ## do both
            ax1 = self.plotdata(ax, spnum=spnum, cname=cname, diff=False,
                                shift=self.shift, max_dx=self.max_dx)
            # Success?
            if ax1:
                spnum += 1
                ax = ax1
                ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
                ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
            ## do diffs
            ax1 = self.plotdata(ax, spnum=spnum, cname=cname, diff=True,
                                shift=self.shift, max_dx=self.max_dx)
            if ax1:
                spnum += 1
                ax = ax1
                ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
                ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))

        if ax:
            ax.set_xlabel(chosenX)
            ax.figure.text(.5, .95, self.work_dir, ha='center')

        # Legend
        handles = []
        labels = []
        if self.ledg_handle_ser1:
            handles.append(self.ledg_handle_ser1[0])
            labels.append(self.ledg_handle_ser1[1])
        if self.ledg_handle_ser2:
            handles.append(self.ledg_handle_ser2[0])
            labels.append(self.ledg_handle_ser2[1])
        if self.ledg_handle_diff:
            handles.append(self.ledg_handle_diff[0])
            labels.append(self.ledg_handle_diff[1])
        if handles:
            if self.ms >= 6:
                markerscale = 1
            else:
                markerscale = 8
            self.fig.legend(handles, labels, loc='upper right',
                            fontsize='small', markerscale=markerscale)

        # Refresh
        self.plotwindow.show()

    def plotdata(self, axh, spnum=1, cname=None, diff=False, shift=0, max_dx=None):
        ### Legacy code ###
        ''' first call, axh is fig; put subplots there
             thereafter,  is first axis (for sharex)

             spnum is subplotnum

             run through singles first
             pairs are plotted as such, then the difference is plotted'''
        # Sanity check and pre-calc
        if diff:
            try:
                abc1 = self.data1.records[self.chosenX]+shift
                abc2 = self.data2.records[self.chosenX]
                ord2 = self.data2.records[cname]
                ord1 = self.data1.records[cname]
                if max_dx is None:
                    s = Stats(np.diff(abc1))
                    max_dx = s.median * 10.0
                ord2_ = interp1(abc2, ord2, abc1, max_dx=max_dx)
            except NonuniformError:
                msg = ("ERROR: Cannot Print %s vs. %s!"
                       "Invalid input for interp1: "
                       "The first argument has duplicate values") % (
                    cname, self.chosenX)
                _log.error(msg)
                print(msg)
                return

        # get ordinate column, rbin#1
        # FIXME: numplots is wrong when some figures cannot be made
        numplots = len(self.chosenYall) + len(self.duply)  # for diffs

        if axh:
            ss = self.fig.add_subplot(numplots,1,spnum, sharex=axh)
            if spnum >= 0:
                ss.xaxis.set_ticklabels([])
        else:  #first, or do not share x
            self.fig = Figure()
            ss = self.fig.add_subplot(numplots, 1, spnum)
            self.plotwindow = self.colorPlot = GenericPlotWindow(
                self.fig, title='Plotting Window',
                ref_axis=ss, with_toolbar=True, parent=self)
            self.plotwindow.canvas.draw()

        if diff:
            if cname == 'lon':
                dx = np.interp(abc1, abc2, self.data2.hx)
                dh = dx*(np.ma.remainder(ord2_ - ord1 + 90, 360) - 90)
            elif cname == 'lat':
                dy = np.interp(abc1, abc2, self.data2.hy)
                dh = dy*(np.ma.remainder(ord2_ - ord1 + 90, 360) - 90)
            elif cname in ('dday','u_dday'):
                dt = np.ma.remainder(ord2_ - ord1 + 90, 360) - 90
                dh = 86400*dt
            else:
                dh = np.ma.remainder(ord2_ - ord1 + 90, 360) - 90

            p = ss.plot(abc1,  dh, 'k.', mfc='k', mew=0, ms=self.ms)

            if cname == 'heading':
                ss.set_ylim(-10,10)

            if diff:
                ylstr = '%s (R2-R1)' % (cname,)
                if cname in ['lon','lat']:
                    ylstr = ylstr+ 'm'
            else:
                ylstr = cname
            ss.set_ylabel(ylstr)
            if not self.ledg_handle_diff:
                self.ledg_handle_diff = [p[0], "Diff."]
        else:
            if cname in self.chosenY1:
                p1 = ss.plot(self.data1.records[self.chosenX], self.data1.records[cname],
                              '.', mew=0, ms=self.ms, mfc=self.color1, label=self.serial1)
                ss.set_ylabel(cname)
                if not self.ledg_handle_ser1:
                    self.ledg_handle_ser1 = [p1[0], self.serial1]

            if cname in self.chosenY2:
                p2 = ss.plot(self.data2.records[self.chosenX], self.data2.records[cname],
                              '.', mew=0, ms=self.ms, mfc=self.color2, label=self.serial2)
                ss.set_ylabel(cname)
                if not self.ledg_handle_ser2:
                    self.ledg_handle_ser2 = [p2[0], self.serial2]

        return ss


# Local Lib
def get_inst_msg(name, uhdas_dir, splitchar=':'):
    '''
    split, then check options to get valid inst,msg pair.  return it
    max number of underscores in name is 2
    '''
    rbindir = os.path.join(uhdas_dir,'rbin')
    parts=name.split(splitchar)
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        # assuming: len(parts) == 3
        # eg. message = 'tss1_hnc'
        if os.path.exists(os.path.join(rbindir, parts[0])):
            return parts[0], '_'.join(parts[-2:])
        else:
            # eg. instrument = 'coda_f185 '
            mstr = '_'.join(parts[:2])
            if os.path.exists(os.path.join(rbindir, mstr)):
                return mstr, parts[2]
            else:
                raise ValueError('cannot determine inst_msg from %s' % (name))


if __name__ == '__main__':
    usage = '''
    This is a simple rbin plotter -- plot one or 2 sets of y versus the same x
    -  choose abcissa (radio button)
    -  plot against chosen ordinates in subplots
    -  one color per instrument; one subplot per ordinate
    -  for each field that is duplicated, plot the difference as well.
    -       differences in lon or lat ar plotted in meters


    specify rbin directory, instrument directory, and message name:
     eg:
    plot_rbins.py --ser1 posmv:pmv --ser2 gyro:hnc uhdasdir
    plot_rbins.py  -s gyro:hnc --step 10  uhdasdir
    '''
    from argparse import ArgumentParser
    arglist = sys.argv[1:]
    parser = ArgumentParser(usage=usage)
    parser.add_argument("uhdas_dir", help="path to UHDAS directory")
    parser.add_argument("--ser1", "-s",  dest='ser1', required=True,
                        help="inst:msg1 - serial instrument #1"
                             "  inst=directory, msg=rbin message")
    parser.add_argument("--ser2",   dest='ser2',   default=None,
                        help="inst:msg2 - serial instrument #2"
                             "  inst=directory, msg=rbin message")
    parser.add_argument("--step",   dest='step',   default=1,
                        help="step size - extract every Nth message"
                             " (default is every step)\n"
                             "(speeds up plotting, might create problems"
                             " with differences)")
    parser.add_argument("--splitchar",   dest='splitchar',   default=':',
                        help="specify different splitter. Ex.: "
                             "use  --splitchar ','  and --ser1 inst,msg "
                             "--ser2 inst,msg")
    parser.add_argument("--shift",  dest='shift',  default=0,
                        help='add seconds to ser1')
    parser.add_argument("--ddrange",dest='ddrange', default=None,
                        help='colon-delimited integer decimal day range')
    parser.add_argument("--masked", action="store_true", dest="masked",
                        default=False,
                        help="use QC masks when plotting "
                             "(eg. ashtech, posmv, seapath)")
    parser.add_argument("--markersize", dest="marker_size", default=2,
                        type=int, help="Marker size. default is 2; max. is 6")
    parser.add_argument("--max_dx", dest="max_dx", default=None, type=float,
                        help="maximum gap for interpolation")

    options = parser.parse_args(args=arglist)

    PlotRbinApp(uhdas_dir=options.uhdas_dir,
                rname1=options.ser1,
                rname2=options.ser2,
                step=options.step,
                shift=options.shift,
                splitchar=options.splitchar,
                marker_size=options.marker_size,
                max_dx=options.max_dx,
                ddrange=options.ddrange,
                masked=options.masked)

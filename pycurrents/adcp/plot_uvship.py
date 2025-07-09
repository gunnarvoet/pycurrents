'''
Specialized diagnostic plotting.

comparison plot of ship speeds calculated using two methods
 - codas fixes (first difference of the ensemble endpoints)
 - average of single-point ship speeds for 'good' profiles only

usage:

    plot_uvship.py filename

where the filename specifies a file used by the 'putnav'
program to add position and ship velocity data to a CODAS
database.
'''


import sys
import logging
from optparse import OptionParser
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.plot.mpltools import savepngs
from pycurrents.num.nptools import loadtxt_

# Standard logging
_log = logging.getLogger(__name__)


def plot_uvship(fname, maxshipspeed=6):
    '''
    assumes a 'putnav' file, with
    [dday, ushipma, vshipma, uship, vship, lon, lat, N], where
    -  ushipma, vshipma are means of single-ping ship speeds for
              profiles that are used in umeas, vmeas
    - uship, vship are first difference from lon, lat (traditional)
    '''

    dday, usma, vsma, us, vs, lon, lat, N = loadtxt_(fname, unpack=True)

    f,ax = plt.subplots(nrows=3, sharex=True, figsize=(8,10))
    ax[0].plot(dday, us,'r.')
    ax[0].plot(dday, usma,'g')
    ax[0].plot(dday, vs,'b.')
    ax[0].plot(dday, vsma,'c')

    ax[0].xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
    ax[0].set_ylim([-maxshipspeed, maxshipspeed])
    ax[0].set_ylabel('m/s')
    ax[0].text(.05,.90,'ushipnav',transform=ax[0].transAxes, color='r')
    ax[0].text(.95,.90,'vshipnav',transform=ax[0].transAxes, color='b', ha='right')
    ax[0].text(.05,.82,'ushipma',transform=ax[0].transAxes, color='g')
    ax[0].text(.95,.82,'vshipma',transform=ax[0].transAxes, color='c', ha='right')
    ax[0].grid(True)
    ax[0].set_xlim([dday[0], dday[-1]])

    ax[1].plot(dday, us-usma,'r.-')
    ax[1].plot(dday, vs-vsma,'b.-')
    ax[1].set_ylim([-1.,1])
    ax[1].set_ylabel('m/s')
    ax[1].text(.05,.90,'ushipnav - ushipma',
            transform=ax[1].transAxes, color='r')
    ax[1].text(.95,.90,'vshipnav - vshipma',
            transform=ax[1].transAxes, color='b', ha='right')
    ax[1].grid(True)

    ax[2].plot(dday, N,'k.')
    ax[2].text(.05,.1,'number in average', color='k',
                transform=ax[2].transAxes)
    ax[2].grid(True)
    ax[2].set_xlabel('decimal day')
    f.text(.5,.92,'\n'.join(['ship speed comparison:',
         '"nav" = traditional = first difference from ensemble "fix"',
         '"ma" = new "uvship" method: averaged speeds from ping-based fixes']),
           ha='center')

    return f


def main():

    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()

    parser = OptionParser(__doc__)


    parser.add_option("-o", "--outfile", dest="outfile",
                      default = None,
                      help="save figure as OUTFILE.png")

    parser.add_option("--maxspeed", dest="maxspeed",
                      default = 6.5,
                      help="max shipspeed")

    parser.add_option("--noshow", dest="show", action="store_false",
                      default=True,
                      help="do not display figure")

    (options, args) = parser.parse_args()

    if len(args) != 1:
        _log.error('no file specifled')

    fname = args[0]


    fig = plot_uvship(fname, float(options.maxspeed))

    restore_ion = False
    if not options.show and plt.isinteractive():
        plt.ioff()
        restore_ion = True

    if options.outfile is not None:
        savepngs(options.outfile, dpi=72, fig=fig)

    if options.show:
        plt.show()

    if restore_ion:
        plt.ion()

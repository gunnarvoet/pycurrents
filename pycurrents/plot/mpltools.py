"""
Functions to aid plotting with mpl.

"""

import time
import os
import shutil
import subprocess
from datetime import datetime, timedelta
import logging

import numpy as np

import matplotlib as mpl
from matplotlib.dates import date2num
from matplotlib.colors import hsv_to_rgb
from matplotlib import ticker
import matplotlib.transforms as mtransforms
import matplotlib.lines as mlines
from matplotlib.pyplot import get_cmap as _get_cmap
# I would prefer to avoid the pyplot import here, but during the colormap
# handling transition around mpl versions 3.5-3.7 it is probably worth it to
# avoid having version-specific code.

_log = logging.getLogger(__name__)

# Imagemagick is changing from 'convert' to 'magick convert', so try the
# newer version first:
for _name in ['magick convert', 'convert']:
    try:
        subprocess.run(_name, stdout=subprocess.DEVNULL,
                       stderr=subprocess.STDOUT)
        _convert_cmd = _name
        break
    except FileNotFoundError:
        _convert_cmd = None


try:
    subprocess.run('pngquant', stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT)
    _have_pngquant = True
except FileNotFoundError:
    _have_pngquant = False
except:
    _log.exception("unexpected exception when checking for pngquant")
_log.debug("_have_pngquant = %s", _have_pngquant)

_pngquant = _have_pngquant

def set_pngquant(true_false):
    """
    Set the default quantization behavior in savepngs.
    """
    global _pngquant
    tf = bool(true_false)
    if _have_pngquant:
        _pngquant = tf
        return
    if tf:
        raise RuntimeError('The pngquant executable was not found')
    _pngquant = False

#########################################################

# Functions to allow use of some pyplot functionality
# if in interactive mode, without requiring that pyplot
# be imported when not in interactive mode.
# Experimental.

def draw_if_interactive():
    """
    Imports pyplot only if mpl is in interactive mode.
    Then it runs plt.draw_if_interactive(), which acts
    only if there is a pyplot current figure.
    """
    if mpl.is_interactive():
        import matplotlib.pyplot as plt
        plt.draw_if_interactive()

def sca_if_interactive(ax):
    """
    Imports pyplot only if mpl is in interactive mode.
    If there is no pyplot figure manager with a current
    figure, it will have no effect.
    """
    if mpl.is_interactive():
        import matplotlib.pyplot as plt
        try:
            plt.sca(ax)
        except:
            pass

######################################################

class DegreeFormatter(ticker.Formatter):
    def __init__(self, fmt="%s"):
        self.fmt = fmt

    def __call__(self, x, pos=None):
        if abs(x - int(x)) < 0.0001:
            x = int(x)
        xf = self.fmt % x
        return u'%s\N{DEGREE SIGN}' % xf

def degticks(ax, axis, **kw):
    """
    Format an axis with degree symbols.

    Arguments:

    *ax*
        Axes

    *axis*
        ['x' | 'y' | 'xy']

    If Keyword arguments are supplied, they will be used
    to initialize a MaxNLocator.

    """
    if axis not in ['x', 'y', 'xy']:
        raise ValueError("second argument must be 'x' or 'y'")

    if 'x' in axis:
        ax.xaxis.set_major_formatter(DegreeFormatter())
        if kw:
            ax.xaxis.set_major_locator(ticker.MaxNLocator(**kw))
    if 'y' in axis:
        ax.yaxis.set_major_formatter(DegreeFormatter())
        if kw:
            ax.yaxis.set_major_locator(ticker.MaxNLocator(**kw))


def station_marks(ax, x, y=1, marker=None, **kw):
    """
    Make a row of marks for station locations at abcissa
    locations *x* in data coordinates, and at ordinate location
    *y* in Axes coordinates.  *y* defaults to 1 (top of plot).
    *marker* defaults to a vertical bar.  Remaining kwargs
    are passed to the Line2D object, which is returned.

    """
    # modeled on Axes.axvline etc.
    if marker is None:
        marker = '|'
        kw.setdefault('markeredgewidth', 2.5)
        kw.setdefault('markersize', 14)
        kw.setdefault('markeredgecolor', 'k')

    trans = mtransforms.blended_transform_factory(
            ax.transData, ax.transAxes)

    line = mlines.Line2D(x, [y]*len(x), linestyle='None',
                         marker=marker, transform=trans, **kw)
    line.y_isdata = False
    ax.add_line(line)
    return line




def dday_to_mpl(yearbase, dday):
    """
    Convert dday with yearbase to mpl date num

    yearbase must be a scalar
    dday may be a scalar or sequence

    """
    offset = date2num(datetime(yearbase, 1, 1))
    try:
        return dday + offset
    except TypeError:
        return [d + offset for d in dday]


def shorten_ax(ax, newyfrac=.1):
    '''
    shorten one axes in the y direction.
    "newyfrac" changes the location of the top or bottom of an axes object
    newyfrac is the fraction of the present height to change by
    positive value raises the bottom; negative values lower the top
    '''

    ## new transforms require parsing a Bbox object
    [xstart, ystart , width, height] = ax.get_position().bounds

    if newyfrac > 0:  # raise the bottom
        newystart = ystart + newyfrac*height
        newpos = [xstart, newystart, width, height - (newystart-ystart)]
    else:
        newheight =  height + newyfrac*height  # lower
        newpos = [xstart, ystart, width, newheight]

    ax.set_position(newpos)


def nowstr():
    '''
    get utc time from computer clock, return string "yyyy/mm/dd hh:mm:ss"
    '''
    return time.strftime("%Y/%m/%d %H:%M:%S")


def savepngs(outfilebase, dpi, fig = None, altdirs=None, quant=None, **kw):
    '''
    Save png files with each of one or more dpi values.

    'outfilebase', 'dpi', and 'altdirs' must be single values or lists.
    The number of file paths must match the number of dpi values, and the
    number of altdirs must be either one or the number of dpi values.

    Normally the 'quant' kwarg should be left as its default, None, so that
    pngquant will be used if it is available.  If it should not be used, set
    'quant' to False.  If a default of False has been set globally via
    'set_pngquant(False)', then the kwarg here can be set to True to override
    that default.  The purpose of pngquant is to shrink the output file by
    using a palette instead of RGBA.

    Additional keyword arguments can be passed to savefig via **kw.
    facecolor and edgecolor default to their original figure values,
    as displayed on the screen.
    '''
    if quant is None:
        quant = _pngquant
    else:
        if quant and not _have_pngquant:
            raise RuntimeError('The pngquant executable was not found;'
                               ' use "quant=None", or install pngquant')

    if fig is None:
        from matplotlib import pyplot
        fig = pyplot.gcf()

    if not np.iterable(dpi):
        dpi = [dpi,]

    if isinstance(outfilebase, str):
        outfilebase = [outfilebase,]

    if len(outfilebase) != len(dpi):
        raise ValueError('differing number of outfile base and dpi')

    if altdirs is not None:
        if isinstance(altdirs, str):
            altdirs = [altdirs,]

        if len(altdirs) > 1 and len(altdirs) != len(dpi):
            raise ValueError('If more than a single altdir is given, there must'
                            ' be one for each dpi and outfilebase.')
        if len(altdirs) == 1 and len(dpi) > 1:
            altdirs *= len(dpi)

    kw.setdefault('facecolor', fig.get_facecolor())
    kw.setdefault('edgecolor', fig.get_edgecolor())

    outfiles = []
    for outf in outfilebase:
        if outf[-4:] != '.png':
            outf = outf + '.png'
        outfiles.append(outf)

    for d, outf in zip(dpi, outfiles):
        fig.savefig(outf, dpi=d, format='png', **kw)
        if quant:
            cmd = f'pngquant -f --ext .png --quality 70-95 --skip-if-larger {outf}'
            subprocess.run(cmd.split())
            _log.debug("ran '%s'", cmd)
        _log.debug("saved %s with dpi %d", outf, d)

    if altdirs is not None:
        for outf, altdir in zip(outfiles, altdirs):
            dest = os.path.join(altdir, os.path.basename(outf))
            shutil.copyfile(outf, dest)
            _log.debug("copied %s to %s", outf, dest)


def _png_thumbnail_PIL(figname, width=400, outdir=None):
    '''
    Make a thumbnail for an existing png file.
    This version based on PIL has poor quality and/or size properties, and
    will probably go away.
    '''
    from PIL import Image
    # this includes the path (drop the thumbnail in place)
    figbase, ext = os.path.splitext(figname)
    # (ext might be '')
    if ext and ext.lower() != '.png':
        raise ValueError('figname %s does not appear to be a png' % figname)
    figname = figbase + '.png'
    thumbnail=figbase+'T.png'
    # change output dir if requested
    if outdir is not None:
        thumbnail = os.path.join(outdir, os.path.basename(thumbnail))
    img = Image.open(figname)
    wpercent = (width / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((width, hsize), Image.LANCZOS)
    img.save(thumbnail)


def png_thumbnail(figname, width=400, outdir=None, tname='T'):
    '''
    Make a thumbnail for an existing png file.
    '''
    if _convert_cmd is None:
        raise RuntimeError('png_thumbnail requires Imagemagick')

    figname_orig = figname
    # this includes the path (drop the thumbnail in place)
    figbase, ext = os.path.splitext(figname)
    # (ext might be '')
    if ext and ext.lower() != '.png':
        raise ValueError('figname %s does not appear to be a png' % figname)
    figname = figbase + '.png'
    thumbnail=figbase+tname+'.png'
    # change output dir if requested
    if outdir is not None:
        thumbnail = os.path.join(outdir, os.path.basename(thumbnail))
    width=int(width)
    cmdlist = [_convert_cmd, figname, '-scale', f'{width}x', thumbnail]
    _log.debug(f"About to run subprocess with argument list {cmdlist}")
    p = subprocess.run(cmdlist, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        _log.warning(f"png_thumbnail failed for {figname_orig} with output {p.stdout}")
    else:
        _log.info(f"'{figname_orig}' -> thumbnail: '{thumbnail}'")


class DecimalDayFormatter(ticker.FuncFormatter):
    """
    Formatter for time in decimal days, using an strftime string.
    """
    def __init__(self, yearbase, fmt=None, dday=None):
        """
        Parameters
        ----------
        yearbase : int, 4-digit year
        fmt : None or str, optional
            strftime formatting string
        dday : None or str in ('top', 'bottom'), optional
            If None, the format will be a single line with date, time
            only; otherwise it will be two lines, with the decimal
            time above or below the date, time string.

        """
        epoch = datetime(yearbase, 1, 1)
        if dday is None:
            if fmt is None:
                fmt="%Y-%m-%d %H:%M"
            def func(x, pos=None):
                dt = epoch + timedelta(x)
                return dt.strftime(fmt)
        elif dday not in ('top', 'bottom'):
            raise ValueError("dday must be None, 'top', or 'bottom'")
        else:
            def func(x, pos=None):
                _fmt = fmt
                dt = epoch + timedelta(x)
                ddaystr = str(x)
                if _fmt is None:
                    if float(ddaystr) == int(x):
                        _fmt = "%m-%d"
                    else:
                        _fmt = "%H:%M"
                dtstr = dt.strftime(_fmt)
                lines = [ddaystr, dtstr]
                if dday == 'bottom':
                    lines = reversed(lines)
                return '\n'.join(lines)

        ticker.FuncFormatter.__init__(self, func)

def utc_formatting(x, pos=None, yearbase=2010):
    """
    Return UTC date (month/day hours:minutes)

    args:
     - x: decimal day, float
    kwargs:
     - pos: position along X-axis, float
     - yearbase: date's yearbase, int

    return: str

    Notes: This is a duplicate of utc_formatting
           in pycurrents.adcpgui_qt.lib.miscellaneous
    """
    # Fix for Ticket 685
    date = datetime(yearbase, 1, 1) + timedelta(x)
    return date.strftime('%m/%d %H:%M')


def add_UTCtimes(oldax, yearbase, offset=30, utc_fontsize=10,
                 xtext_rotation=20, alignment = 'left',
                 position='top', alternate_text='UTC dates (MM/DD hh:mm)'):
    """
    Add parallel X-axis with UTC dates (MM/DD hh:mm)

    args:
     - oldax: matplolib axis
     - yearbase: date's year base, int
    kwargs:
     - offset: offset from original axis, int
     - utc_fontsize: font size, int
     - xtext_rotation: ticks' rotation, deg., int
     - alignment: ticks' alignment, 'left' or 'right'
     - position: ticks' position, 'top' or 'bottom'
     - alternate_text: parallel axis' label, str
    """
    # Define parallel X-axis
    newax = oldax.twiny()
    newax.xaxis.set_ticks_position(position)
    newax.xaxis.set_label_position(position)
    newax.spines[position].set_position(('outward', offset))
    # Set x axis range
    newax.set_xlim(oldax.get_xlim())
    newax.set_xlabel(alternate_text)
    # Define tick formatter & locator
    newax.xaxis.set_major_locator(
            ticker.MaxNLocator(nbins=7, prune='both'))
    utc_formatter = ticker.FuncFormatter(
            lambda x, pos: utc_formatting(x, pos, yearbase))
    newax.xaxis.set_major_formatter(utc_formatter)
    # Format tick labels
    if position == 'bottom':
        xtext_rotation *= -1.0
    for label in newax.get_xticklabels():
        label.set_fontsize(utc_fontsize)
        label.set_ha(alignment)
        label.set_rotation(xtext_rotation)


def spinmap(cmap, spinfrac=0.0):
    '''
    spin colormap by this fraction (foward = positive, backward = negative)
    does not alter the original colormap
    cmap must be a LinearSegmentedColormap instance; so it will work with jet,
    but not with viridis, for example.
    '''
    shift = int(spinfrac * cmap.N)
    if shift == 0:
        return cmap

    cmap._init()
    cdict = cmap._segmentdata
    newcmap = mpl.colors.LinearSegmentedColormap('spun'+ cmap.name,
                                                    cdict, cmap.N)
    newcmap._init()
    newcmap._lut[:cmap.N] = np.roll(cmap._lut[:cmap.N], shift, axis=0)

    return newcmap

# As of 2023-05-07 we don't appear to be using any of the options other than
# 'name' in get_extcmap.  Therefore I suggest simplifying by removing the
# spinmap function (above) and all of the unused options in get_extcmap.
def get_extcmap(name=None, r=None, g=None, b=None, lut=256, banded=0,
                spinfrac = 0):
    '''
    return cmap instance using one of 2 schemes:
    (1) kwarg 'name'
        either built-in name (from mpl), eg 'jet'
        or one of the names below:
             'gautoedit',  'pg3080', 'g3080'    # variations on 'jet'
             'topo',                            # tan-blue
             'buoy',                            # garish stripes
             'rb_vel', 'blue_white_red', 'blue_red_vel'    # red - blue
             'ob_vel',                          # orange - blue
             'white_black_white',
             'seasons', 'season1', 'season2', 'season3', 'season4' # cyclic
             'blue_red_cyclic'
    (2) specify r,g,b (lists of integers? arrays?


    '''
    if name is not None and name not in ['gautoedit', 'buoy',
                                         'topo', 'topo_brown',
                                         'topo_pink', 'topo_steel_blue',
                                         'pg3080', 'g3080',
                                         'rb_vel',  'ob_vel',
                                         'white_black_white',
                                         'blue_white_red', 'blue_red_vel',
                                         'blue_red_cyclic',
                    'seasons', 'season1', 'season2', 'season3', 'season4']:

        return  spinmap(_get_cmap(name, lut), spinfrac)

    if name == 'blue_red_vel':
        cdict = {'red':  ((0.0, 0.0, 0.0),
                           (0.25,0.0, 0.0),
                           (0.5, 0.8, 1.0),
                           (0.75,1.0, 1.0),
                           (1.0, 0.4, 1.0)),

                 'green': ((0.0, 0.0, 0.0),
                           (0.25,0.0, 0.0),
                           (0.5, 0.9, 0.9),
                           (0.75,0.0, 0.0),
                           (1.0, 0.0, 0.0)),

                 'blue':  ((0.0, 0.0, 0.4),
                           (0.25,1.0, 1.0),
                           (0.5, 1.0, 0.8),
                           (0.75,0.0, 0.0),
                           (1.0, 0.0, 0.0))
                }
        cmap = mpl.colors.LinearSegmentedColormap(name, cdict, lut)

        return spinmap(cmap, spinfrac)

    if name == "blue_red_cyclic":
        t = np.linspace(0, 2*np.pi, num=64, endpoint=False) - np.pi/2
        r = 0.5 * (1 + np.sin(t))
        g = np.zeros_like(t)
        b = 0.5 * (1 + np.cos(t))
        rgb = np.vstack((r, g, b)).T
        cmap = mpl.colors.LinearSegmentedColormap.from_list(name, rgb, lut)
        return spinmap(cmap, spinfrac)

    if name == 'seasons':

        winter = _get_cmap("Blues")._segmentdata
        spring = _get_cmap("Purples")._segmentdata
        summer = _get_cmap("Greens")._segmentdata
        fall   = _get_cmap("Oranges")._segmentdata

        reds = np.concatenate(
            (spring['red'], summer['red'], fall['red'], winter['red']),
            axis=0)

        blues = np.concatenate(
            (spring['blue'], summer['blue'], fall['blue'],winter['blue']),
            axis=0)

        greens = np.concatenate(
            (spring['green'],summer['green'],fall['green'], winter['green']),
            axis=0)

        numpts = len(greens[:,0])
        x0 = np.arange(numpts)/(numpts-1.0)

        reds[:,0] = x0
        greens[:,0] = x0
        blues[:,0] = x0


        cdict = {
            'red'  :  reds,
            'green':  greens,
            'blue' :  blues
            }

        cmap = mpl.colors.LinearSegmentedColormap(name, cdict, lut)
        return spinmap(cmap, spinfrac)

    if name == 'season2':
        ws = _get_cmap("Purples")._segmentdata
        sf = _get_cmap("Oranges")._segmentdata

        reds = np.concatenate(
            (ws['red'], sf['red']),
            axis=0)

        blues = np.concatenate(
            (ws['blue'], sf['blue']),
            axis=0)

        greens = np.concatenate(
           (ws['green'],  sf['green']),
            axis=0)


        numpts = len(greens[:,0])
        x0 = np.arange(numpts)/(numpts-1.0)

        reds[:,0] = x0
        greens[:,0] = x0
        blues[:,0] = x0

        cdict = {
            'red'  :  reds,
            'green':  greens,
            'blue' :  blues
            }

        cmap = mpl.colors.LinearSegmentedColormap(name, cdict, lut)
        return spinmap(cmap, spinfrac)

    if r is None:

        if name == 'gautoedit':
            r = np.array([   0,   0,   0, 128, 255, 255, 255, 160], float)
            g = np.array([   0, 128, 255, 255, 255, 255, 128,   0], float)
            b = np.array([ 160, 255, 255, 255, 128,   0,   0,   0], float)

        elif name == 'topo': # original, inspired by Kathy D.
            r = np.array([    50, 111, 205, 251, 223, 178], float)
            g = np.array([   163, 215, 242, 235, 191, 132], float)
            b = np.array([   219, 255, 255, 231, 147,  55], float)

        elif name == 'topo_brown': # lighter
            r = np.array([    50, 111, 205, 251, 219, 204], float)
            g = np.array([   163, 215, 242, 235, 199, 166], float)
            b = np.array([   219, 255, 255, 231, 170, 107], float)

        elif name == 'topo_steel_blue': # blue version 1
            r = np.array([    28,  71, 102, 148, 202], float)
            g = np.array([   138, 181, 207, 226, 241], float)
            b = np.array([   189, 231, 250, 255, 255], float)

        elif name == 'topo_pink': # pink version
            r = np.array([    28,  71, 102, 148, 184, 251, 225], float)
            g = np.array([   138, 181, 207, 226, 228, 235, 208], float)
            b = np.array([   189, 231, 250, 255, 248, 231, 204], float)

        elif name == 'buoy':
            r = np.array([   122, 112, 245, 133, 102, 235,
                          143,  41,   8,   0,  38, 204,
                          163,  46,  13,   0,   0,   0, 0,   0], float)
            g = np.array([   122, 112, 245, 133,  38,   5,
                          0,  51, 217, 153,  43,  10,
                          0,  25, 191, 173,  48,  15,  0,   0], float)
            b = np.array([   122,  36,   3,   0,  64, 229,
                          143,  92, 224, 153,  43,  10,
                          0,   0,   0,   0,  13, 178, 184,  51], float)
        elif name == 'pg3080':
            r = np.array([  0,     0,   102,   230,   153], float)
            g = np.array([  0,   128,   255,   255,     0], float)
            b = np.array([153,   255,   153,    25,     0], float)
        elif name == 'g3080':
            r = np.array([ 0,    99,   145,   152,   255], float)
            g = np.array([ 0,    99,   145,   152,   255], float)
            b = np.array([ 0,    99,   145,   152,   255], float)
        elif name == 'blue_white_red':
            r = np.array([      0,   177,  255,  255,   255], float)
            g = np.array([      0,   177,  255,  177,     0], float)
            b = np.array([    255,   255,  255,  177,     0], float)
        elif name == 'white_black_white':
            r = np.array([    255,   100,    0,  100,   255], float)
            g = np.array([    255,   100,    0,  100,   255], float)
            b = np.array([    255,   100,    0,  100,   255], float)
        elif name == 'rb_vel':
            r = np.array([     0,     0,     0,   255,   255,   153], float)
            g = np.array([     0,    39,   193,   193,    39,     0], float)
            b = np.array([   153,   255,   255,     0,     0,     0], float)
        elif name == 'ob_vel':

            hues = np.array([270,250,230,220,210,205,200, 55, 50, 40, 30, 20, 10,340],float)
            sats = np.array([100,100, 80, 70, 40, 30, 10, 10, 50, 70, 80, 90,100,100],float)
            vals = np.array([ 50,100,100,100,100,100,100,100,100,100,100,100,100, 50], float)
            hsv = np.zeros([len(hues),1,3])
            hsv[:,0,0]=hues/360.
            hsv[:,0,1]=sats/100.
            hsv[:,0,2]=vals/100.
            rgb = 255*hsv_to_rgb(hsv)
            r = np.ones(sats.shape)
            r[:] = rgb[:,0,0]
            g = np.ones(sats.shape)
            g[:] = rgb[:,0,1]
            b = np.ones(sats.shape)
            b[:] = rgb[:,0,2]

        elif name == 'season1':
            r = np.array([217,  66,   5,  66, 217, 255, 255, 255, 255, 255],
                         float)
            g = np.array([242, 130,  55, 130, 242, 253, 140,  88, 140, 253],
                         float)
            b = np.array([255, 225, 129, 225, 255, 217,   0,   0,   0, 217],
                         float)

        elif name == 'season3':
            r = np.array([81, 149, 228, 243, 250, 225, 250, 243,
                            228, 149,  81], float)
            g = np.array([107, 163, 222, 222, 189,  55, 189, 222,
                            222, 163, 107], float)
            b = np.array([251, 242, 243, 243, 228,  84, 228, 243,
                            243, 242, 251], float)

        elif name == 'season4':
            r = np.array([149,  81, 148,  16, 250, 225, 201, 123, 123, 149],
                         float)
            g = np.array([163, 107, 237, 141, 189, 55, 106,  49,  49, 163],
                         float)
            b = np.array([242, 251, 137,   6, 228, 84,  45,   8,   8, 242],
                         float)

        r /= 255.0
        g /= 255.0
        b /= 255.0

       # name was specified, but failed

   #r,g,b came from arguments

    nverts = len(r)
    ra = np.zeros((nverts,3), float)
    ra[:,0] = np.linspace(0.0, 1.0, nverts)
    ga = ra.copy()
    ba = ra.copy()
    ra[:,1] = r

    ra[:,2] = r
    ga[:,1] = g
    ga[:,2] = g
    ba[:,1] = b
    ba[:,2] = b

    cdict =  {'red': ra, 'green': ga, 'blue': ba}
    cmap = mpl.colors.LinearSegmentedColormap('new_cmap',cdict,lut)


    if name is not None and name.startswith('topo'):
        land = dict(topo='#7A5229',
                    topo_brown='#9a7b59',
                    topo_steel_blue= '#B6AF9D', topo_pink = '#A1A1A1')
        # darker brown  '#7A5229'
        # gray          '#A1A1A1'
        # light brown   '#B6AF9D'
        # darker green  '#246B47'

        cmap.set_over(land[name])

    return spinmap(cmap, spinfrac)
#    return cmap

def axes_inches(fig, rect, **kw):
    """
    Wrapper for Figure.add_axes in which *rect* is given in inches.
    The translation to normalized coordinates is done immediately
    based on the present figsize.

    *rect* is left, bottom, width, height in inches
    *kw* are passed to Figure.add_axes

    """

    fw = fig.get_figwidth()
    fh = fig.get_figheight()
    l, b, w, h = rect
    relrect = [l / fw, b / fh, w / fw, h / fh]
    ax = fig.add_axes(relrect, **kw)
    return ax

def _boundaries(x):
    xb = np.empty((len(x) + 1,), dtype=float)
    xb[1:-1] = 0.5 * (x[1:] + x[:-1])
    xb[0] = xb[1] + (x[0] - x[1])
    xb[-1] = xb[-2] + (x[-1] - x[-2])
    return xb

def boundaries(x, y=None):
    """
    Given 1-D cell center coordinate arrays x and (optionally) y,
    return the corresponding cell boundary coordinate array(s).
    This is primarily for use in pcolorfast.  It might be expanded
    later to handle 2-D coordinate arrays.
    """
    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError("x must be 1-D, but ndim is %s" % x.ndim)
    if x.size < 2:
        raise ValueError("x needs at least 2 values, but size is %s" % x.size)
    if y is None:
        return _boundaries(x)

    y = np.asarray(y)
    if y.ndim != 1:
        raise ValueError("y must be 1-D, but ndim is %s" % y.ndim)
    if y.size < 2:
        raise ValueError("y needs at least 2 values, but size is %s" % y.size)
    return _boundaries(x), _boundaries(y)


def regrid_for_pcolor(x, c, dx_max=None, axis=1):
    """
    Calculate edge coordinates for use in the pcolor family.

    Parameters
    ----------
    x : 1-D array-like
        Center positions along an axis of 'c'.
    c : 2-D array-like
        Values to be color-mapped and plotted via pcolormesh or pcolorfast.
    dx_max : scalar or None
        Maximum width of a quadrilateral in the `x` direction.
    axis : integer
        Axis of `c` corresponding to center positions in `x`.

    Returns
    -------
    xb : 1-D ndarray
        Quadrilateral edge positions. Length is larger than `x` by at least 1.
    cb : 2-D ndarray
        Possibly modified counterpart to `c`, with any masked elements replaced
        by NaN, and with columns (if `axis` is 1) or rows (if `axis` is 0)
        inserted as needed to match the `dx_max` constraint.

    Examples
    --------
    ::

        x, y = np.arange(10), np.arange(3, 7)
        X, Y = np.meshgrid(x, y)
        Z = X * Y
        xgap = np.sqrt(x) * 5
        fig, ax = plt.subplots()
        xb, c = regrid_for_pcolor(xgap, Z, dx_max=1)
        yb, c = regrid_for_pcolor(y, c, axis=0)
        # Or use "yb = boundaries(y)" since no dx_max is needed.
        ax.pcolormesh(xb, yb, c)

    """
    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError(f'Input array "x" must be 2-D; found x.ndim = {x.ndim}.')
    if c.ndim != 2:
        raise ValueError(f'Input array "c" must be 2-D; found c.ndim = {c.ndim}.')
    if axis not in (0, 1, -1):
        raise ValueError(f'axis must be in (0, 1, -1); found {axis}')
    if axis == -1:
        axis = 1
    c = np.ma.filled(c, np.nan)
    if len(x) == c.shape[axis]:
        bounds = boundaries(x)
        centers = x
    else:
        raise ValueError("len(x) must equal c.shape[axis],"
                         f" but len(x) is {len(x)} and c.shape is {c.shape}.")
    if axis == 0:
        c = c.T

    edges = np.column_stack((bounds[:-1], bounds[1:]))
    widths = np.diff(edges, axis=1)
    if dx_max is None or (widths <= dx_max).all():
        if axis == 0:
            c = c.T
        return bounds, c

    # Insert a NaN column between each existing column.
    edges_const_width = np.column_stack(
        (centers - dx_max/2, centers + dx_max/2))
    edges_limited = np.column_stack(
        (np.maximum(edges_const_width[:, 0], edges[:, 0]),
        np.minimum(edges_const_width[:, 1], edges[:, 1])))

    c1 = np.empty((c.shape[0], c.shape[1] * 2 - 1), dtype=float)
    c1[:, 1::2] = np.nan
    c1[:, ::2] = c

    # Strip out the NaN columns we don't actually need.
    limited_bounds = edges_limited.ravel()
    keep = np.hstack((np.diff(limited_bounds) > 0, [True]))
    x2 = limited_bounds[keep]
    c2 = c1[:, keep[:-1]]
    if axis == 0:
        c2 = c2.T
    return x2, c2

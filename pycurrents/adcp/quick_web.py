"""
core of quick_web.py
"""

import sys
import os
import string

import matplotlib as mpl
import numpy as np
import numpy.ma as ma

import pycurrents.adcp.panelplotter as pplotter

from pycurrents.adcp import dataplotter
from pycurrents.adcp.quick_codas import binmaxdepth
from pycurrents.adcp.qplot import textfig
from pycurrents.adcp.reader import regrid_zonly

from pycurrents.plot.mpltools import savepngs
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.plot.maptools import mapper
from pycurrents.system.misc import safe_makedirs

from pycurrents.codas import get_profiles, get_txy

from pycurrents.num.grid import interp1

if "--interactive" in sys.argv:
    interactive = True
else:
    interactive = False
    mpl.use("Agg")


np.seterr(all="ignore")

# pyplot will choose a backend so this needs to come after the above mpl.use
import matplotlib.pyplot as plt # noqa: E402



sectinfofile = "sectinfo.txt"
sectnamefile = "sectnames.txt"
cruisename = "ADCP"
# cruiseid = cruisename  # not used?


def get_names(n, webdir, sectnamefile):
    """
    Return two lists of names for *n* sections.
    The first is always a 3-digit sequence number.
    The second is identical to the first unless a sectnamefile is
    found, in which case that supplies the list of names.

    """
    numnames = [f"{sec:03d}" for sec in range(n)]
    namefile = os.path.join(webdir, sectnamefile)
    try:
        with open(namefile) as newreadf:
            lines = newreadf.readlines()
        names = [line.strip() for line in lines]
        names = [line for line in names if line]  # remove blanks
        if len(names) == n:
            return (numnames, names)
        else:
            wstr = f"Found {len(names)} names; looked for {n}"
            wstr += "Use '--redo' but do not use '--auto'\n"
            raise IOError(wstr)

    except IOError:
        pass  # no file found
    return (numnames, numnames)


def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def make_simple_web(webdir, basename, cruisename, redo=False):
    html_figfile_template = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head>
        <title>${cruisename} ${basename}</title></head>

        <body>
        <img src="./${basename}.png">
        <br>
        <br>
        <br>
        </body></html>
        """
    dest = os.path.join(webdir, "index.html")
    if os.path.exists(dest) and redo is False:
        print("not overwriting {dest}")
        sys.exit()

    s = string.Template(html_figfile_template)
    h = s.substitute(basename=basename, cruisename=cruisename)
    if os.path.exists(dest):
        os.remove(dest)
    with open(dest, "w") as file:
        file.write(h)


# ----------------
class html_table:
    def __init__(
        self,
        rows,
        columns,
        txy_dict=None,
        sonar=None,
        webdir="./",
        dpi=80,
        cruisename="ADCP",
        otherfigs=None,
        redo=False,
    ):
        self.rows = rows
        self.columns = columns
        self.txy_dict = txy_dict
        self.sonar = sonar
        self.webdir = webdir
        self.otherfigs = otherfigs
        self.redo = redo
        self.dpi = dpi
        self.outfile = "index.html"
        self.cruisename = cruisename

        self.titledict = {
            "vect": "longitude + latitude",
            #'ddaycont' : 'decimal day',
            "ddaycont": "days ",
            "loncont": "longitude",
            "latcont": "latitude",
        }

        self.txy_columns = {"ddaycont": [0, 1], "loncont": [2, 3], "latcont": [4, 5]}

        print("otherfigs is", otherfigs)

        # ---------  index.html templates ------------------
        self.doc_head = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html>
        <head>
           <title>{0} thumbnails</title>
        </head>
        <body>
        <br>
        <div style="text-align: center;"><big><span style="font-weight:
        bold;"> {1} Thumbnails</span>
        </big></div>
        """

        self.ttable_head = """
        <table
          style="width: 100%%; text-align: center;  vertical-align: middle;
        background-color: {};"
          border="3" cellpadding="2" cellspacing="2">
           <tbody>
        """

        self.ttable_col_title = """
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(204, 204, 204);">
        <span style="font-weight: bold;">${titlename}</span><br>
        </td>
        """

        self.ttable_col_vect = """
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(204, 204, 204);">

             <a target="txy" href="./${txyname}.html" name="">
                   <img alt="${txyname}"
                   src="./thumbnails/${txyname}_thumb.png"
                   style="border: 0px solid ;" align="middle"> </a> <br>

             <a target="vector" href="./${vectname}.html" name="${name}">
                  <img alt="${vectname}"
                   src="./thumbnails/${vectname}_thumb.png"
                   style="border: 0px solid ;" align="middle"> </a> <br>
                  <span style="font-weight: bold;">${sec_string}</span><br>
                  <a href="#overview">(back to top)</a><br>


             </td>
        """
        self.ttable_col = """
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(204, 204, 204);">
                    <a target="${figtype}" href="./${basename}.html" name="${name}">
             <img alt="${basename}"
                   src="./thumbnails/${basename}_thumb.png"
                   style="border: 0px solid ;" align="middle"> </a> <br>
             <br> ${titlename}
             </td>
        """

        self.backtotop = """
                    <a href="#overview">(back to top)</a><br>
        """

        self.ttable_note = """
        <p> Navigation: <br>
        <ul>
        <li> Colored sections match colored section names
                     and link to rows on this page </li>
        <li> Each thumbnail in the main table is a link to a larger figure. </li>
        <li> Figures of like kind (txy, vector, contour) share one new
                       display each</li>
        </ul>
        """

        self.ttable_tail = """

           </tbody>
        </table>
        </body>
        </html>
        """

        # -------------------

        ## for fig.html

        self.html_linked_figfile_template = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head>
        <title>${basename}</title></head>

        <a href="index.html">Back to sections</a>, or <a href="../index.html"> back to cruises</a>
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <a href="sec_list.html">Table of details of all sections</a><br>
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <a href=".html"> View vector plot </a> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;

        <body>
        <img src="./${basename}.png">
        <br>
        <br>
        <br>
        </body></html>
        """

        self.html_figfile_template = """
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head>
        <title>${cruisename} ${basename}</title></head>

        <body>
        <img src="./${basename}.png">
        <br>
        <br>
        <br>
        </body></html>
        """

        # -------------------------------------------------------

    def make_html_figshell(self, basename):
        fname = f"{basename}.html"
        dest = os.path.join(self.webdir, fname)

        if os.path.exists(dest) and self.redo is False:
            print("not overwriting {dest}")
            sys.exit()

        s = string.Template(self.html_figfile_template)
        h = s.substitute(basename=basename, cruisename=cruisename)
        if os.path.exists(dest):
            os.remove(dest)
        with open(dest, "w") as file:
            file.write(h)

    def make_ttable(self):
        fname = os.path.join(self.webdir, self.outfile)

        print("generating {fname}")
        sv = string.Template(self.ttable_col_vect)
        # st = string.Template(self.ttable_col_title)

        tlist = [self.doc_head.format(self.cruisename, self.cruisename)]
        tlist.append(self.ttable_head.format("rgb(204, 204, 204)"))
        tlist.append("  <!-- overview --> ")
        tlist.append("  <td> <br><br>")

        secnums = self.rows
        xlist = [0.1] * len(secnums)
        ylist = np.arange(len(secnums), 0, -1, dtype=float) / (len(secnums) + 1)
        numlist, textlist = get_names(len(secnums), self.webdir, sectinfofile)

        tlist.append(
            html_clicktext(
                textlist,
                xlist,
                ylist,
                dest_dir=self.webdir,
                dpi=self.dpi,
                basename="secnames",
            )
        )

        tlist.append("  <td> ")
        s = string.Template(self.ttable_col)
        basename = self.sonar + "_overview"
        tlist.append(
            s.substitute(
                figtype="overview", titlename="", basename=basename, name="overview"
            )
        )
        tlist.append(
            s.substitute(
                figtype="overview",
                titlename="",
                basename="ADCP_vectoverview",
                name="vect_overview",
            )
        )
        tlist.append(self.ttable_note)
        tlist.append(self.ttable_tail)

        # make the table with sections
        tlist.append(self.ttable_head.format("rgb(51, 102, 255)"))
        tlist.append("  <!-- FIGURES--> ")

        # fill the rows
        for i, row in enumerate(self.rows):  # row is in '000', '001',...
            ## row should be the same as numlist[i]
            tlist.append("<tr>")
            for column in self.columns:
                # add label
                # assemble parts
                basename = self.sonar + "_" + column + row
                pngfile = "{basename}.png"
                try:
                    if column == "vect":
                        txyname = self.sonar + "_txy" + row
                        sec_string = "section " + textlist[i]
                        tlist.append(
                            sv.substitute(
                                vectname=basename,
                                txyname=txyname,
                                sec_string=sec_string,
                                name="section_" + row,
                            )
                        )
                    else:
                        titlename = f"{self.titledict[column]}"
                        if self.txy_dict is not None:
                            # add a year to ddaycount
                            if column == "ddaycont":
                                titlename += f"({self.txy_dict[row][6]})"
                            i1 = self.txy_columns[column][0]
                            i2 = self.txy_columns[column][1]
                            titlename += f" <br> ( {self.txy_dict[row][i1]} to {self.txy_dict[row][i2]} )"
                        tlist.append(
                            s.substitute(
                                figtype="contour",
                                titlename=titlename,
                                basename=basename,
                                name="",
                            )
                        )

                        # make html file for png
                    self.make_html_figshell(basename)
                except:
                    print("Error with ", pngfile)
                    raise
            tlist.append("</tr>")
        tlist.append(self.ttable_tail)
        if os.path.exists(fname):
            os.remove(fname)
        with open(fname, "w") as file:
            file.write("\n".join(tlist))

        if self.otherfigs is not None:
            if isinstance(self.otherfigs, str):
                self.otherfigs = [
                    self.otherfigs,
                ]
            for ff in self.otherfigs:
                self.make_html_figshell(ff)


# ---------------------


def html_clicktext(
    textlist,
    xlist,
    ylist,
    basename="secnames",
    dest_dir="./",
    savefile=False,
    units="normalized",
    rgb=None,
    dpi=80,
    fontsize=14,
    fontweight="bold",
):
    """
    html_clicktext(*args, **kwargs)

    annotates axes (if specified) or figure subplot(111) with
    text as specified; returns the html  "map" for clicking.

    Assumes sections are sequentially numbered 0,1,2,3


    args:
        textlist   : list of strings
        xlist      : list of x coordinates for text
        ylist      : list of y coordinates for text

    kwargs:
        fontsize   :  14
        fontweight : 'bold'
        basename   : 'secnames'

        dest_dir   : directory to write into (default is ./)
        savefile   : default = False:  the html paragraph with the links goes to stdout
                   : if True, include head and tail to make a standalone html file
    """

    click_html_head = """
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
    <html  lang="en">
    <BODY>
    """

    click_html_body0 = """<P>Select section by clicking on section name</P>
                          <P><MAP NAME="{}">"""

    # [left-top-x, left-top-y, right-bottom-x, right-bottom-y]
    click_html_links = """<AREA SHAPE="rect" HREF="${linkname}" COORDS=" ${ltx}, ${lty}, ${rbx}, ${rby}"> """

    click_html_body1 = """</MAP>
    <IMG USEMAP="#{0}" SRC="{1}.png"
    ALT= "clickable colored list of section names"></P>
    """

    click_html_tail = """
    </BODY>
    </HTML>
    """

    secnums = list(range(len(textlist)))

    # should allow for colors to be constant
    if not rgb:
        rgb = get_extcmap(name="buoy")(
            np.arange(len(textlist), dtype=float) / len(textlist)
        )

    fig = plt.figure(dpi=dpi, figsize=(2, 0.5 * len(textlist)))
    ax0 = fig.add_axes([0, 0, 1, 1])
    # must do this
    fig.savefig(os.path.join(dest_dir, basename + ".png"), dpi=dpi)
    # xx0 and yy0 should be 0
    xx0, yy0, xx1, yy1 = ax0.get_window_extent().bounds
    ax0.xaxis.set_ticklabels([])
    ax0.yaxis.set_ticklabels([])
    ax0.yaxis.set_ticks([])
    ax0.xaxis.set_ticks([])
    ax0.set_frame_on(False)
    ax0.set_xlim(xx0, xx1)
    ax0.set_ylim(yy0, yy1)

    # scale xlist and ylist
    sxlist = []
    sylist = []
    if units == "normalized":
        for sec in secnums:
            sxlist.append(xx0 + xlist[sec] * (xx1 - xx0))
            sylist.append(yy0 + ylist[sec] * (yy1 - yy0))
    elif units == "pixels":
        sxlist = xlist
        sylist = ylist
    else:
        print(f"cannot deal with units = {units}")
        raise ValueError

    thandles = {}

    for sec, secname in enumerate(textlist):
        tt = plt.text(
            sxlist[sec], sylist[sec], secname[:8], va="top"
        )  # string with dday range
        thandles[sec] = tt
        tt.set_size(18)
        tt.set_weight("bold")
        tt.set_color(rgb[sec, :3])

    plt.draw()
    dest = os.path.join(dest_dir, basename + ".png")
    if os.path.exists(dest):
        os.remove(dest)
    fig.savefig(dest, dpi=dpi)

    ## now make the html

    #### Note: the use of labeled regions in an image is
    #### unnecessarily complicated, and only here by historical accident.
    #### (Maybe OK--color coding is facilitated by this.)

    hlist = []

    if savefile:
        hlist.append(click_html_head)

    hlist.append(click_html_body0.format(basename))

    s = string.Template(click_html_links)
    for sec in secnums:
        anchorname = f"index.html#section_{sec:03d}"  # link to anchor
        x0, y0, x1, y1 = thandles[sec].get_window_extent().extents
        # html needs
        # left-top-x, left-top-y, right-bottom-x, right-bottom-y]
        hlist.append(
            s.substitute(
                linkname=anchorname,
                ltx=str(x0),
                lty=str(yy1 - y1),
                rbx=str(x1),
                rby=str(yy1 - y0),
            )
        )
    hlist.append("\n")
    hlist.append(click_html_body1.format(basename, basename))

    if savefile:
        hlist.append(click_html_tail)

    if savefile:
        if dest_dir is None:
            dest = basename + ".html"
            if os.path.exists(dest):
                os.remove(dest)
            with open(dest, "w") as file:
                file.write("\n".join(hlist))
        else:
            dest = os.path.join(dest_dir, basename + ".html")
            if os.path.exists(dest):
                os.remove(dest)
            with open(dest, "w") as file:
                file.write("\n".join(hlist))
    else:
        return "\n".join(hlist)


# ---------------------------------


def mk_webdirs(webdir):
    if not os.path.exists(webdir):
        print("")
        print(f"destination web directory {webdir} does not exist.  ")
        print(f"making directory  {webdir}")
        safe_makedirs(webdir)
        safe_makedirs(os.path.join(webdir, "thumbnails"))
    else:
        print("")
        print(f"web directory {webdir} exists.")
        print("use '--redo' to remake plots")
        sys.exit()


# --------------------------------


def get_vectlist(prefix, suffix, dest_dir):
    fn = "".join([prefix, "_vect", suffix, ".png"])
    destfile = os.path.join(dest_dir, fn)
    fn = "".join([prefix, "_vect", suffix, "_thumb.png"])
    thumb_destfile = os.path.join(dest_dir, "thumbnails", fn)
    return [destfile, thumb_destfile]


# ---------------------------------

zsteps = {
    "bb600": 2,
    "bb300": 5,
    "wh600": 2,
    "wh1200": 2,
    "wh300": 5,
    "wh150": 10,
    "nb300": 10,
    "bb75": 10,
    "bb150": 10,
    "nb150": 10,
    "os150bb": 10,
    "os150nb": 10,
    "ec150fm": 10,
    "ec150cw": 10,
    "os75": 10,
    "os75bb": 10,
    "os75nb": 20,
    "os38bb": 20,
    "os38nb": 30,
    "pn45bb": 20,
    "pn45nb": 30,
}


def get_dbinfo(
    sonar=None,
    dbname=None,
    ndays=None,
    startdd=None,
    enddd=None,
    vec_deltat=None,
    yearbase=None,
    webdir=None,
    fullsectinfofile=None,
    newfile=False,
    step=None,
):
    """
    get_dbinfo(freq = freq, dbname = dbname)

    returns dictionary with
        - deltaz and zstart (based on frequency)
        - yearbase
        - startdd, enddd  (for the whole database)
        - ddranges (startdd = dd0, enddd = dd1) of segments

    """

    dinfo = {}
    dinfo["dbname"] = dbname
    ranges = []
    dinfo["sonar"] = sonar

    # ddrange
    # vertical grid size for contouring
    dinfo["deltaz"] = zsteps[sonar]
    # start z

    # get startdd, endd for whole database
    if yearbase is not None:
        dinfo["yearbase"] = int(yearbase)
        all_txy = get_txy(dbname, yearbase=dinfo["yearbase"])
    else:
        all_txy = get_txy(dbname)
        dd = get_profiles(dbname, ddrange=0.1)
        dinfo["yearbase"] = dd.yearbase

    print(f"using {dinfo['yearbase']} as yearbase")

    if startdd:
        dinfo["startdd"] = float(startdd)
    else:
        dinfo["startdd"] = all_txy.dday[0]

    if step >= 1:
        dinfo["startdd"] = np.floor(dinfo["startdd"])
        print("startdd is ", dinfo["startdd"])

    if enddd:
        dinfo["enddd"] = float(enddd)
    else:
        dinfo["enddd"] = all_txy.dday[-1]
        print("enddd is ", dinfo["enddd"])

    # get the section [startdd,endd] if they exist; else create it
    if os.path.exists(fullsectinfofile):
        if os.path.getsize(fullsectinfofile) == 0:
            print(f"section file  {fullsectinfofile} is empty")
            print("starting over")
            os.remove(fullsectinfofile)

    if os.path.exists(fullsectinfofile):
        print(f"---> reading section times from {fullsectinfofile}")
        X = np.atleast_2d(np.loadtxt(fullsectinfofile))
        dinfo["dd0"] = X[:, 0]
        dinfo["dd1"] = X[:, 1]
        ranges = [tuple(a) for a in X]
    elif newfile:
        print(f"---> creating sections with step = {step} days")
        dinfo["dd0"] = np.arange(dinfo["startdd"], dinfo["enddd"], step)
        dinfo["dd1"] = dinfo["dd0"] + ndays
        print(dinfo)
        ranges = [tuple(a) for a in zip(dinfo["dd0"], dinfo["dd1"])]
        print("ranges", ranges)

        print("writing sectinfo with automatically-generated sections")
        sfid = open(fullsectinfofile, "w")
        for r in sorted(ranges):
            print(r[0], r[-1])
            sfid.write(f"{r[0]:10.7f}   {r[-1]:10.7f}\n")
        sfid.close()

    dinfo["zstart"] = binmaxdepth(dbname, 0)

    if vec_deltat:
        dinfo["vec_deltat"] = vec_deltat
    else:
        dinfo["vec_deltat"] = ndays / 72.0

    return dinfo, ranges


# -----------------


def txyplot(
    txydata, index=None, txysub=None, axfig=None, suptitle=None, all_labels_visible=True
):
    """
    handles = txyplot(txydata, index=None, txysub=None,
                axfig = 'newfig', all_labels_visible=True)

    plots a figure with 2x2 grid of subplots, as

                lon(time)     lat(lon)
                subset        subset

                lon(lat)       time(lon)
                all, subset    subset
                highlighted


    full dataset is txydata: np.array([dday,lon,lat])
    subset (if present) can be
        index (into txydata)
        txysub (independent data. 3xNprofs)

    axfig can be
    -  None (default; plots in a new figure)
    -  an axes object, in which case the subplots are inside the axes
    -  a figure, in which case the subplots are inside the figure


    The container (figure or axes) instance is returned as 'axfig' in
    the dictionary that is returned.

    returns dictionary of axfig and 4 axes
    """

    if isinstance(axfig, plt.Axes):
        # get the axes set up
        axbb = axfig.get_position()
        axfig.xaxis.set_visible(False)
        axfig.yaxis.set_visible(False)
        left = axbb.xmin
        bottom = axbb.ymin
        width = axbb.ymax - axbb.ymin
        height = axbb.xmax - axbb.xmin
    elif isinstance(axfig, plt.Figure):
        left = 0.125
        bottom = 0.125
        width = 0.8
        height = 0.8
    else:
        axfig = plt.figure()
        left = 0.125
        bottom = 0.125
        width = 0.8
        height = 0.8

    plt.figure(axfig.number)

    # fractions
    xfrac = 0.4  # xy_all is in bottom left; uses .4 of x direction
    yfrac = 0.4  # xy_all is in bottom left; uses .4 of y direction
    # values
    xspace = 0.02 * width  # x space between axes
    yspace = 0.02 * height  # y space between axes
    xstart = 0.1 * width  # gap in left
    ystart = 0.1 * width  # gap in bottom
    # build axes ll, lr, ul, ur
    # graphics area
    gwidth = 0.8 * width
    gheight = 0.8 * height
    # lower left = xy_all
    llwidth = xfrac * gwidth
    llheight = yfrac * gheight
    # lower right = xt
    lrwidth = (1 - xfrac) * gwidth
    lrheight = llheight
    # upper left = ty
    ulwidth = llwidth
    ulheight = (1 - yfrac) * gheight
    # upper right = xy (subset)
    urwidth = lrwidth
    urheight = ulheight

    # bounds:        left, bottom, width, height
    llbounds = [left + xstart, bottom + ystart, llwidth, llheight]
    lrbounds = [llbounds[0] + llwidth + xspace, llbounds[1], lrwidth, lrheight]
    ulbounds = [llbounds[0], llbounds[1] + llheight + yspace, ulwidth, ulheight]
    urbounds = [lrbounds[0], ulbounds[1], urwidth, urheight]

    try:
        xy_all_ax = plt.axes(llbounds, facecolor="y")
    except AttributeError:  # old mpl
        xy_all_ax = plt.axes(llbounds, axisbg="y")

    xt_ax = plt.axes(lrbounds)
    ty_ax = plt.axes(ulbounds)
    xy_ax = plt.axes(urbounds, sharex=xt_ax, sharey=ty_ax)

    xy_all_ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    xy_all_ax.yaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    xy_ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    xy_ax.yaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    xt_ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    xt_ax.yaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    ty_ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))
    ty_ax.yaxis.set_major_formatter(mpl.ticker.ScalarFormatter(useOffset=False))

    # move ticks and labels
    xt_ax.yaxis.tick_right()
    ty_ax.xaxis.tick_top()
    xy_ax.xaxis.tick_top()
    xy_ax.yaxis.tick_right()

    xt_ax.yaxis.set_label_position("right")
    ty_ax.xaxis.set_label_position("top")
    xy_ax.xaxis.set_label_position("top")
    xy_ax.yaxis.set_label_position("right")

    if all_labels_visible:
        ty_ax.xaxis.set_visible(all_labels_visible)
        xt_ax.yaxis.set_visible(all_labels_visible)
        xy_ax.xaxis.set_visible(all_labels_visible)
        xy_ax.yaxis.set_visible(all_labels_visible)

    ty_ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=3))
    ty_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4))
    xy_ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=3))
    xy_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4))
    xt_ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=3))
    xt_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4))
    xy_all_ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=3))
    xy_all_ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4))

    if gwidth < 0.3 or gheight < 0.3:
        plt.setp(ty_ax.get_yticklabels(), fontsize=6)
        plt.setp(xt_ax.get_xticklabels(), fontsize=6)
        plt.setp(xy_all_ax.get_xticklabels(), fontsize=6)
        plt.setp(xy_all_ax.get_yticklabels(), fontsize=6)

    xy_all_ax.plot(txydata[1, :], txydata[2, :], "k.-")

    if index is not None:
        xy_all_ax.plot(txydata[1, index], txydata[2, index], "r.-")
        xy_ax.plot(txydata[1, index], txydata[2, index], "r.-")
        ty_ax.plot(txydata[0, index], txydata[2, index], "r.-")
        xt_ax.plot(txydata[1, index], txydata[0, index], "r.-")

    if txysub is not None:
        xy_all_ax.plot(txysub[1, :], txysub[2, :], "r.-")
        xy_ax.plot(txysub[1, :], txysub[2, :], "r.-")
        ty_ax.plot(txysub[0, :], txysub[2, :], "r.-")
        xt_ax.plot(txysub[1, :], txysub[0, :], "r.-")

    xy_all_ax.set_xlabel("longitude")
    xy_all_ax.set_ylabel("latitude")

    xy_ax.set_xlabel("longitude")
    xy_ax.set_ylabel("latitude")

    ty_ax.set_xlabel("time")
    ty_ax.set_ylabel("latitude")

    xt_ax.set_ylabel("time")
    xt_ax.set_xlabel("longitude")

    ss_handles = {}
    ss_handles["axfig"] = axfig
    ss_handles["xy"] = xy_ax
    ss_handles["ty"] = ty_ax
    ss_handles["xt"] = xt_ax
    ss_handles["xy_all"] = xy_all_ax

    if suptitle:
        axfig.text(0.5, 0.95, suptitle, fontsize=14, weight="bold", ha="center")

    return ss_handles


# ---------------


def mk_overview(
    londat,
    latdat,
    prefix,
    dest_dir,
    dpi=[90, 40],
    bmap_kw=None,
    grid_kw=None,
    topo_kw=None,
    zoffset=0,
    suptitle=None,
    pad=1,
    figsize=(6, 4.5),
    resolution=None,
    aspect=0.8,
):
    if bmap_kw is None:
        bmap_kw = {}
    if grid_kw is None:
        grid_kw = {}
    if topo_kw is None:
        topo_kw = {}

    fn = "".join([prefix, "_overview", ".png"])
    destfile = os.path.join(dest_dir, fn)

    fn = "".join([prefix, "_overview", "_thumb.png"])
    thumb_destfile = os.path.join(dest_dir, "thumbnails", fn)

    destlist = [destfile, thumb_destfile]

    topofig = plt.figure(figsize=figsize, layout="constrained")
    ax = topofig.add_subplot(111)

    print("mk_overview with prefix=", prefix, "zoffset=", zoffset)
    bmap = mapper(londat, latdat, zoffset=zoffset, ax=ax, **bmap_kw)

    bmap.grid(**grid_kw)
    # We are ignoring topoticks for now. Also subsample.
    bmap.topo(**topo_kw)  # nsub=subsample
    bmap.mplot(londat, latdat, "k.")

    if suptitle is not None:
        ax.set_title(suptitle, fontsize=14, fontweight="bold")

    if dpi is not None:
        for dest in destlist:
            if os.path.exists(dest):
                os.remove(dest)
        savepngs(destlist, dpi=dpi, fig=topofig)
        for fname in destlist:
            os.chmod(fname, 0o664)

    return destlist, bmap, topofig


# ---------------


def dday_fill_gaps(dday):
    """
    Make a dday grid that coincides with the input dday,
    but that fills in the gaps, so that when zgrid is used,
    long gaps will be left blank.
    """
    ddaydiff = np.diff(dday)
    dt = np.median(ddaydiff)
    gapstartmask = ddaydiff > 3 * dt
    if not gapstartmask.any():
        return dday

    igaps = np.nonzero(gapstartmask)[0]
    chunks = []
    i0 = 0
    for ii in igaps:
        chunks.append(dday[i0 : ii + 1])
        i0 = ii + 1
        filler = np.arange(dt, ddaydiff[ii] - dt / 2, dt)
        chunks.append(dday[ii] + filler)
    chunks.append(dday[i0:])
    return np.concatenate(chunks)


# ---------------


def conplots(
    data,
    prefix,
    suffix,
    dest_dir,
    dbinfo=None,  # or maybe just pass in deltaz
    cmapname="ob_vel",
    dpi=[90, 40],
    maxvel=None,
    suptitle=None,
    fill_color=None,
    redo=False,
    native=False,
    ddrange=None,  # need both for native
    add_amp=False,
):
    print("dest_dir is", dest_dir)
    dlist = []

    dday = data["dday"]
    lat = data["lat"]
    lon = data["lon"]

    ng = min(100, len(lat))
    xgrids = {}
    if not native:
        xgrids["dday"] = dday_fill_gaps(dday)

    xgrids["lat"] = np.linspace(lat.min(), lat.max(), ng)
    xgrids["lon"] = np.linspace(lon.min(), lon.max(), ng)

    zz = np.arange(
        np.min(data["depth"].compressed()),
        np.max(data["depth"].compressed()) + dbinfo["deltaz"],
        dbinfo["deltaz"],
    )

    dgrids = dict(dday=zz, lat=zz, lon=zz)

    for xvar, xgrid in xgrids.items():
        fn = "".join([prefix, f"_{xvar}cont", suffix, ".png"])
        destfile = os.path.join(dest_dir, fn)
        fn = "".join([prefix, f"_{xvar}cont", suffix, "_thumb.png"])
        thumb_destfile = os.path.join(dest_dir, "thumbnails", fn)
        destlist = [destfile, thumb_destfile]

        gdata = {}
        gdata["dday"] = data.dday
        gdata["lon"] = data.lon
        gdata["lat"] = data.lat
        gdata["u"] = regrid_zonly(data.dday, data.u, data.depth, zz)
        gdata["v"] = regrid_zonly(data.dday, data.v, data.depth, zz)

        ## NOT masked, and it will be used by pcolorfast in adp.cuvplot...
        temp_a = np.ma.zeros((len(data.lon), len(zz)), float)
        for iprof in range(len(data.lon)):
            temp_a[iprof, :] = interp1(
                data["depth"][iprof, :], data["amp"][iprof, :], zz
            )

        gdata["amp"] = temp_a
        gdata["dep"] = zz
        gdata["yearbase"] = data.yearbase

        ###

        adp = dataplotter.ADataPlotter(
            gdata,
            zname="uv",
            x=xvar,
            y="dep",
            ylim=[np.max(zz), 0],
            xlim=[np.min(xgrid), np.max(xgrid)],
            cmapname=cmapname,
        )
        adp.cuvplot(
            title_base=prefix,
            nxticks=5,
            suptitle=suptitle,
            fill_color=fill_color,
            xout=xgrid,
            yout=dgrids[xvar],
            add_amp=add_amp,
        )
        fig = adp.cuv_fig

        for dest in destlist:
            if os.path.exists(dest):
                os.remove(dest)
        adp.save(destlist, dpi=dpi, fig=fig)
        dlist.extend(destlist)
        for fname in destlist:
            os.chmod(fname, 0o664)
        plt.close(fig)

    if native:
        sonar = dbinfo["sonar"]
        fn = f"{sonar}_ddaycont{suffix}.png"
        destfile = os.path.join(dest_dir, fn)
        fn = f"{sonar}_ddaycont{suffix}_thumb.png"
        thumb_destfile = os.path.join(dest_dir, "thumbnails", fn)
        destlist = [destfile, thumb_destfile]
        dlist = make_panelplot(
            dbinfo["dbname"],
            destlist,
            maxvel=maxvel,
            ddrange=ddrange,
            sonar=sonar,
            suptitle=suptitle,
        )
        print(f"making panel plots for {dlist[0]}")


# ---------------
### need to add year, "add_utcdates", cruisename


def make_panelplot(
    dbname, destlist, ddrange=None, sonar=None, suptitle="ADCP DATA", maxvel=None
):
    data = get_profiles(dbname, ddrange=ddrange, diagnostics=True)
    NCD = pplotter.NCData(data)
    NCD.set_grid()
    fig = pplotter.plot_data(
        NCD,
        speed=True,
        sonar=sonar,
        figsize=(9, 10),  ## width is 9
        maxvel=maxvel,
        axlist=["u", "v", "amp", "pg", "heading"],
        add_utc=True,
        add_suntimes=True,
    )
    ## add cruise title to top left
    fig.text(0.05, 0.98, suptitle, fontsize=14, fontweight="bold", ha="left")

    for dest in destlist:
        if os.path.exists(dest):
            os.remove(dest)

    savepngs(destlist, dpi=[90, 40], fig=fig)
    plt.close(fig)
    for d in destlist:
        os.chmod(d, 0o644)
    return destlist


# ---------------


def call_txyplot(
    alldata, data, prefix, suffix, dest_dir, suptitle=None, dpi=[90, 40], redo=False
):
    fn = "".join([prefix, "_txy", suffix, ".png"])
    destfile = os.path.join(dest_dir, fn)

    fn = "".join([prefix, "_txy", suffix, "_thumb.png"])
    thumb_destfile = os.path.join(dest_dir, "thumbnails", fn)

    destlist = [destfile, thumb_destfile]

    try:
        cond = ma.getmaskarray(alldata["lon"])
        dday = ma.masked_where(cond, alldata["dday"]).compressed()
        lon = alldata["lon"].compressed()
        lat = alldata["lat"].compressed()
        txydata = np.array([dday, lon, lat])

        cond = ma.getmaskarray(data["lon"])
        dday = ma.masked_where(cond, data["dday"]).compressed()
        lon = data["lon"].compressed()
        lat = data["lat"].compressed()
        txysub = np.array([dday, lon, lat])

        hdict = txyplot(txydata, txysub=txysub, suptitle=suptitle)
        fig = hdict["axfig"]
    except:  # noqa: E722 at the moment it's impossible to tell what depends on this
        fig = textfig("no data", title=suptitle)

    for dest in destlist:
        if os.path.exists(dest):
            os.remove(dest)
    savepngs(destlist, dpi, fig=fig)

    for fname in destlist:
        os.chmod(fname, 0o664)

    plt.close(fig)
    return destlist

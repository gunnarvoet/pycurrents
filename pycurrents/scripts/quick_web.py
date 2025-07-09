#!/usr/bin/env python
''' set up a directory for making a UHADCP adcp web page

     - go to processing directory (in which adcpdb is located)


    (1) "interactive": (select sections from scratch)

          quick_web.py --interactive --sonar SONAR --cruisename TITLE


    (2) "auto" -- use time gridding to automatically determine sections

        quick_web.py --auto --sonar SONAR --cruisename TITLE [options]


    (3) "redo" -- redo with sectinfo that already exists

        quick_web.py --redo --sonar SONAR --cruisename TITLE



       other variables      | vertical     | time gridding
                            |     grid     |
       ---------------      | -------------| --------------
                            |  specify     |  specify as
      dbname: path to codas |   sonar:     |  'interactive'
                database    |              |  or using
      cruisename:  title    |   wh300      |
     =======================|   wh600      |  ddrange : number of days
     remaking or finer      |   wh1200     |          :    per plot
        control of behavior |   nb150      |  step    : step size between
      --------------------  |   nb300      |          :    plot starts
      setup: make web page  |   os150bb    |  startdd : start at this dday
             and overview,  |   os150nb    |  enddd   : show no data past
             then stop      |   os75bb     |          :    this day
      html_only:            |   os75nb     |  yearbase: specify if not
              do not redo   |   wh75       |          :      same as database
              figures,      |   wh300      |
              only redo     |   pn45       |
                index.html  |   os38bb     |
       redo:   redo html    |   os38nb     |
                 and all    |              |
                 figures    |              |


   NOTE: will use "dbinfo.txt" (if that file exists) to find
   values for "sonar" and "cruisename".  Otherwise, must specify

'''

import sys
import os
import glob
from optparse import OptionParser

import matplotlib

if '--interactive' in sys.argv:
    interactive = True
else:
    interactive = False
    matplotlib.use('Agg')

import numpy as np
np.seterr(all='ignore')

import numpy.ma as ma
import matplotlib.pyplot as plt

from pycurrents.adcp import dataplotter
from pycurrents.adcp.uhdasfile import guess_dbname

from pycurrents.plot.txyselect import RangeSet, TMapSelector
from pycurrents.plot.mpltools import savepngs
from pycurrents.plot.mpltools import get_extcmap
from pycurrents.plot.maptools import LonFormatter, LatFormatter

from pycurrents.codas import get_profiles

import  pycurrents.adcp.quick_web as qweb


## for debugging
#from IPython.Shell import IPShellEmbed
#ipshell = IPShellEmbed()

##-------------------------------------

step = 3         # step each figure forward by 3 days
ddrange = 4      # plot 4 days of data

dbname = None
#webdir = 'webpy' (default is set in options handling in main())
sonar = None


#------------------------------

def main():

    smalldpi=  [90,30]
    bigdpi= [120,70]

    parser = OptionParser(__doc__)
    parser.add_option("--yearbase", dest="yearbase",
                          help='\n'.join(["for decimal day ",
                                         "(defaults to 1st year of data)"]))
    parser.add_option("--ddrange" , dest="ndays",
                          help='\n'.join(["number of days duration per plot",
                                          "(default = 4)"]))
    parser.add_option("--startdd", dest="startdd",
                          help="dday to start if not at the beginning")
    parser.add_option("--enddd", dest="enddd",
                          help="dday to stop if before the end")
    parser.add_option("--step", dest="step",
                          help='\n'.join([" days to advance between plots",
                                          "(default = 3)"]))
    parser.add_option("--vecscale", dest="vecscale",
                          help='\n'.join(["velocity scale for vector plots:",
                                          "(mps/inch) default=1.0",
                                          "(try smaller for big vectors)"]))

    parser.add_option("--add_amp", action="store_true", dest="add_amp",
                          help="add amplitude (signal return) to contour plots -- only impacts older contour plots, not 'native'",
                          default=False)
    parser.add_option("--vec_deltat", dest="vec_deltat",
                   help='\n'.join(["averaging time for vector section plots:\n",
                             "specify in minutes.  default is 1 hour (60min)"]))
    parser.add_option("--bmap_pad", dest="bmap_pad",
                          help='\n'.join(["map fractional margin:",
                                          "default=1.0",
                                          "(try 0.5 to reduce extra map area)"]))
    parser.add_option("--bmap_aspect", dest="bmap_aspect",
                          help='\n'.join(["map aspect ratio:",
                                          "default=0.8",
                                          "(try 1.2 for a taller map)"]))
    parser.add_option("--grid_nx", dest="grid_nx",
                          help='\n'.join(["map max x grid intervals:",
                                          "default=5",
                                          "(try 4 to reduce label crowding)"]))
    parser.add_option("--grid_ny", dest="grid_ny",
                          help='\n'.join(["map max y grid intervals:",
                                          "default=5",
                                          "(try 4 to reduce label crowding)"]))
    parser.add_option("--refbins", dest="refbins",
                          help='\n'.join(["reference layer bins to plot",
                                          "(vector plots)",
                                          "colon-delimited inclusive range.",
                                          "default=1:3",
                                          "NOTE: not original data bins"]))
    parser.add_option("--bigfig", dest="bigfig", action="store_true", default=False,
                      help="make the initial figures larger (for big monitors)")

    parser.add_option("--topo_levels", dest="topo_levels",
                          help="default = 'auto' (per section), 'fixed' (whole cruise)")

    parser.add_option("--zoffset", dest="zoffset", default=0,
                          help='\nsubtract this\nfrom all topo')
    parser.add_option("--maxvel", dest="maxvel", default=None,
                          help='max velocity in colorbar (symmetric)')
    parser.add_option("--webdir", dest="webdir", default='webpy',
                          help="directory to put web page info (default = 'webpy'")
    parser.add_option("--reports", action="store_true", dest="reports",
                          help="default is False; if True, put 'webpy' into 'reports/webpy'",
                          default=False)
    parser.add_option("--dbname", dest="dbname",
                          help='\n'.join(["path to database, (up to but ",
                                          "not including 'dir.blk')"]))
    parser.add_option("--cruisename", dest="cruisename",
                          help="cruise ID or title for plots (or use 'cruiseid'")
    parser.add_option("--cruiseid", dest="cruiseid",
                          help="cruise ID or title for plots (overrides cruisename) ")
    parser.add_option("--sonar", dest="sonar",
                          help="instrument type + frequency.  see --help")
    parser.add_option("--simple_web", action="store_true", dest="simple_web",
                          help="set up web page, make overview plot; stop (else do whole web site)",
                          default=False)
    parser.add_option("--simple_timeplot", action="store_true", dest="simple_timeplot",
                          help="default is False, i.e. use native CODAS resolution and pcolor plots (if True, then regrid in time and only plot u and v (original behavior)",
                          default=False)
    parser.add_option("--interactive",action="store_true",dest="interactive",
         help="choose sections interactively; creates (or builds on) sectinfo.txt ",
                          default=False)
    parser.add_option("--redo", action="store_true", dest="redo",
         help="allow overwrite of html and png files using existing sections",
                          default=False)
    parser.add_option("--auto", action="store_true", dest="auto",
         help="from scratch, using options (eg. 'ddrange') to determine sections",
                          default=False)

    options, args = parser.parse_args()

    if len(sys.argv[1:]) == 0:
        print(__doc__)
        return

    # --native used to be the way to turn this on.
    # now we want CODAS native resolution to be the default, and only disable it if requested
    options.native = not(options.simple_timeplot)

    fill_color = [.85,.85,.85]  # could be pulled out as an option


    ## comment:
    #
    #  ddrange is the argument the user sees, but it refers to the number of days extracted
    #  ddrange should always be a tuple, with startdd,enddd (for consistency)

    ## set variables:
    if  options.ndays:
        ndays = float(options.ndays)
    else:
        ndays = 4

    if options.vecscale:
        vecscale=float(options.vecscale)
    else:
        vecscale=1.0

    if options.maxvel:
        maxvel = float(options.maxvel)
    else:
        maxvel = None

    if options.refbins:
        rr = options.refbins.split(':')
        if len(rr) == 1:
            refbins = [int(rr[0])]
        elif len(rr) == 2:
            refbins = np.arange(int(rr[0]),int(rr[1])+1)
        else:
            refbins = np.array(rr,int)
    else:
        refbins = [1,]

    webdir = os.path.realpath(options.webdir)
    if options.reports:
        dirparts = os.path.split(webdir)
        webdir = os.path.join(dirparts[0], 'reports', dirparts[1])

    # for mapper (via dataplotter.vecplot and qweb.mk_overview

    bmap_kw = dict(aspect=0.8, pad=1.0)
    if options.bmap_aspect:
        bmap_kw['aspect'] = float(options.bmap_aspect)
    if options.bmap_pad:
        bmap_kw['pad'] = float(options.bmap_pad)

    grid_kw = dict(nx=5, ny=5)
    if options.grid_nx:
        grid_kw['nx'] = int(options.grid_nx)
    if options.grid_ny:
        grid_kw['ny'] = int(options.grid_ny)

    if options.topo_levels in [None, 'auto']:
        topo_levels = 'auto'
    elif options.topo_levels == 'fixed':
        topo_levels = None
    else:
        print('--topo_levels can only be "fixed" (default) or "auto"')
        raise ValueError
    topo_kw = dict(levels=topo_levels)


    if  options.step:
        step = float(options.step)
    else:
        step = 3

    if options.bigfig:
        figsize=(14,8)
    else:
        figsize=(6,5)

    if options.dbname is None:
        print('guessing dbname')
        dbname = guess_dbname('./')
    else:
        dbname = options.dbname
    print('found dbname\n %s' % (dbname))

    dbpath = os.path.split(os.path.abspath(dbname))[0]
    basepath = os.path.split(dbpath)[0]
    dbinfopath = os.path.join(basepath, 'dbinfo.txt')

    sonar = None
    ## TODO This next block needs to add a path to dbinfo
    if options.sonar is not None:
        sonar = options.sonar
    else:
        if os.path.exists(dbinfopath):
            print('found dbinfo.txt')
            from pycurrents.system.misc import Cachefile
            dbcache = Cachefile('dbinfo.txt')
            dbcache.read()
            if 'cruisename' in list(dbcache.cachedict.keys()):
                cruisename = dbcache.cachedict['cruisename']
            if 'sonar' in  list(dbcache.cachedict.keys()):
                sonar = dbcache.cachedict['sonar']

    if sonar is None: #not found with dbinfo:
        print(__doc__)
        print('---> Error : must specify "sonar" (instrument+pingtype).')
        print('choose from the left column, below')

        print('\n      sonar    deltaz\n')
        for ipstr, dz in qweb.zsteps.items():
            print('%15s   %5d' % (ipstr, dz))
            sys.exit()


    # cruiseid overrides
    if options.cruisename is not None:
        cruisename = options.cruisename
    if options.cruiseid is not None:
        cruisename = options.cruiseid
    if cruisename is None:
        print(__doc__)
        print('---> Error : must specify "cruisename"\n')
        sys.exit()

    #--------------------------
    ''' make web dir, make overview plot, quit '''
    if os.path.exists(webdir):
        if not options.redo:
            print('directory exists.  use "redo" to re-use it')
            sys.exit()
    else:
        if not (options.auto or options.interactive):
            print('making a new directory for web plots')
            print('must choose --interactive or --auto')
            sys.exit()

    ## set up dir, go to dir
    if not os.path.exists(webdir):
        qweb.mk_webdirs(webdir)
    thumbdir = os.path.join(webdir, 'thumbnails')
    if not os.path.exists(thumbdir):
        os.mkdir(os.path.join(thumbdir))

    if options.auto:
        try:
            os.remove(os.path.join(webdir, 'sectinfo.txt'))
        except:
            pass
        options.redo = True


    ## set up for data, get metadata (ddrange, etc)
    ## this will read sectinfo.txt if it exists,
    ## otherwise will write it.

    if options.yearbase is None:
        try:
            alldata = get_profiles(dbname)
        except:
            msg= 'cannot find quoted dbname %s' % (dbname,)
            raise IOError(msg)
    else:
        try:
            alldata = get_profiles(dbname, yearbase=int(options.yearbase))
        except:
            msg= 'cannot find quoted dbname %s' % (dbname,)
            raise IOError(msg)


    print(alldata.yearbase)


    ## move this information earlier: we need dbinfo['deltaz']
    fullsectinfofile=os.path.join(webdir, qweb.sectinfofile)
    ## set up for data, get metadata (ddrange, etc)
    ## this will read sectinfo.txt if it exists, otherwise will write it.
    dbinfo, ranges =  qweb.get_dbinfo(sonar = sonar,
                        yearbase = options.yearbase,
                        startdd  = options.startdd,
                        enddd    = options.enddd,
                        webdir   = webdir,
                        fullsectinfofile = fullsectinfofile,
                        dbname   = dbname,
                        newfile  = options.auto,
                        ndays  = ndays,  #duration
                        step     = step)



    # make overview plot
    fig = plt.figure(layout="constrained")
    ax=fig.add_subplot(111)
    print("making overview with vecplot, grid_kw: ", grid_kw)
    dataplotter.vecplot(alldata,
                        vecscale=vecscale,
                        bmap_kw=bmap_kw.copy(), # copy to prevent side effects
                        grid_kw=grid_kw.copy(), # (maybe copy is not needed
                        topo_kw = {'levels':topo_levels,},
                        zoffset=float(options.zoffset),
                        refbins=refbins,        #  after change to vecplot)
                        deltaz=dbinfo['deltaz'],  # side effects
                        deltat = 1/24.,
                        ax=ax)

    suptitle = cruisename + ' ' + sonar
    ax.set_title(suptitle, fontsize=14)
    destlist = qweb.get_vectlist('ADCP', 'overview', webdir)

    for dest in destlist:
        if os.path.exists(dest):
            os.remove(dest)
    savepngs(destlist, dpi=bigdpi, fig=fig)
    for fname in destlist:
        os.chmod(fname, 0o664)

    #save small thumbnails png, with background color
    dest = qweb.get_vectlist('small', 'overview', webdir)[1]

    ax.set_title(cruisename, fontsize=15)

    if os.path.exists(dest):
        os.remove(dest)
    savepngs(dest, dpi = 50, fig=fig, facecolor='#E4DED3')

    plt.close(fig)


    print('Made overview plot for whole cruise: %s/ADCP_vectoverview.png' % (webdir,))

    #--------------------------
    if options.simple_web is False:
        ''' read data, get time ranges if requested, make plots'''

        # move this earlier:   dbinfo, ranges =  get_dbinfo(sonar...

        alldata = get_profiles(dbinfo['dbname'], yearbase=dbinfo['yearbase'])

        if interactive:
            ''' get time ranges '''
            print('''
                 Select or update sections in the 4-panel window.
                    Close window when finished, and
                      plot generation will commence''')

            cond = ma.getmaskarray(alldata['lon'])

            dday= ma.masked_where(cond, alldata['dday']).compressed()
            lon = alldata['lon'].compressed()
            lat = alldata['lat'].compressed()

            destlist, Map, fig = qweb.mk_overview(lon, lat,
                        sonar,
                        webdir,
                        dpi=None,
                        zoffset = float(options.zoffset),
                        bmap_kw=bmap_kw.copy(), # copy to prevent side effects
                        grid_kw=grid_kw.copy(), # (maybe copy is not needed
                        topo_kw=topo_kw.copy(), #
                        figsize=figsize        )



            rs = RangeSet(dday,  lon,  lat, ranges = ranges)
            fig = plt.figure(figsize=figsize)
            TMapSelector(fig, rs, minspan=600.0/86400)
            if not plt.isinteractive():
                plt.show()

            if ranges == rs.ranges:
                print(('\nNOTE: sectinfo.txt has not been changed.\n' +
                        'If you want to generate new plots with this sectinfo.txt,\n' +
                         'run qweb.py again with "--redo option".'))
                sys.exit()
            else:
                #ranges = rs.ranges
                print(rs.ranges)

            if os.path.exists(fullsectinfofile):
                os.remove(fullsectinfofile)
            sfid = open(fullsectinfofile,'w')
            for r in sorted(rs.ranges):
                print(r[0], r[-1])
                sfid.write('%10.7f   %10.7f\n' % (r[0], r[-1]))
            sfid.close()

        else:
            # write out

            cond = ma.getmaskarray(alldata['lon'])
            dday= ma.masked_where(cond, alldata['dday']).compressed()
            lon = alldata['lon'].compressed()
            lat = alldata['lat'].compressed()
            rs = RangeSet(dday,  lon,  lat, ranges = ranges)

            if os.path.exists(fullsectinfofile):
                os.remove(fullsectinfofile)
            sfid = open(fullsectinfofile,'w')
            for r in sorted(rs.ranges):
                print(r[0], r[-1])
                sfid.write('%10.7f   %10.7f\n' % (r[0], r[-1]))
            sfid.close()


        # load the times from this file, however it got there
        X = np.atleast_2d(np.loadtxt(fullsectinfofile))
        print('found sectinfo.txt with times')
        dbinfo['dd0'] = X[:,0]
        dbinfo['dd1'] = X[:,1]
        dbinfo['startdd'] = dbinfo['dd0'].min()
        dbinfo['enddd']   = dbinfo['dd1'].max()


        # now get colors and annotate topo fig
        numsecs = len(dbinfo['dd0'])
        rgb = get_extcmap(name='buoy')(np.arange(numsecs,
                                       dtype=float)/numsecs)

        ## make it again so we can annotate with colors
        print('making overview file')
        cond = ma.getmaskarray(alldata['lon'])
        dday= ma.masked_where(cond, alldata['dday']).compressed()
        lon = alldata['lon'].compressed()
        lat = alldata['lat'].compressed()
        if len(lat) == 0:
            print("FAIL: NO GOOD POSITIONS.")
            sys.exit()

        topo_destlist, colorMap, colorfig= qweb.mk_overview(lon, lat,
                       sonar, #prefix
                       webdir,#destdir
                       suptitle= suptitle,
                       dpi=None,
                       zoffset = float(options.zoffset),
                       bmap_kw=bmap_kw.copy(), # copy to prevent side effects
                       grid_kw=grid_kw.copy(), # (maybe copy is not needed
                       topo_kw=topo_kw.copy(), #
                       )


        if colorMap is None:
            print('cannot make topographic overview: figure exists')
            sys.exit()


        print(dbinfo['dd0'])
        print('database start,end is', (dbinfo['startdd'],dbinfo['enddd']))

        txy_dict = {}
        lonf = LonFormatter()
        latf = LatFormatter()

        numlist, textlist = qweb.get_names(numsecs, webdir, qweb.sectnamefile)

        for iday in  range(numsecs):
            print('\n--------- section %d ----------\n' % (iday,))
            ddrange = dbinfo['dd1'][iday] - dbinfo['dd0'][iday]  #duration
            print('about to extract %f days starting at %f' % (
                    ddrange, dbinfo['dd0'][iday]))

            print('dbname is', dbinfo['dbname'])

            try:
                data = get_profiles(dbinfo['dbname'],
                                    startdd= dbinfo['dd0'][iday],
                                    yearbase = dbinfo['yearbase'],
                                    ndays=ddrange)
                print('found %d ensembles' % (len(data.dday)))
            except:
                data=None

            if data is not None:
                cond = ma.getmaskarray(data['lon'])
                parts = (ma.masked_where(cond, data['dday']).compressed(),
                         data['lon'].compressed(),
                         data['lat'].compressed())
                for p in parts:
                    if len(p) <= 2:
                        data = None
                        print('===> skipping this section: no good positions<===')
                        break
            #
            suffix = numlist[iday]
            prefix = sonar
            ## add colors to the overview plot
            if data is not None:
                plt.sca(colorMap.ax)
                colorMap.mplot(data.lon, data.lat, marker='.',
                          mec=rgb[iday,:],
                          color=rgb[iday,:])
                ddrange = (dbinfo['dd0'][iday], dbinfo['dd1'][iday])
                ##------------ txy ------------
                qweb.call_txyplot(alldata, data, prefix,
                                  suffix, webdir,
                                  suptitle=suptitle,
                                  dpi = smalldpi,
                                  redo=options.redo)
                print('Made txy plots for %f to %f' % ddrange)

                ## ------------ contour plots ------------
                qweb.conplots(data, prefix, suffix, webdir,
                              dbinfo=dbinfo,
                              suptitle=suptitle,
                              dpi = smalldpi,
                              fill_color=fill_color,
                              maxvel=maxvel,
                              redo=options.redo,
                              native = options.native,
                              ddrange = ddrange,
                              add_amp=options.add_amp)
                print('Made contour plots for %f to %f' % ddrange)

                ## ------------ vector plots ------------
                fig = plt.figure(layout="constrained")
                ax=fig.add_subplot(111)
                if options.vec_deltat is None:
                    deltat = dbinfo['vec_deltat']
                else:
                    deltat = float(options.vec_deltat)/1440
                dataplotter.vecplot(data,
                                    vecscale=vecscale,
                                    refbins=refbins,
                                    deltaz=dbinfo['deltaz'],  # side effects
                                    deltat = deltat,
                                    zoffset = float(options.zoffset),
                                    topo_kw = {'levels':topo_levels,},
                                    ax=ax)
                ax.set_title(suptitle, fontsize=14)

                destlist = qweb.get_vectlist(prefix, suffix, webdir)
                for dest in destlist:
                    if os.path.exists(dest):
                        os.remove(dest)
                savepngs(destlist, dpi=smalldpi, fig=fig)
                plt.close(fig)

                for fname in destlist:
                    os.chmod(fname, 0o664)

                print('Made vector plot for %f to %f' % \
                    (dbinfo['dd0'][iday], dbinfo['dd1'][iday]))

                ## ------------ create txy_dict------------

                d_start = '%5.2f' %dbinfo['dd0'][iday]
                d_end = '%5.2f' %dbinfo['dd1'][iday]
                yearbase = data.yearbase

                lon = data['lon'].compressed()
                lat = data['lat'].compressed()

                lonmin = lonf(round(lon[0],2))
                lonmax = lonf(round(lon[-1],2))
                latmin = latf(round(lat[0],2))
                latmax = latf(round(lat[-1],2))

                lonmin = lonmin.encode('ascii', 'xmlcharrefreplace').decode('ascii')
                lonmax = lonmax.encode('ascii', 'xmlcharrefreplace').decode('ascii')
                latmin = latmin.encode('ascii', 'xmlcharrefreplace').decode('ascii')
                latmax = latmax.encode('ascii', 'xmlcharrefreplace').decode('ascii')

                txy_dict[suffix] = [d_start, d_end, lonmin, lonmax,
                                            latmin, latmax, yearbase]


        plt.sca(colorMap.ax)

        for dest in topo_destlist:
            if os.path.exists(dest):
                os.remove(dest)
        savepngs(topo_destlist, dpi=bigdpi, fig=colorfig)
        for fname in topo_destlist:
            os.chmod(fname, 0o664)

    #-----------
    if options.simple_web:
        qweb.make_simple_web(webdir, 'ADCP_vectoverview', cruisename,
                             redo=options.redo)
    else:

        # findout out how many rows:
        filelist = glob.glob(os.path.join(webdir, '*_ddaycont*.png'))
        if len(filelist) == 0:
            print('no ddaycont files found.  cannot make web page')
            sys.exit()

        filelist.sort()
        numstrings = [fn[-7:-4] for fn in filelist]  #eg os38nb_ddaycont002.png

        otherfigs = ['ADCP_vectoverview', sonar+'_overview',]
        filelist = glob.glob(os.path.join(webdir, '*_txy*.png'))
        filelist.sort()
        for fn in filelist:
            otherfigs.append(os.path.splitext(os.path.split(fn)[-1])[0])
        if len(otherfigs) == 0:
            otherfigs = None

        HTML = qweb.html_table(numstrings,
                          columns=['vect','ddaycont','loncont','latcont'],
                          txy_dict = txy_dict,
                          sonar = sonar,
                          cruisename = suptitle,
                          webdir = webdir,
                          otherfigs = otherfigs,
                          redo = options.redo)

        HTML.make_ttable()


if __name__=='__main__':
    main()

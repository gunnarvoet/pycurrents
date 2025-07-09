'''
Script and functions for making a reasonable template with
ADCP meta-data, using either a control file or arguments:

cruisename         cruise title or prefix for config/*.m files
sonar              [os75bb, os75nb, wh300, nb150,...]
datatype           [lta, enx, ens, uhdas, pingdata]


This is used by quick_adcp.py, but may be run as a script on
older directories.

'''

import sys
import os
import glob
import time
import string
from optparse import OptionParser
from pycurrents.system.misc import Cachefile
from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.uhdasfile import guess_dbname

#=======================================================

unk = 'unspecified'
npad = '\n                  '

instruction_str = '''

<...> Please consider submitting your final processed data to JASADCP
<...> (Joint Carchive for SHipblard ADCP) data so other people can benefit
<...> from all the work that went into this.  GoogleSearch for
<...> "JASADCP shipboard ADCP" in your browser.
<...>
<...> NOTE: Markup description:
<...> - Narration is preceeded by these characters:     <...>
<...> - Anything with those characters at the beginning of a line will be
<...>   stripped out by JASADCP before archiving.
<...>

==================================================
POST PROCESSING STEPS:
==================================================
<...> Post processing commands start in the ${sonar} directory.
<...> If the cruise dates are wrong in the header, adjust manually.
<...> The time range of processed data can be found in ${sonar}/adcpdb/${dbname}.tr

<...> This template covers most common situations when processing UHDAS data in CODAS.
<...> For more detail, the latest version of the CODAS manual can be found at:
<...> https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/index.html

--------------------------
### 1. Check visual oddities
--------------------------
<...> Perform a visual first pass of the data looking for the following problems:
<...>   (a) good heading correction for all of the ADCP data (any gaps?)
<...>   (b) sharp transitions in velocities
<...>       (i)   on station vs underway (transducer angle or scale factor)
<...>      (ii)   vertical stripes when transitioning between underway and
<...>             stopped (an offset between ADCP and GPS is not accounted for)
<...>      (iii) biases when underway with poor PG (will need to apply uvship)
<...>   (c) gaps due to "free inertial" flag in Seapath (heading exists,
<...>       but positions are missing, so no ship speed)
<...>   (d) false bottoms near steep topography: symptom strong scattering
<...>       layer is mis-identified as the bottom, resulting in shorter
<...>       profiles that stop at the scattering layer, but data on both
<...>       sides is much deeper
<...>
<...> When to post-process vs reprocess (eg. with adcp_database_maker.py)
<...> You should reprocess if
<...>   (a) heading correction: if there are gaps and there is another accurate
<...>       heading device, you could reprocess using that other device
<...>   (b) sharp transitions in velocities
<...>      (ii)  vertical stripes when transitioning between underway and stopped
<...>            (likely an offset between ADCP and GPS is not accounted for)
<...>      (iii) biases when underway with poor PG (will need to apply uvship)
<...>            If the offset is greater than 2m in x or y AND if there are periods
<...>            when the ship is underway in heavy weather, then you should reprocess
<...>            ensuring that you use the final xducer_dx and xducer_dy.  Then the
<...>            'uvship' algorithm can be attempted.  Otherwise do not use it
<...>   (c) there are gaps due to "free inertial" flag in Seapath.  In this case,
<...>       pick another position device, and make sure you get its xducer_dx and
<...>       xducer_dy correct.  You might have to process twice, once to estimate
<...>       the values, and a second time to use them.
<...>   (d) false bottoms near steep topography: If the Percent Good is BLUE below
<...>       the scattering layers, you can only get those parts back by reprocessing
<...>       and NEVER looking for the bottom.  Then you have to edit out the bottom
<...>       using the threshold tool for Bottom Selector.  If the PG is red or orange,
<...>       you can resurrect those profiles by using "reset editing".
<...>
<...> Otherwise you may postprocess the cruise.
<...>
<...> Heading correction:
<...> Check that we have a good heading correction for all of the ADCP data.
<...>
<...> There should be no holes in the heading correction graphs
<...> (cal/rotate/ens_hcorr*.png), where "valid corrections" are green
<...> circles and "bad corrections" are red crosses. Gaps in the plots where
<...> there are no symbols are okay, no data was collected there.
<...>
<...> If there are red crosses on the heading correction graphs
<...> (cal/rotate/ens_hcorr_*.png) then they need to be patched in the cal/rotate dir
<...> using patch_hcorr.py.
<...>
--------------------------

### Run this: (to look for gaps in the cruise track)
plot_nav.py nav/a*.gps

### Run this: (to look for gaps in the heading correction, examine the character of <...> the watertrack and bottom track calibration, etc
figview.py

### Run this: (looking for missing heading correction values or missing positions)
dataviewer.py

<...> NOTE: IF there are holes in the heading correction plots, you need to
<...> run "patch_hcorr.py" to interpolate across the gaps.  Do this BEFOE doing any
<...> further post-processing

### Run this: (to interpolate for missing heading correction fixes)
cd cal/rotate
patch_hcorr.py
cd ../..

### Run this: (to check watertrack calibration after patching hcorr)
catwt.py

### Run this: (to check watertrack calibration after patching hcorr)
catbt.py

### Run this: (to check dxdy statistics calibration after patching hcorr)
catxy.py

---------------------
### 2. ADCP calibration
---------------------
<...> Calibrate the dataset in sum by checking the calibration values
<...> and applying a fix to the necessary categories if necessary.
<...>
<...> When looking at a water track or bottom track calibration, we want to see
<...> statistics inside the following values:
<...>
<...>             median_tolerance
<...>
<...> - amplitude range   .997 to  1.003       # 0.3%
<...> - phase/angle range  -0.05 to  0.05      # 1/2 degree
<...> - offset (dx,dy)      rounded residual should be between -2 and 2 meters
<...>
<...> When looking at an xy calibration to adjust the relative location of the GPS
<...> to the sonar we try to get the dx and dy values close to zero, bearing
<...> in mind that this is a guess. The "signal" should be between 1000 and 5000.
<...> Less than 1000 means very little data, more than 5000 means too much change.
<...>
<...> If values are out of range we make a bulk correction to the entire dataset
<...> which should reduce the number of outliers to be edited out.
<...>
<...> If we make any changes to x or y they should be integers.
<...>
<...> The command to be run to edit the calibration is listed below, where *
<...> is replaced with desired values for the options to be changed and
<...> other options removed:
<...>
<...> quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_amplitude *.** --rotate_angle *.** --xducer_dx * --xducer_dy * --auto
---------------------

### Run this: (look at the watertrack calibration residuals remaining)
catwt.py

### Run this: (look at the bottom track calibration residuals remaining)
catbt.py

### Run this: (look at the remaining offsets required)
catxy.py

---
### If a large dxdy correction is needed (values greater than 5), do this first:

### Run this: (replace '*' with your values (round to nearest integer))
quick_adcp.py --steps2rerun rotate:apply_edit:navsteps:calib --xducer_dx * --xducer_dy * --auto

### Run this: (look at the watertrack calibration again)
catwt.py

### Run this: (look at the offset again)
catxy.py

### If a scale factor or phase need to be applied, do that now (replace '*' with your values)

### Run this:
quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_amplitude * --rotate_angle * --auto

### Run this: (look at the watertrack calibration again)
catwt.py

### Run this: (look at the offset again)
catxy.py

<...> How do the calibrations look?  See above for median tolerances and
<...> repeat steps if the calibrations are still out of median tolerances.

-------------------
### 3. Editing points
-------------------
<...> Edit out biased data or artifacts deeper than the range of the sonar
<...> in the dataset, or other problems. We are looking for 1 cm/s accuracy
<...> in ocean velocities, and any transitions larger than that could be suspect.
<...>
<...> Use `dataviewer.py -e` to look for problems with the data and
<...> flag the bad data as bad. After editing out data we rerun the
<...> calibration to see if the changed dataset statistics have
<...> changed enough that a new calibration is needed.
-------------------

### Run this: (to go through the dataset and edit out bad values)
dataviewer.py -e

### Run this: (to recompute the calibration residuals)
quick_adcp.py --steps2rerun navsteps:calib --auto

### Run this:
catwt.py

### Run this:
catxy.py

<...>  The calibrations should still be good after editing.

--------------------------------------------------
### 4. Re-check heading correction and other figures
--------------------------------------------------
<...> Check all figures from section 1 again to make sure that any problems
<...> were addressed and no new problems have appeared after making changes
<...> to the dataset.
--------------------------------------------------

### Run this: (Is there anything strange with any of the figures?)
figview.py

--------------------------------------------------------------
### 5. Check edited, calibrated dataset against original dataset
--------------------------------------------------------------
<...> Compare the edited, calibrated dataset against
<...> the original dataset to make sure all problems have been dealt
<...> with, and no new problems have appeared.There is likely to be strong
<...> colors in the difference plot if big changes were made.

<...> Compare sonars against the next nearest frequencies available
<...> (Ex. os150 with wh300 and os75, not wh1200 and os38).
<...> Compared datasets across different sonars should show a uniform
<...> bias, Ex. all faint red or blue, equivalent to roughly 1 cm/s.

<...> Look at the compared datasets on the default scale (0.8 days) and a
<...> medium term scale (2 to 3 days) to look for longer scale bias.

<...> When running dataviewer.py -c, put the finer resolution/smaller bin
<...> sized data first to show the diff at the finer resolution.
<...> NOTE that changes in bin size or number of bins will look like
<...> a major problem.  Just choose a different time range so the transition
<...> is not in view and it will look better.
--------------------------------------------------------------

### Run this: (Has this corrected the problems in the original?)
dataviewer.py -c . ../${sonar}.orig

### Run this to compare this sonar with another sonar (after both are finished)
dataviewer.py -c ../ANOTHER_SONAR  .

<...> Use the comparison to determine if anything else needs to be done.

-------------------------
### 6. Make plots and files
-------------------------
<...> Create the figures and data files needed to finish processing
<...> and make public/submit to a repository (JASADCP, if nowhere else).

<...> Make the plots needed for web viewing, matlab files (legacy),
<...> and netCDF files, then check that the netCDF files are readable.
<...> Plots should be in 3 to 5 day chunks for a cruise longer than one week,
<...> or divided by geographic features where it makes sense.
<...>
<...> If quick_web.py --interactive has been done for a different sonar, do:

<...> Run this: (edit for your particular case)

<...> mkdir webpy
<...> cp ../ANOTHER_SONAR
/webpy/sectinfo.txt webpy
<...> quick_web.py --redo
-------------------------

<...> If it's the first time:
### Run this:

quick_web.py --interactive

### Run this to extract matlab files
quick_adcp.py --steps2rerun matfiles --auto

### Run this to extract a netCDF file
adcp_nc.py adcpdb contour/${sonar}  CRUISENAME ${sonar} --ship_name SHIPNAME

### Run this to look at the headers
ncdump -h contour/${sonar}.nc


'''


def get_headstr(opts):
    ss='gyro?? (specify primary heading device here)'
    if opts['datatype'] == 'uhdas' and opts['cruisename']:
        if 'uhdas_config' in opts:
            ss = opts['uhdas_config'].gbin_params.hdg_inst
    return ss

def parse_cnh(cnhfile):
    '''
    parse adcpdb/dbname.cnh to get basic logging info such as
            bin, blank, averaging time, bottom track
    return list of lines to print
    '''
    if os.path.exists(cnhfile):
        with open(cnhfile) as newreadf:
            cnh_lines = newreadf.readlines()
    else:
        return 'no cnh file to read'

    # param_* are the whole list
    param_abbrev = []  # eg 'BT'
    param_descr= []    # eg. "bottom track"
    for line in cnh_lines:
        parts = line.split(' : ')
        if len(parts) == 2:
            param_abbrev.append(parts[0])
            param_descr.append(parts[1])
    param_ord = list(range(len(param_abbrev)))
    # initialize
    param_format = []
    for ii in range(len(param_ord)):
        param_format.append(0)

    # desired_* are the subset
    desired_fields = ['BT', 'SI', 'NB', 'BL', 'TD', 'BK', 'HO', 'HB', 'CRPH']
    desired_formats =      ['5',   '5', '4',  '4',   '4', '3',  '7',  '7',  '5']
    desired_ord = [] #  index into param_*
    for ff in desired_fields:
        pord = param_abbrev.index(ff)
        desired_ord.append(pord) #eg. [1, 2, 3, 4, 6, 7, 10, 11]
        param_format[pord] = desired_formats[desired_fields.index(ff)]

    # start building the list to print.  start with the desired_fields
    lines = []
    for pord in desired_ord:
        pabbrev = param_abbrev[pord]
        pdesc   = param_descr[pord].strip()
        lines.append('%s : %s' % (pabbrev, pdesc))
    for line in cnh_lines:
        # just get yy/mm/dd
        if line[0] == 'y':
            parts = line.split()
            str = '%s%s  %s' % (npad, parts[0], parts[1])   #yy/mm/dd hh:mm:ss
            for pord in desired_ord:
                str=str+'%*s' % (int(param_format[pord]), parts[pord+2])
            lines.append(str)
        elif line[0] in ['1','2']:
            parts = line.split()
            str = '%s %s' % (parts[0], parts[1])   #yy/mm/dd hh:mm:ss
            for pord in desired_ord:
                str = str + '%*s' % (int(param_format[pord]), parts[pord+2])
            lines.append(str)

    return npad.join(lines)

def calstr(opts):
    ''' return string for calibration note
    '''
    lines = []
    if 'datatype' in opts and opts['datatype'] is not None:
        if opts['datatype'].lower() == 'uhdas':
            try:
                h_align = opts['uhdas_config'].pingavg_params['head_align']
                tr_depth = opts['uhdas_config'].pingavg_params['tr_depth']
                velscale = opts['uhdas_config'].pingavg_params['velscale']
                lines.append('original transducer orientation: %3.2f' % (h_align))
                lines.append('transducer depth: %2.1f' % (tr_depth))
                lines.append('acquisition scale factor applied: %4.4f' % (velscale))
            except:
                lines.append('(check original processing parameters)')
        else:
            lines.append('check parameters for original heading alignment')
    if 'rotate_angle' not in opts:
        opts['rotate_angle'] = 'unknown'

    lines.append('(1) transducer alignment')
    lines.append('    original transducer alignment: ')
    lines.append('    additional rotation %s' % (opts['rotate_angle'],))
    lines.append('    final transducer angle is:')
    lines.append('         (original transducer angle) - (rotate_angle)')
    lines.append('')

    if 'rotate_amplitude' not in opts:
        opts['rotate_amplitude'] = 'unknown'
    lines.append('(2) scale factor')
    lines.append('    original scale factor %s' % (opts['rotate_amplitude'],))
    lines.append('    additional scale factor (none)')
    lines.append('')

    if 'xducer_dx' not in opts:
        opts['xducer_dx'] = 'unknown'
        opts['xducer_dy'] = 'unknown'
    lines.append('(3) ADCP (dx=starboard, dy=fwd) meters from GPS')
    lines.append('  original:        xducer_dx          xducer_dy')
    lines.append('  correction           %s                 %s' % (
                        opts['xducer_dx'],opts['xducer_dy']))
    lines.append('  final offset          ?                  ?')
    lines.append('       final = original +  corrections ')
    lines.append('')


    return npad.join(lines)

def get_metadata(opts):
    '''
    return two dictionaries with metadata info
    '''
    report_names = dict([
        (0 ,  ( 'changed'          ,       'LAST CHANGED   ')),
        (1 ,  ( 'cruisename'       ,       'CRUISE NAME(S) ')),
        (2 ,  ( 'cruise_dates'     ,       'CRUISE DATES   ')),
        (3 ,  ( 'shipname'         ,       'SHIP NAME      ')),
        (4 ,  ( 'ports'            ,       'PORTS          ')),
        (5 ,  ( 'chiefsci'         ,       'CHIEF SCIENTIST')),
        (6 ,  ( 'dbname'           ,       'DATABASE NAME  ')),
        (7 ,  ( 'data_files'       ,       'DATA FILES     ')),
        (8 ,  ( 'status'           ,       '\nSTATUS         ')),
        (9 ,  ( 'instname'         ,       '\nINSTRUMENT     ')),
        (10,  ( 'acquisition'      ,       '\nACQUISITION    ')),
        (11,  ( 'datatype'         ,       '     PROGRAM   ')),
        (12,  ( 'proc_engine'      ,       '     PROCESSING:   ')),
        (13,  ( 'pingtype'         ,       '     PING TYPE ')),
        (13,  ( 'logging'           ,      '\nLOGGING        ')),
        (14,  ( 'params'           ,       '\n     PARAMETERS')),
        (15,  ( 'heading'          ,       '\nHEADING        ')),
        (16,  ( 'heading_device'   ,       '     PRIMARY   ')),
        (17,  ( 'hcorr_inst'       ,       '     CORRECTION')),
        (18,  ( 'positions'        ,       '\nPOSITIONS      ')),
        (19,  ( 'calib'            ,       '\nCALIBRATION    ')),
        (20,  ( 'comments'         ,       '\nCOMMENTS       ')),
        (21,  ( 'processor'        ,       'PROCESSOR      '))])


    # this will hold the actual information
    infodict = {}
    infodict['changed'] = time.strftime("%Y/%m/%d %H:%M:%S")
    infodict['cruisename'] = opts['cruisename']
    try:
        infodict['dbname'] = opts['dbname']
    except:
        infodict['dbname'] = unk
    try:
        with open(os.path.join('adcpdb', opts['dbname']+'.tr')) as newreadf:
            lines = newreadf.readlines()
        infodict['cruise_dates'] = lines[0].rstrip()
    except:
        infodict['cruise_dates'] = unk
    try:
        infodict['shipname'] = opts['shipname']
    except:
        infodict['shipname'] = unk
    infodict['ports'] = unk
    infodict['chiefsci'] = unk
    if 'datadir' in opts:
        if 'datafile_glob' in opts:
            try:
                filelist = glob.glob(os.path.join(opts['datadir'],
                                                  opts['datafile_glob']))
                filelist.sort()
            except:
                filelist=[]
            if len(filelist) > 0:
                infodict['data_files'] = \
                         os.path.split(filelist[0])[-1] + ' to ' + \
                         os.path.split(filelist[-1])[-1]
            else:
                infodict['data_files'] = unk
        else:
            infodict['data_files'] = unk
    else:
        infodict['data_files'] = unk
    #status
    status1 = npad.join([' to do                           done',
                         '------                       -----------',
                         'averaged                       [     ]',
                         'loaded                         [     ]'])

    status3 = npad.join(['',
                         'check heading correction       [     ]',
                         'calibration                    [     ]',
                         'edited                         [     ]',
                         're-check heading correction    [     ]',
                         'check editing                  [     ]',
                         'figures                        [     ]'])


    if opts['datatype'] == 'uhdas':
        if not opts['hcorr_inst']:
            status2=npad.join(['',
                               'NOTE: No automated time-dependent',
                               '      heading correction exists'])
        else:
            status2=npad.join(['',
                               'NOTE: heading correction instrument exists'])

            if opts['ping_headcorr'] is None: #from __main__
                hcorr_comment = npad.join(['',
                               '      NOTE: time-dependent heading correction',
                               '      status must be determined'])
            elif opts['ping_headcorr']:
                hcorr_comment = npad.join(['',
                               '      NOTE: time-dependent heading corrections',
                               '      applied IN the ensembles',
                               '      (see   cal/rotate/ens_hcorr.ang)',
])
            else:
                hcorr_comment = npad.join(['',
                               '      NOTE: time-dependent heading corrections',
                                      'staged but NOT applied',
                               '      (see     cal/rotate/hcorr.ang)',
                               '      --> check if applied using "rotate"'])
            status2 += hcorr_comment



    elif opts['datatype'] in ['lta', 'sta']:
        status2=npad.join(['      NOTE: No automated time-dependent',
                           '      heading correction exists'])
    elif opts['datatype'] in ('pingdata'):
        status2=npad.join(['',
                           '      NOTE: time-dependent heading corrections',
                           '      status NOT KNOWN',
                           '      --check if applied using "rotate"'])
    else:
        status2 = ''

    infodict['status'] = '\n'.join([status1, status2, status3])

    # instrument
    if 'instname' in opts:
        infodict['instname'] = opts['instname']
    else:
        infodict['instname'] = \
                 'specify instrument: wh300, nb150, os150, os75, bb75, os38,...'
    # data acquisition
    infodict['acquisition']=''
    if 'datatype' in opts:
        infodict['datatype'] = opts['datatype']
    else:
        infodict['datatype'] = 'choose lta, enx, ens, uhdas, pingdata'

    infodict['proc_engine'] = opts['proc_engine']

    # ping type
    if 'pingtype' in opts:
        infodict['pingtype'] = opts['pingtype']
    else:
        infodict['pingtype'] = 'specify ping type: "bb" or "nb"\n' + \
                 'also (if ocean Surveyor) say whether pinging was interleaved'
    # logging parameters
    infodict['logging']=''
    cnhfile = os.path.join('adcpdb', '%s.cnh' % (opts['dbname'],))
    if os.path.exists(cnhfile):
        infodict['params'] = parse_cnh(cnhfile)
    else:
        infodict['params'] = \
                       'fill in bottom tracking, pin size, number of bins\n' + \
                       'look at %s' % (cnhfile,)
    infodict['heading'] = ''
    infodict['heading_device'] = 'heading from %s' % (get_headstr(opts))

    # heading correction
    infodict['hcorr_inst'] = 'specify heading correction device (if it exists)'
    if opts['datatype'] == 'pingdata':
        infodict['hcorr_inst'] = 'unknown'
    elif opts['datatype'] == 'uhdas':
        try:
            infodict['hcorr_inst'] = 'heading correction from %s' % (
                    opts['hcorr_inst'] + hcorr_comment)
        except:
            infodict['hcorr_inst'] = 'does not exist?'
    #gps
    if 'uhdas_config' in opts:
        infodict['positions'] = 'gps positions from %s' % (
                opts['uhdas_config'].gbin_params.pos_inst)
    else:
        infodict['positions'] = 'gps (specify more detail if available)'
    #calibration
    infodict['calib'] = calstr(opts)
    infodict['comments'] = npad.join(['gaps in heading correction?',
                                                  'scattering layers?',
                                                  'bubbles?',
                                                  'underway bias?',
                                                  ''])
    infodict['processor'] = 'I.M. Persistent'

    return report_names, infodict


def write_report(opts, fname = None, overwrite=False):
    '''
    'overwrite' will redo the file.  usually used for incremental only
    '''
    report_names, infodict = get_metadata(opts)

    if fname is None:
        fnameparts=[]
        if 'cruisename' in opts:
            fnameparts.append(opts['cruisename'])
        if 'instname' in opts:
            fnameparts.append(opts['instname'])
            if 'pingtype' in opts and opts['instname'][:2] == 'os':
                fnameparts[-1] = fnameparts[-1] + opts['pingtype']
        if len(fnameparts) == 0:
            fnameparts.append('cruise')
            fnameparts.append('info')
        fname = '_'.join(fnameparts)
        fname = fname + '.txt'


    mnums=list(report_names.keys())
    mnums.sort()

    if os.path.exists(fname) and overwrite is False:
        return 1, 'not overwriting meta-data file %s' % (fname,)


    F = open(fname,'w')
    for mnum in mnums:
        kk = report_names[mnum][0]
        name = report_names[mnum][1]
        desc = infodict[kk]
        try:
            F.write( name + ' : ' + desc + '\n')
        except:
            print('skipping:', name, desc, '... continuing')
            pass

    # Cachefile used by quick_adcp.py
    try:
        cc=Cachefile('dbinfo.txt')
        cc.read()
    except:
        print('no dbinfo file')
        pass


    if hasattr(cc, 'cachedict'):
        F.write('\n\n--- original processing parameters from dbinfo.txt ----------\n\n')
        F.write('<...> NOTE: Replace the text below with the final dbinfo.txt content\n')
        F.write('<...>        after you are done with all postprocessing.  Change the\n')
        F.write('<...>        comment to say "final processing parameters" \n')
        for line in cc.comments:
            if line[:2] == '##':
                F.write('\n' + line)
        F.write('\n')
        kk= list(cc.cachedict.keys())
        kk.sort()
        llist=[]
        for k in kk:
            llist.append('%20s   %s' %(k,cc.cachedict[k]))
        F.write('\n'.join(llist))
        F.write('\n')

    s = string.Template(instruction_str)
    try:
        ss=s.substitute(sonar=cc.cachedict['sonar'], dbname=cc.cachedict['dbname'])
    except:
        ss=s.substitute(sonar=opts['sonar'], dbname=opts['dbname'])

    F.write(ss)  # instructions
    F.close()
    return 0,'wrote cruise metadata to %s' % (fname,)

#==================================================================


def main():

    from pycurrents.adcp.quick_adcp import get_default_opts, parse_opts

    parser = OptionParser(__doc__)
    parser.add_option("--dbname ", dest="dbname",
                      help="database path")
    parser.add_option("--cruisename ", dest="cruisename",
                      help="cruise ID or title for web page and some plots ")
    parser.add_option("--sonar ",   dest="sonar",
                      help="sonar name [os75bb, os75nb, wh300, nb150,...] ")
    parser.add_option("--datatype ",   dest="datatype",
                      help="data type [lta, enx, ens, uhdas, pingdata] ")
    parser.add_option("--hcorr_inst",   dest="hcorr_inst",
                      help="heading correction device, eg [posmv, seapath, abxtwo] ")

    options, args = parser.parse_args()

    if len(sys.argv[1:]) == 0:
        print(__doc__)
        sys.exit()

    opts = get_default_opts()
    cmdline_opts = parse_opts(sys.argv[1:])
    opts.update(cmdline_opts)
    if not options.dbname:
        try:
            opts['dbname'] = os.path.split(guess_dbname('./'))[-1]
        except:
            opts['dbname'] = None

    opts['hcorr_inst'] = options.hcorr_inst # fixme

    if options.sonar:
        sonar = Sonar(options.sonar)
        opts['instname'] = sonar.instname
        opts['pingtype'] = sonar.pingtype

    for kk,vv in opts.items():
        if vv is None:
            opts[kk] = 'unspecified'
        if vv == '':
            opts[kk] = 'unspecified'
        if vv == 'None':
            opts[kk] = 'unspecified'

    opts['ping_headcorr'] = None

    try:
        status, msg = write_report(opts)
        print(msg)
    except:
        raise Exception('quick_template.py failed.  Could not write report')

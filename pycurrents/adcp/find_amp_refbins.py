import string
import os
import subprocess

import numpy as np
import matplotlib.pyplot as plt
from pycurrents.system.misc import Bunch
from pycurrents.adcp.quick_mpl import Wtplot
from pycurrents.codas import to_datestring

# (1) run from cal/watertrk
# (2) choose endbin and reflayer step
# default is to output a file

#------------------------------------


names = ['startbin', 'endbin', 'mid_depth', 'edited',
         'amp_mean', 'amp_median', 'amp_std',
         'phase_mean', 'phase_median', 'phase_std']

fformat = '%8d %8d %10.1f %8d  %10.4f %10.4f %10.4f %10.4f %10.4f %10.4f\n'

dtype_bunch = Bunch()
for name in ['startbin', 'endbin', 'edited']:
    dtype_bunch[name] = np.int16
for name in names:
    if name not in dtype_bunch.keys():
         dtype_bunch[name] = np.float64
dtype_list = []
for name in names:
    dtype_list.append(dtype_bunch[name])


asnav_str = '''
           dbname:             ${dbname}
           output:             aship_refl     /* writes to ./aship.nav */
           step_size:          1
           ndepth:             ${end_rlbin}  /* extract this many bins */
           time_ranges:        separate
           year_base=          ${yearbase}

           option_list:
             pg_min=           50
           navigation:
             reference_bins  ${start_rlbin}  to   ${end_rlbin}
             end
           statistics:       mean
             units=          0.01       /* cm/s instead of default m/s */
             end
           flag_mask:        ALL_BITS
             end
           end
          ${daterange}
'''

timslip_str = '''

        fix_file_type:      simple
        fix_file:           ${txyfile}

        reference_file:     aship_refl.nav   /* from adcpsect run */
        output_file:        ${calfile}

        year_base=          ${yearbase}

        min_n_fixes=        ${min_n_fixes} /* 5 7 9 */

        n_refs=             ${n_refs}      /* 5 7 9 */

        i_ref_l0=     1
        i_ref_l1=           ${i_ref_l1}    /* 1 2 3 */
        i_ref_r0=           ${i_ref_r0}    /* 4 5 6 */
        i_ref_r1=           ${i_ref_r1}    /* 4 6 8 */

        up_thresh=          ${speed_cutoff}        /* m/s */
        down_thresh=        ${speed_cutoff}        /* m/s */
        turn_speed=         2.0        /* m/s */
        turn_thresh=        60         /* degrees */

        dtmax=              360        /* seconds, for 300-second ensembles */
        tolerance=          5.e-5      /* days, about 5 seconds */
        grid:               ensemble

        use_shifted_times?  no
'''

def run_adcpsect(dbname, yearbase, start_rlbin=2, end_rlbin=20, verbose=False,
                 ddrange=None):
    s=string.Template(asnav_str)

    if ddrange is None:
        daterange='all'
    else: # assume tuple of decimal days
        start_date = to_datestring(yearbase, ddrange[0])
        end_date = to_datestring(yearbase, ddrange[1])
        daterange = '%s to %s' % (start_date, end_date)

    tmpstr = s.substitute(dbname=dbname, yearbase=yearbase,
                          start_rlbin=start_rlbin,
                          end_rlbin=end_rlbin,
                          daterange=daterange)
    with open('asnav_refl.tmp', 'w') as file:
        file.write(tmpstr)
    status, output = subprocess.getstatusoutput('adcpsect asnav_refl.tmp')
    if status:
        print('adcpsect failed: %s' % (output))
    else:
        if verbose:
            print(output)


def run_timslip(txyfile, yearbase, calfile, speed_cutoff=3.0, morepts=False):
    s=string.Template(timslip_str)

    if morepts:
        min_n_fixes=    5
        n_refs=         5
        i_ref_l1=       1
        i_ref_r0=       4
        i_ref_r1=       4
    else:
        min_n_fixes=   7
        n_refs=        7
        i_ref_l1=      2
        i_ref_r0=      5
        i_ref_r1=      6

    tmpstr = s.substitute(txyfile=txyfile,
                          calfile=calfile,
                          yearbase=yearbase,
                          min_n_fixes=  min_n_fixes,
                          n_refs=       n_refs,
                          i_ref_l1=     i_ref_l1,
                          i_ref_r0=     i_ref_r0,
                          i_ref_r1=     i_ref_r1,
                          speed_cutoff=speed_cutoff,
                          )

    with open('timslip_refl.tmp', 'w') as file:
        file.write(tmpstr)
    status, output = subprocess.getstatusoutput('timslip timslip_refl.tmp')
    if status:
        print('timslip failed: %s' % (output))
    else:
        print(output)

def get_WT_str(calfile, yearbase):
    WT = Wtplot()
    # fake init
    for p in WT.defaultparams:
        setattr(WT, p, WT.defaultparams[p])
    # override
    WT.cal_filename = calfile
    WT.ddrange = None
    try:
        WT.get_data()
    except:
        print('No watertrack calibration data')
        return('')
    if not WT.edit_points():
        print('Fewer than 2 edited points found. No WT plot made.')
        return('')
    statstr = WT.get_stats()
    return(statstr)

def parse_wtstr(statstr):
    '''
    return a Bunch with
        cal.amp.mean, cal.amp.med, cal.amp.std
        cal.phase.mean, cal.phase.med, cal.phase.std
        cal.num.edited,  cal.num.total
        cal.ddrange # dday range of data
        cal.timestamp
    '''
    cal = Bunch()
    cal.num = Bunch()
    cal.amp = Bunch()
    cal.phase = Bunch()
    for line in statstr.split('\n'):
        if 'Time range' in line:
            parts = line.split()
            cal.ddrange = (float(parts[2]), float(parts[4]))
        if 'Calculation done' in line:
            cal.timestamp = line.strip()
        if 'Number of edited' in line:
            parts = line.split()
            cal.num.edited = int(parts[4])
            cal.num.total  = int(parts[7])
        if 'amplitude  ' in line:
            parts = line.split()
            cal.amp.median  = float(parts[1])
            cal.amp.mean  = float(parts[2])
            cal.amp.std  = float(parts[3])
        if 'phase     ' in line:
            parts = line.split()
            cal.phase.median  = float(parts[1])
            cal.phase.mean  = float(parts[2])
            cal.phase.std  = float(parts[3])
    return(cal)

def write_cals(allcal, caldatafile = 'wt_cal_refbins.txt'):
    if os.path.exists(caldatafile):
        os.remove(caldatafile)

    wtf = open(caldatafile,'a') # water track file
    wtf.write('# ' + ', '.join(names) + '\n')
    for v in allcal:
        wtf.write(fformat % tuple(v))
    wtf.close()

def read_cals(caldatafile='wt_cal_refbins.txt'):
    ## is it worth making a structured array for any reason?
    # np.dtype({    'names': names,    'formats': dtype_list        })
    data = Bunch()
    columns = np.loadtxt(caldatafile)
    for num in range(len(names)):
        data[names[num]] = columns[:,num]
    return data

def plot_cals(data, title, autoscale=False):
    f = plt.figure(figsize=(10,7))
    ax1=f.add_subplot(161)
    ax2=f.add_subplot(162, sharey=ax1)
    ax3=f.add_subplot(132, sharey=ax1)
    ax4=f.add_subplot(133, sharey=ax1)
    ax=[ax1, ax2, ax3, ax4]

    y = data.mid_depth
    ax[0].plot(data.edited,    y, 'b.-'  )
    ax[0].grid(True)
    ax[1].plot(data.amp_std,   y, 'y.-')
    ax[1].set_xlim(0, 0.05)
    ax[1].grid(True)
    ax[2].plot(data.amp_mean,  y, 'ro')
    ax[2].plot(data.amp_median,y,  'k.')
    ax[2].grid(True)
    ax[3].plot(data.phase_mean,  y, 'go')
    ax[3].plot(data.phase_median,y,  'k.')
    ax[3].grid(True)

    ax[0].invert_yaxis()
    ax[0].set_ylabel('depth, meters')

    ax[0].set_title('watrtrk # points')
    ax[1].set_title('stddev(amp)')
    ax[2].set_title('amplitude')
    ax[3].set_title('phase')
    ax[2].text(.9,.2,'mean', color='r', transform = ax[2].transAxes, ha='right')
    ax[2].text(.9,.1,'median', color='k', transform = ax[2].transAxes, ha='right')
    ax[3].text(.9,.2,'mean', color='g', transform = ax[2].transAxes, ha='right')
    ax[3].text(.9,.1,'median', color='k', transform = ax[2].transAxes, ha='right')

    if not autoscale:
        ax[2].set_xlim([.970, 1.03])
        ax[2].xaxis.grid()
        ax[3].set_xlim([-1,1])
        ax[3].xaxis.grid()

    ax[0].set_ylim(max(y), 0)
    ax[2].vlines(1.0, 0, max(y), colors='k')
    ax[2].vlines([.99, 1.01], 0, max(y), colors=(.5,.5,.5))
    ax[3].vlines(0.0, 0, max(y), colors='k')
    ax[3].vlines([-0.5, 0.5], 0, max(y), colors=(.5,.5,.5))



    f.text(.5, .95, title, ha='center')

    return f

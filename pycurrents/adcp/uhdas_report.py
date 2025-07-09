'''
create a directory with reports about a uhdas cruise
'''

import logging
import logging.handlers

import os
import glob
import string
import subprocess

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

from pycurrents.adcp.adcp_specs import Sonar
from pycurrents.adcp.uhdas_defaults import codas_adcps
from pycurrents.adcp.uhdas_defaults import serial_msgstr
from pycurrents.adcp.uhdas_cfg_api import get_cfg
from pycurrents.codas import get_profiles
from pycurrents.file.binfile_n import BinfileSet
from pycurrents.file.mfile import mfile_to_bunch
from pycurrents.plot.mpltools import add_UTCtimes
from pycurrents.system import Bunch


_log = logging.getLogger(__name__)

# TODO : Instead of log.warning do we need log.exception to show what went
# wrong? Raise or just warn?


class HeadingSerialReport(object):
    '''
    get raw attitude statistics
    '''
    def __call__(self, uhdas_dir, inst, msg, outfile=None, cruisename='cruise', cutoff=0.02):
        self.uhdas_dir = uhdas_dir
        self.inst = inst
        self.msg = msg
        self.inst_msg = '%s_%s' % (self.inst, self.msg)
        self.cruisename = cruisename
        self.cutoff=cutoff

        if outfile is None:
            outfile = '%s_%s_quality.txt' % (inst, msg)
        self.outfile = outfile
        self.make_report()


    def get_numbad(self, data):
        '''
        return number bad, and a description of the error
        '''
        ## TODO -- posmv: get mean and stddev of heading accuracy
        if self.msg in ('adu', 'at2', 'paq'):
            return int(sum(data.reacq)), 'failed (required reacqusition)'
        if self.msg == 'pmv':
            num_bad_heading = int(sum(data.acc_heading > self.cutoff))
            msg = "failed (heading accuracy error exceeded cutoff of %3.1f)" % (self.cutoff)
            return num_bad_heading, msg
        if self.msg == 'gps_sea':
            return int(sum(data.head_qual!=0)), "failed (nonzero heading quality)"
        if self.msg in ('hnc_tss1', 'hdg_tss1'):
            return int(sum(data.status != 7)), "failed (status != 7)"
        return ()

    def make_report(self):
        outlist =  ['=========  %s %s quality stats ===========' % (
                                           self.cruisename, self.inst_msg) ,]
        self.outlist = outlist
        rbin_glob = '%s/rbin/%s/*%s.rbin' % (self.uhdas_dir, self.inst, self.msg)
        # should only be one suffix in raw
        raw_glob  = '%s/raw/%s/*' % (self.uhdas_dir, self.inst)
        nmea = serial_msgstr[self.msg]
        cmd = "zgrep %s %s | wc" % (nmea[1:], raw_glob)  # don't include $ in grep
        try:
            outstr = subprocess.check_output(cmd, shell=True).decode('ascii').rstrip()
            num_raw = int(outstr.split()[0])
            outlist.append("%s %s messages found by string match" % (num_raw, nmea))
            if num_raw >0:
                bindata = BinfileSet(rbin_glob)
                #
                numrbins = len(bindata.dday)
                outlist.append("%d %s lines transformed to rbins (%3.2f%% of total)" % (
                    numrbins, nmea, 100.0*numrbins/num_raw))
                    #
                if numrbins > 0:
                    numbad, errstr = self.get_numbad(bindata)
                    outlist.append('%d %s (%3.2f%% of total)\n' % (
                                              numbad, errstr, 100.0*numbad/num_raw))
                    #
                outlist.append('')
                if self.outfile is None:
                    _log.info('\n'.join(outlist))
                else:
                    with open(self.outfile, 'w') as file:
                        file.write('\n'.join(outlist))
        except Exception:
            _log.warning('could not get %s report for %s' % (self.msg, self.uhdas_dir))



class UHDAS_CruiseInfo(object):
    def __init__(self, verbose=False, debug=False):
        '''
        usage:
        CI = UHDAS_CruiseInfo()
        CI.set_uhdas_dir('/home/data/km1001c')
        CI.get_info()
        '''
        self.verbose = verbose
        if debug:
            _log.setLevel(logging.DEBUG)
        else:
            _log.setLevel(logging.INFO)


    #-----
    def __call__(self,  uhdas_dir):
        self.uhdas_dir = uhdas_dir

        proc_globlist = ['*_proc.py', 'procsetup_onship.py', '*_proc.m',
                            '*_proc.toml',]
        sensor_globlist= ['sensor_cfg.py', '*_sensor.py',
                            'sensor_cfg.toml', '*_sensor.toml']

        self.proc_file = self.get_configfile(proc_globlist)
        if self.proc_file is not None and self.proc_file[-1] != 'm':
            self.proc_cfg = get_cfg(self.proc_file)

        self.sensor_file = self.get_configfile(sensor_globlist)
        if self.sensor_file is None:
            _log.warning('could not find sensor_cfg.*')
        else:
            self.sensor_cfg = get_cfg(self.sensor_file)


        if not hasattr(self.proc_cfg, 'yearbase'):
            #try again
            mprocfile = self.get_configfile(['*_cfg.m'])
            if mprocfile is not None:
                mdict = mfile_to_bunch(mprocfile)
                if hasattr(mdict, 'yearbase'):
                    self.proc_cfg.yearbase = mdict.yearbase
                else:
                    self.proc_cfg.yearbase = None

        # get heading correction inst
        # fill hcorr_info (with None if necessary)
        self.hcorr_info = Bunch()
        if self.proc_file is not None:
            if self.proc_file[-2:] == 'py':
                for k in self.proc_cfg.keys():
                    if 'hcorr_' in k:
                        self.hcorr_info[k] = self.proc_cfg[k]
        if 'hcorr_inst' not in self.hcorr_info.keys():
            self.hcorr_info.hcorr_inst = None
        if 'hcorr_msg' not in self.hcorr_info.keys():
            try:
                messages = self.guess_hcorr_msg()
                if len(messages) > 1:
                    _log.warning('found multiple heading correction messages: %s' % (
                        ' '.join(messages)))
                    self.hcorr_info.hcorr_msg = None
                elif len(messages) == 1:
                    self.hcorr_info.hcorr_msg = messages[0]
                else:
                    _log.warning('found no heading correction messages')
                    self.hcorr_info.hcorr_msg = None
            except Exception:
                _log.warning('could not guess heading correction message.  specify on command line')
                self.hcorr_info.hcorr_msg = None

        # get acc_heading_cutoff if it exists
        self.acc_heading_cutoff = 0.02
        if self.proc_file is not None:
            if self.proc_file[-2:] == 'py':
                for k in self.proc_cfg.keys():
                    if 'acc_heading_cutoff' in k:
                        self.acc_heading_cutoff = self.proc_cfg['acc_heading_cutoff']

        #get position instrument
        self.gps_info = Bunch()
        if self.proc_file is not None:
            if self.proc_file[-2:] == 'py':
                for k in self.proc_cfg.keys():
                    if 'pos_' in k:
                        self.gps_info[k] = self.proc_cfg[k]
        if not hasattr(self.gps_info, 'gps_inst'):
            #try again
            mprocfile = self.get_configfile(['*_cfg.m'])
            if mprocfile is not None:
                mdict = mfile_to_bunch(mprocfile)
                if hasattr(mdict, 'best_gps_rule'):
                    self.gps_info.pos_inst, self.gps_info.pos_msg = mdict.best_gps_rule


        try:
            self.cruisename = os.path.splitext(os.path.basename(self.proc_file))[0][:-5]
        except Exception:
            self.cruisename = 'cruise'

        self.get_sonarinfo()


    #----
    def guess_hcorr_msg(self):
        '''
        - assumes we already have self.sensor_cfg and self.hcorr_info.hcorr_inst
        - this is required because we mapped instrument to message back in matlab days
        '''
        from pycurrents.adcp.uhdasfile import headingmsg
        for sensor in self.sensor_cfg.sensors:
            if sensor['subdir'] == self.hcorr_info.hcorr_inst:
                sensor_msgs = set(sensor['messages'])
                break  # use this one
        for heading_list in headingmsg:
            if heading_list[0] ==  self.hcorr_info.hcorr_inst:
                hcorr_msgs = set(heading_list[1])
                break # use this one
        msgs = sensor_msgs.intersection(hcorr_msgs)
        messages=[]
        for mm in msgs:
            messages.append(mm)
        return messages


    #-----
    def get_configfile(self, globlist=None):
        '''
        input: uhdas directory and list of preferred wildcard expansions:
            proc_globs = ['*_proc.py', '*_proc.m']
            sensor_globs = ['sensor_cfg.py', 'sensor_cfg.toml', '*_sensor.py']
        output: path of most recent file found using wildcards
        '''
        configdir =  os.path.join(self.uhdas_dir, 'raw', 'config')
        if self.verbose:
            _log.debug('config dir is %s' % (configdir))
        for gg in globlist:
            gstr = os.path.join(configdir, gg)
            glist = glob.glob(gstr)
            glist.sort()
            if self.verbose:
                _log.debug('globstr is %s' % (gstr))
            if len(glist) == 0:
                continue
            s_glist = sorted(glist, key=os.path.getmtime)
            return s_glist[-1] #most recent
        return None

    def get_sonarinfo(self):
        self.procpaths = []
        self.instruments = []
        try:
            for procdir in glob.glob(os.path.join(self.uhdas_dir, 'proc', '*')):
                self.procpaths.append(procdir)
                sonar = Sonar(os.path.basename(procdir))
                instrument = sonar.instname
                if instrument not in self.instruments and instrument in codas_adcps:
                    self.instruments.append(instrument)
        except Exception:
            _log.warning('no appropriate sonars found')




class CODAS_ProcInfo(object):
    def __init__(self, procdir, verbose=False, debug=False):
        '''
        This is a placeholder for further development
        '''
        #usage:
        #CPI = CODAS_ProcInfo()
        #CPI.set_procdir('os75_LTA')
        #CPI.get_info()

        self.verbose = verbose
        if debug:
            _log.setLevel(logging.DEBUG)
        else:
            _log.setLevel(logging.INFO)
        self.procdir = procdir


class DB_TimerangePlotter(object):
    def __init__(self, dblist):
        self.dblist = dblist

    def get_colpat(self, sonar):
        colordict=Bunch()
        colordict['1200'] = ('y', 'y')
        colordict['600'] =  ('m', 'm')
        colordict['300'] =  ('k', 'k')
        colordict['150'] =  ( (.5,.5,.5), (1,0,0))
        colordict['75'] =   ( (.5,.5,.5), (.2,1,.2))
        colordict['38'] =   ( (.5,.5,.5), (0,0,1))
        #
        if sonar.pingtype == 'bb':
            color = colordict[sonar.frequency][0]
        else:
            color = colordict[sonar.frequency][1]
        return color

    def guess_sonar(self, dbpath):
        #dbpath is blah/blah/os75bb/adcpdb/aXXX
        parts = dbpath.split(os.sep)
        procdir = os.sep.join(parts[:-2])
        # look for dbinfo.txt
        dbinfo_file = os.path.join(procdir, 'dbinfo.txt')
        if os.path.exists(dbinfo_file):
            with open(dbinfo_file,'r') as newreadf:
                lines = newreadf.readlines()
            for line in lines:
                parts2 = line.split()
                if parts2[0] == 'sonar':
                    sonar = parts2[1]
                    return Sonar(sonar)
        # guess from procdirname
        try:
            return Sonar(parts[-3]) # eg. 'os75bb'
        except Exception:
            _log.warning('could not get sonar from %s' % (dbpath))
            return None

    def plot_sonars(self, cruise=None):
        f = plt.figure(figsize=(8,8))
        ax=f.add_subplot(111)
        plt.subplots_adjust(right=0.8)
        ax.set_ylim(0,320)
        mindday = 999.0
        maxdday = -999.0
        for db in self.dblist:
            sonar = self.guess_sonar(db)
            if sonar:
                color = self.get_colpat(sonar)
                pingtype = sonar.pingtype
                freq = int(sonar.frequency)
                if pingtype == 'bb':
                    poffset = -5
                else:
                    poffset = 5
            else:
                color='r'
                freq = 123
                poffset = 0
            data=get_profiles(db[:-7])
            mindday = min(mindday, data.dday[0])
            maxdday = max(maxdday, data.dday[-1])
            yearbase = data.yearbase
            ax.plot(data.dday, freq+poffset+0*data.dday, '.', ms=4, color=color)
        #
        ax.set_xlim(mindday, maxdday)
        f.subplots_adjust(bottom=0.15)
        for db in self.dblist:
            sonar = self.guess_sonar(db)
            if sonar:
                color = self.get_colpat(sonar)
                pingtype = sonar.pingtype
                freq = int(sonar.frequency)
                if pingtype == 'bb':
                    poffset = -5
                else:
                    poffset = 5
                freq = int(sonar.frequency)
                sonarname=sonar.sonar
            else:
                freq=123
                poffset=0
                sonarname='unknown'
                color='r'

            ax.text(maxdday+0.03*(maxdday-mindday), freq+poffset, sonarname, color=color, weight='bold')
        ax.set_title('extent of sonar use')
        ax.set_ylabel('frequency')
        ax.set_xlabel('')
        ax.tick_params(axis='x', direction='in')

        aa = ax.twinx()
        aa.xaxis.set_major_formatter(ScalarFormatter(useOffset = False))
        aa.set_xlim(mindday, maxdday)
        aa.set_yticks([])
        add_UTCtimes(aa, yearbase, position='bottom')
        f.subplots_adjust(bottom=0.2)

        if cruise is not None:
            f.text(.45, .95, cruise, ha='center')
        #
        return f


class ReportActions(object):
    def __init__(self, report_dir='./', runnit=False, verbose=False):

        self.report_dir = report_dir
        self.runnit=runnit
        self.verbose = verbose

    def make_cmd(self, strtemplate, filename, remove=False):
        '''
        if requested:
            print command
            remove original
        fill command as attribute
        '''
        outfile = os.path.join(self.report_dir, filename)
        if remove:
            try:
                os.remove(outfile)
                if self.verbose:
                    _log.info('removing %s' % (outfile))
            except (FileNotFoundError, PermissionError):
                pass

        cmd = strtemplate % (outfile)
        return cmd

    def run_cmd(self, cmd, system_rsync=True):
        '''
        if requested:
            run command
        '''
        if self.runnit:
            try:
                if system_rsync and 'rsync' in cmd:
                    os.system(cmd)
                    return "no feedback: ran rsync with 'os.system()'", ''

                proc=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  universal_newlines=True)
                stdout, stderr = proc.communicate()
                return stdout, stderr
            except Exception:
                msg = 'command failed\n%s' % (cmd)
                _log.warning(msg)
                return '', msg


class HTML_page(object):
    def __init__(self, cruisename, report_dir='./', catlist=None):
        '''
        provides tools to create chunks in an html document
        '''
        if catlist is None:
            self.catlist = ['overview', 'processed ADCP', 'quality',
                            'raw ADCP', 'UHDAS settings', 'serial logging']
        else:
            self.catlist = catlist
        self.cruisename = cruisename
        self.report_dir = report_dir


        self.newline = '<br>'
        self.space = '&nbsp'


        ## lists of html lines in categories
        html_catlists = Bunch()
        for name in self.catlist:
            html_catlists[name] = []


            self.header = '''<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
            <html>
            <head>
              <meta  http-equiv="Refresh" content="120">
              <title>${CRUISE} ${TITLE_TEXT}</title>
            </head>
            <body>
               <br>
               <div style="text-align: center;"><big><span style="font-weight:
                bold;"> ${CRUISE} summary report</span>
                </big></div>


            <br><br>
            '''


            self.tail = '''</body>
            </html>
            '''

    def comment(self, text='REPLACEME'):
        return ' <!-- %s --> \n' % (text)


    def make_html_index(self, html_list, title_text='summary report'):
        '''
        html_list is generated by using the other modules in HTML_page, such as
        make_table_row
        make_table (from rows)
        make_plot_html
        make_html_entry  (simple link)

        returns assembled string
        '''

        hlist = []
        # header
        s = string.Template(self.header)
        hlist.append(s.substitute(CRUISE=self.cruisename, TITLE_TEXT=title_text))
        for h in html_list:
            hlist.append(h)
        hlist.append(self.tail)
        return '\n'.join(hlist)


    def make_html_entry(self, filename, text):
        '''
        return simple link to a file
        '''
        h="<a href='%s' >  %s</a>" % (filename, text)
        return h

    def make_expanded_html_entry(self, filename):
        '''
        fill with contents of file, not a link to the file
        '''
        if os.path.exists(filename):
            with open(filename, 'r') as newreadf:
                text = newreadf.read()
            h="<pre>\n%s\n</pre>" % (text)
            return h
        else:
            return "<b>ERROR:</b> file %s does not exist" % (filename)


    def make_table_row(self, cells, alignments=None):
        '''
        'cells' is a list of the items to go in columns.  return the string
        if using align, it should be an array with elements 'left', 'right' or 'center'
            same len as 'cells'
        '''
        rowlist = ['   <tr>',]
        if alignments is None:
            for cell in cells:
                rowlist.append('\n'.join(['    <td>', cell, '    </td>']))
            rowlist.append('   </tr>')
        else:
            for cell, align in zip(cells, alignments):
                rowlist.append('\n'.join(['    <td align="%s">' % (align), cell, '    </td>']))
            rowlist.append('   </tr>')
        return '\n'.join(rowlist)

    def make_table(self, rowlist):
        tlist = [
            ''' <table
          style="width: 100%; text-align: center;  vertical-align: middle;
          background-color: rgb(251, 251,  251);"
          border="1" cellpadding="2" cellspacing="2">
           <tbody>
            ''',]
        tlist.append('\n'.join(rowlist))
        tlist.append('</tbody>')
        tlist.append('</table>')
        return '\n'.join(tlist)


    def thumbnail_cmd(self, figname, tpix=400):
        cmd = 'png_thumbnail.py  --width %d  --outdir %s  %s ' % (tpix, self.report_dir, figname )
        return cmd


    def make_plot_html(self, fignamebase, alt_text='plot'):
        '''
        make html chunk for plot;
        requires running         self.make_html_file_for_figure(fignamebase, alt_text)
        return string
        '''

        htemp = '''<a href="./${FIGNAME}.html" name="">
                  <img alt="${ALT_TEXT}"
                   src="./${FIGNAME}T.png"
                   style="border: 0px solid ;" align="middle"> </a>
                  '''
        hstr = string.Template(htemp)
        newstr = hstr.substitute(FIGNAME=fignamebase, ALT_TEXT=alt_text)
        return newstr

    def make_plot_html0(self, fignamebase, link_target, alt_text='plot', ):
        '''
        make html chunk for plot;
        ## point to png; not html with 'refreshing' png
        return string
        '''

        htemp = '''<a " href="./${LINK_TARGET}" name="">
                  <img alt="${ALT_TEXT}"
                   src="./${FIGNAME}T.png"
                   style="border: 0px solid ;" align="middle"> </a>
                  '''
        hstr = string.Template(htemp)
        newstr = hstr.substitute(FIGNAME=fignamebase, ALT_TEXT=alt_text, LINK_TARGET=link_target)
        return newstr


    def make_html_file_for_figure(self, fignamebase, alt_text):
        '''
        make html file for figure, write to out_dir/fignamebase.html
        '''
        stemp = '''
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head>
        <title>${TEXT}</title></head>
        <body>
        <img src="./${FIGNAME}.png">
        <br>
        <br>
        <br>
        </body></html>
        '''
        outfile = os.path.join(self.report_dir, '%s.html' % (fignamebase))
        s = string.Template(stemp)
        newstr = s.substitute(FIGNAME=fignamebase, TEXT=alt_text)
        with open(outfile, 'w') as file:
            file.write(newstr)

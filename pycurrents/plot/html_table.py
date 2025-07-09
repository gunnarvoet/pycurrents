'''
This is used by uhdas/scripts/run_3dayplots.py to create index.html
for png_archive
'''

import os
import string
import sys
import glob
import logging

from PIL import Image

from pycurrents.plot.mpltools import nowstr

_log = logging.getLogger(__name__)

class html_table:
    def __init__(self, rows, columns,
                            figdir='./',
                            instname = None,
                            outfile='index.html',
                            width=400,
                            redo=False,
                            reverse = False,
                            title = 'ADCP Thumbnails',
                            convention = 'num_sec',
                            fullsize = False):
        self.rows = rows
        self.columns = columns
        self.figdir   = figdir
        self.redo     = redo
        self.outfile  = outfile
        self.instname = instname
        self.convention = convention
        self.width = width
        self.reverse = reverse
        self.title = title


        #---------  index.html templates ------------------
        self.ttable_head = '''
        <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html>
        <head>
           <title>${title}</title>
        </head>
        <body>
        <br>
        <div style="text-align: center;"><big><span style="font-weight:
        bold;"> ${title}</span>
        </big></div>
        <table
          style="width: 100%; text-align: center;  vertical-align: middle;
        background-color: rgb(51, 102, 255);"
          border="1" cellpadding="2" cellspacing="2">
           <tbody>
        <!-- FIGURES -->
        '''

        if fullsize:
            im_src = "./${basename}.png"
        else:
            im_src = "./thumbnails/${basename}_thumb.png"

        self.ttable_col = f'''
        <td style="text-align: center; vertical-align: middle;
                    background-color: rgb(204, 204, 204);">
                    <a target="" href="./${{basename}}.html">
             <img alt="${{basename}}"
                   src="{im_src}"
                   style="border: 0px solid ;" align="middle"> </a> <br>
            <span style="font-weight: bold;">${{basename}}</span><br>
        </td>
        '''

        #---------

        self.ttable_tail = '''
           </tbody>
        </table>
        </body>
        </html>
        '''

        #-------------------------------------------------------


        ## for fig.html

        self.html_figfile_template = '''
        <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
        <html><head>
        <meta http-equiv="Refresh" content="30">
        <title>${basename}</title></head>
        <body>
        <img src="./${basename}.png">
        <br>
        <br>
        <br>
        </body></html>
        '''

    def make_ttable(self):
        fname = os.path.join(self.figdir, self.outfile)

        if os.path.exists(fname) and self.redo is False:
            _log.debug('not overwriting %s', fname)
            sys.exit()

        s = string.Template(self.ttable_head)
        tlist = [s.substitute(title=self.title)]

        s = string.Template(self.ttable_col)
        for row in self.rows:   #sec_01: suffixes are numbers
            tlist.append('<tr>')
            for column in self.columns:
                # assemble parts
                basename = assemble_parts(self.convention, row, column,
                            instname = self.instname)
                pngfile = '%s.png' % (basename)
                pngpath = os.path.join(self.figdir, pngfile)
                tlist.append(s.substitute(basename=basename))
                # make html file for png
                self.make_html_figshell(basename)
                if os.path.exists(pngpath):
                    self.make_thumb(pngfile, width=self.width) # path is in self.figdir
                else:
                    # FIXME: use a stock "not available" png
                    pass
            tlist.append('</tr>')
        tlist.append(self.ttable_tail)
        with open(fname, 'w') as file:
            file.write('\n'.join(tlist))


    def make_html_figshell(self, basename):
        fname = "%s.html" % (basename,)
        dest = os.path.join(self.figdir, fname)

        if os.path.exists(dest) and self.redo is False:
            _log.debug('not overwriting %s', dest)
            sys.exit()

        s = string.Template(self.html_figfile_template)
        h = s.substitute(basename=basename)
        with open(dest, 'w') as file:
            file.write(h)

    def make_thumb(self, infile, width=400):
        rect = (width, 1.2*width)
        # infile is just the file; path is in self.figdir
        filebase, ext = os.path.splitext(infile)
        tfile = os.path.join(self.figdir, 'thumbnails', '%s_thumb%s' % \
                            (filebase, ext))
        if os.path.exists(tfile) and self.redo is False:
            _log.debug('not overwriting %s', tfile)
            sys.exit()
        im = Image.open(os.path.join(self.figdir, infile))
        im.thumbnail(rect, Image.LANCZOS)
        im.save(tfile)

#------

def glob_by_parts(convention='onecolumn', gname=None):
    if convention != 'onecolumn' and gname is None:
        _log.error('must specify columns\n')
        sys.exit(1)

    if convention == 'num_sec':
        globstr = '*_%s.png' %(gname,)       #235_vect
    elif convention == 'sec_num':
        globstr = '%s_*.png' %(gname,)       #sec_01
    elif convention == 'uhdas':
        globstr = '*_%s.png' %(gname,)
    else: #convention = 'onecolumn'
        globstr = '*.png'
    return globstr

def assemble_parts(convention, row, column, instname=None):
    if convention == 'sec_num':
        # eg.  sec_01.png, secmap_01.png
        basename = '%s_%s' %(column, row)
    elif convention == 'num_sec':
        # eg.  235_vect.png, 235_cont.png
        basename = '%s_%s' %(row, column)
    elif convention == 'uhdas':
        #eg.   245_os38nb_shallow.png
        #      245_os38nb_ddaycont.png
        #      245_os38nb_latcont.png
        #      245_os38nb_loncont.png

        basename = '%s_%s_%s' %(row, instname, column)
    else:
        basename = os.path.splitext(os.path.basename(row))[0]

    return basename

#-----------------

def uhdas_split(filelist):
    nums = []
    instname = '' # initialized in case filelist is empty; never should happen
    for f in filelist:
        basename = os.path.basename(f)
        filebase, ext = os.path.splitext(basename)
        parts = filebase.split('_')
        nums.append(parts[0])
        instname = parts[1]
    nums.sort()
    return nums, instname

def secnum_split(filelist):
    nums = []
    instname = None
    for f in filelist:
        basename = os.path.basename(f)
        filebase, ext = os.path.splitext(basename)
        parts = filebase.split('_')
        nums.append(parts[-1])
    nums.sort()
    return nums, instname


def numsec_split(filelist):  # need to handle olr2023-09-30_013042_[uv,topo].png
    nums = []
    instname = None
    for f in filelist:
        basename = os.path.basename(f)
        filebase, ext = os.path.splitext(basename)
        parts = filebase.split('_')
        nums.append('_'.join(parts[:-1]))  # num is olr2023-09-30_013042
    nums.sort()
    return nums, instname


def onecolumn_split(filelist):
    instname = None
    nums = []
    for f in filelist:
        basename = os.path.basename(f)
        filebase, ext = os.path.splitext(basename)
        nums.append(filebase)
    nums.sort()
    return nums, instname


func_dict = {'uhdas'   : uhdas_split,
             'sec_num' : secnum_split,
             'num_sec' : numsec_split,
             'onecolumn'    : onecolumn_split}

#-----------

class Convention_to_Html:
    '''
    generate index.html for one convention in 'uhdas', 'sec_num', 'num_sec', 'onecolumn'

    '''
    def __init__(self, figdir='./',
                 reverse = False,
                 convention = 'uhdas',
                 columns =  ('shallow', 'ddaycont', 'latcont', 'loncont'),
                 width = 400,
                 title = 'ADCP Thumbnails',
                 fullsize = False,
                 ):

        _log.debug('figdir: %s', figdir)
        _log.debug('convention: %s', convention)
        _log.debug('columns: %s', columns)

        if not os.path.exists(figdir):
            msg= '%s\nfigdir "%s" does not exist.  exiting\n' % (nowstr(), figdir,)
            raise IOError(msg)

        if convention == 'onecolumn':
            globstr = glob_by_parts(convention=convention)
        else:
            if type(columns) is not list:
                msg= 'must specify list of columns, consistent with convention'
                raise TypeError(msg)
            globstr = glob_by_parts(convention=convention, gname=columns[0])

        _log.debug(globstr)

        filelist = glob.glob(os.path.join(figdir, globstr))
        filelist.sort()
        _log.debug('\n'.join(filelist))

        # Don't pass an empty file list to the func_dict func;
        # stop right here until we figure out a better way of
        # handling this situation.
        if not filelist:
            raise RuntimeError("No files found matching %s" % globstr)

        nums, instname = func_dict[convention](filelist)
        if reverse:
            nums = nums[::-1]

        if not os.path.exists(os.path.join(figdir, 'thumbnails')):
            os.mkdir(os.path.join(figdir, 'thumbnails'))

        HTML = html_table(nums, columns,
                       instname = instname,
                       figdir = figdir,
                       outfile = 'index.html',
                       convention = convention,
                       title = title,
                       width=width,
                       redo = True,
                       fullsize = fullsize)
        HTML.make_ttable()

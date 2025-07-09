import string
import os
import subprocess
import glob

class Gallery:
    '''
    Consolidate simple components for creation of a restructured "page"
    - start with *.png
    - Gallery.make_thumbnails(*args, **kwargs) : make thumbnails of pngs
      using:
                     convert  -resize 400 figure.png figureT.png
    - Gallery.make_directive(*args, **kwargs)  : make text for a directive
                                                 and image call
    - Gallery.make_all() : convert all png, print skeleton page to stdout
'''

    def __init__(self):
        self.fig_template = '''
.. -------------------------------------------------------
.. |${name}| image:: ${figname}
                     :alt: ${atext}
.. _${name}: ${figname}
.. -------------------------------------------------------

'''



    def make_directive(self, name, figname, atext='alternate text'):
        '''
        returns chunk of text with directive
        '''
        s = string.Template(self.fig_template)
        h = s.substitute(name=name, figname=figname, atext=atext)
        return(h)


    def make_thumbnails(self, figname, suffix='T', dpi=400):
        '''
        converts figure.png to figureT.png using
        convert  -resize 400 figure.png figureT.png
        '''
        base, ext = os.path.splitext(figname)
        thumb = base + suffix + ext
        if os.path.exists(thumb):
            print('file exists: not making thumbnail %s' % (thumb))
            return
        #
        cmd = 'convert -resize %d  %s %s' % (dpi, figname, thumb)
        status, output = subprocess.getstatusoutput(cmd)
        if status != 0:
            print('ERROR: %s' % (cmd))
        else:
            print('running: %s' % (cmd))


    def make_all(self, outfile='index.rst'):
        outlist = []
        glist=glob.glob('*.png')
        filelist = []
        for f in glist:
            if ('T.png' not in f) and ('thumb.png' not in f):
                filelist.append(f)
        filelist.sort()

        # make thumbnails
        for f in filelist:
            self.make_thumbnails(f)

        # make all directives
        for f in filelist:
            base = os.path.splitext(os.path.basename(f))[0]
            s=self.make_directive(base, f, atext='ALTERNATE-TEXT')
            outlist.append(s)

        for f in filelist:
            base = os.path.splitext(os.path.basename(f))[0]
            outlist.append('|%s|_'  % (base))

        outstr = '\n'.join(outlist)
        if outfile is None:
            print(outstr)
        else:
            if os.path.exists(outfile):
                print('outfile %s exists. not overwriting')
                outfile = outfile + '.new'
            with open(outfile,'a') as file:
                file.write(outstr)
            print('wrote output to %s' % (outfile))

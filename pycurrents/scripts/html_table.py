#!/usr/bin/env python

import logging
import os
import sys

from pycurrents.plot.html_table import Convention_to_Html
from pycurrents.plot.mpltools import nowstr
#==================================================================
from optparse import OptionParser

_log = logging.getLogger()

def main():

    usage = '''

    html_table.py: [-d figdir] -[f htmlfile] [-t type] [-c columns]

    NOTE:  if type is 'uhdas', argument 'rows' is equivalent to
                      shallow:ddaycont:latcont:loncont
           if type is 'sec_num', default is
                      sec
           if type is 'lame', use the filenames for the left column
                       and the thumbnail on the right


    eg. for png_archive:
        cd png_archive; html_table.py -d os38nb -t uhdas --redo
        -or-
        cd png_archive/os38bb; html_table.py --redo

    eg. for research:
        cd workingdir; html_table.py -t sec_num -c sec:secmap --redo

'''


    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--figdir", dest="figdir", default="./",
                    help="directory with png files")
    parser.add_option("-f", "--htmlfile", dest="outfile", default='index.html',
                    help="html file to write, eg. index.html")
    parser.add_option("-T", "--title", dest="title", default='ADCP thumbnails',
                    help="visible title of table")
    parser.add_option("-t", "--type", dest="convention",
                    default="uhdas",
                    help="naming convention: 'num_sec', 'sec_num', 'onecolumn', or 'uhdas' (default)")
    parser.add_option("-c", "--columns", dest="columns",
                      default="shallow:ddaycont:latcont:loncont",
                      help="colon-delimted list (glob on these), eg sec:secmap")
    parser.add_option("-w", "--width", dest="width", default=300,
                    help="width of thumbnails")
    parser.add_option("--redo", dest="redo",
                  default=False,
                  help = "redo all files",
                  action="store_true")
    parser.add_option("--reverse", dest="reverse",
                  default=False,
                  help = "reverse the sorted order of files",
                  action="store_true")
    parser.add_option("-v", "--verbose", dest="verbose",
                  default=False,
                  help = "be verbose",
                  action="store_true")
    parser.add_option("--fullsize", dest="fullsize",
                  default=False,
                  help = "use full size images instead of thumbnails",
                  action="store_true")

    (options, args) = parser.parse_args()

    if options.verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    if not os.path.exists(options.figdir):
        print('figdir "%s" does not exist\n' % (options.figdir,))
        print('%s UTC:  html_table.py exiting' % (nowstr()))
        sys.exit()

    if options.convention not in ('uhdas','sec_num','num_sec', 'onecolumn'):
        print("convention %s not allowed\n" % (options.convention,))
        print(usage)
        print("choose 'uhdas', 'onecolumn', 'sec_num', or 'num_sec'\n")
        sys.exit()

    if options.convention not in ('uhdas', 'onecolumn') and options.columns is None:
        print(usage)
        print("MUST specify 'columns'\n")
        sys.exit()

    if options.convention == 'onecolumn':
        options.columns = ''

    Convention_to_Html(figdir = options.figdir,
                       reverse = options.reverse,
                       convention = options.convention,
                       columns = options.columns.split(':'),
                       width=int(options.width),
                       title = options.title,
                       fullsize = options.fullsize,
                       )


if __name__ == "__main__":
    main()

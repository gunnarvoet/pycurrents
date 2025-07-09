#!/usr/bin/env python
'''
use case:

# remake index.html to have COMMENTs for linking earlier and later reports

# generate the reports:
for cruise in `\ls | grep RB`
  do
  uhdas_report_generator.py -u $cruise --full_report --remake_index
done

# then make the overall index.html

 uhdas_cruisereport_index.py -rlt "Ron Brown UHDAS summaries"

The following directory structure is assumed:

ship/cruise01/reports
ship/cruise02/reports
ship/cruise03/reports
ship/cruise04/reports
ship/cruise05/reports

Run the command from 'ship'


'''



import argparse
import glob
import os
import subprocess

from pycurrents.system import logutils
from uhdas.system.uhdas_report_subs import  HTML_page

log = logutils.getLogger(__file__)

def make_html_entry(filename, text):
    '''
    return simple link to a file
    '''
    h="<a href='%s' >  %s</a>" % (filename, text)
    return h


def add_links_to_page(indexfile, earlier_file=None, later_file=None):
    dots = rel_path(indexfile)
    if earlier_file:
        earlier_link = make_html_entry(os.path.join(dots, earlier_file), 'earlier cruise')
    else:
        earlier_link=''
    if later_file:
        later_link = make_html_entry(os.path.join(dots, later_file), 'later cruise')
    else:
        later_link=''
    earlier_later_link =  '<br> %s &nbsp &nbsp %s <br><br> \n\n' % (earlier_link, later_link)
    back_to_index = make_html_entry(os.path.join(dots, 'index.html'), '(back to list)')
    #
    with open(indexfile, 'r') as newreadf:
        lines = newreadf.read().split('\n')
    for ii in range(len(lines)):
        if 'INDEX_LINKS' in lines[ii]:
            lines[ii] = earlier_later_link + '<br>' + back_to_index + '<br>'
    return lines



def rel_path(this_file):
    '''
    construct the relative path from thisfile back to root
    '''
    backdots = []
    if os.path.isdir(os.path.realpath(this_file)):
        dirname = this_file
    else:
        dirname = os.path.split(this_file)[0]
    for part in os.path.relpath(dirname).split(os.sep):
        backdots.append('..')
    return os.sep.join(backdots)


if __name__ == '__main__':


    parser = argparse.ArgumentParser(
        description="make a simple index.html for a group of cruise reports")


    parser.add_argument('-t', '--title',
                        default='UHDAS automated cruise reports',
                        help='ship name, or title for index.html')


    parser.add_argument('-p', '--prefix',
                        default=None,
                        help='shipletters: only grab these cruises for index.html')


    parser.add_argument('-r', '--reverse',
                        action='store_true',
                        default=False,
                        help='reverse order of links: oldest at the top')

    parser.add_argument('-l', '--add_links',
                        action='store_true',
                        default=False,
                        help='add links at top and bottom pointing to neighboring index.html.  stores in "index_linked.html"')

    opts = parser.parse_args()

    if opts.prefix is None:
        prefix = '*'
    else:
        prefix = opts.prefix

    ## this only works if all the cruises were named with the same prefix, eg Autopilot.
    cruise_glob1 = '%s*' % (prefix)
    cruise_glob2 = '*/%s*' % (prefix)

    indexes1 = glob.glob(os.path.join(cruise_glob1, 'reports', 'index.html'))
    indexes2 = glob.glob(os.path.join(cruise_glob2, 'reports', 'index.html'))
    indexes = indexes1 + indexes2

    indexes.sort()

    html_list = []
    HP_ = HTML_page(opts.title, report_dir='./')  # dummy

    if opts.add_links:
        log.info('about to write %d files with links to earlier, later' % (len(indexes)))

    if len(indexes) > 1:
        counter = range(len(indexes)-1)
        if opts.reverse:
            indexes = indexes[::-1]

        for inum in counter:
            index = indexes[inum]
            parts = index.split(os.sep)
            report_dir = os.path.split(index)[0]
            if len(indexes) > 1:
                if opts.add_links:
                    index_link = os.path.join(report_dir,  "index_links.html")
                    if inum  == 0:
                        earlier_file = None
                    else:
                        earlier_file = os.path.join(os.path.split(
                            indexes[inum - 1])[0], "index_links.html")

                    if inum == counter[-1]:
                        later_file = None
                    else:
                        later_file = os.path.join(os.path.split(
                            indexes[inum + 1])[0], "index_links.html")
                    #
                    if opts.reverse: # meaning is reversed
                        i2lines = add_links_to_page(index, later_file, earlier_file)
                    else:
                        i2lines = add_links_to_page(index, earlier_file, later_file)
                    #
                    with open(index_link, 'w') as file:
                        file.write('\n'.join(i2lines))
                else:
                    index_link = index
            else:
                index_link = index

            cruisename = os.path.join(*parts[:-2])

            cmd = 'du -sh %s' % (report_dir)
            proc=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()

            # every line needs one of these
            HP = HTML_page(cruisename, report_dir=report_dir)
            if len(stderr) == 0:
                size, rdir = stdout.strip().split()
                rtext='&nbsp &nbsp summary report &nbsp  &nbsp  &nbsp (%s) ' % (size)
            else:
                rtext=" summary data report"
            html_list.append(HP.newline + rtext + HP.space + HP.make_html_entry(index_link, cruisename)  )

    hstr = HP_.make_html_index(html_list, opts.title )
    with open('index.html', 'w') as file:
        file.write(hstr)

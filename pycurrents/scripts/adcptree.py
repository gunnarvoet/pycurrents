#!/usr/bin/env python

'''
   Python script for setting up an ADCP processing directory

   USAGE:
      python adcptree.py  processing_directory  [options]
                                   (1)            (2)


       (1) required

           processing_directory is the name of the processing directory.
           It can be a full path or a relative path.  Good choices are the
           cruise name (for averaged data) or the instrument name (for raw
           data)

       (2) options are:

          -d, --datatype      : choose what kind of data logging (and
                              : hence which kind of data files are being
                              : processed)
                              :
                              : name          what
                              : ----          ----
                              : "uhdas"        implies known directory
                              :                    structure for access
                              :                    to raw data
                              : "lta", "sta"   VmDAS averages
                              : "enx"          implies VmDAS single-ping
                              :                    data,time-corrected,
                              :                    navigated with attitude
                              :                              :
                              : "pingdata"     implies DAS2.48 (or 2.49) NB
                              :                    data, already averaged

                         ---------------------------------------------

             --cruisename     :   uhdas only (use --verbose for more info)
                              :         required; no default
             --configpath     :   uhdas only  (use --verbose for more info)
                              :         default = "config"
             ---cruisedirpath :   uhdas only, path to cruise directory
                              :         default = './'
          -h, --help          : print this help
          -v, --verbose       : print notes about uhdas logging
                              :            (see previous options)
          -V, --varvals       : print list of options and their values


  The directory holding adcp templates is assumed to be in
  pycurrents/adcp/templates, where pycurrents is installed.


USAGE:

UNIX:
 example: (for pingdata:)
    adcptree.py vg0304

 example (for LTA data:)
    adcptree.py vg0404   --datatype lta
    adcptree.py vg0404  -d lta

 example (for uhdas data:) NOTE: find the configuration files from your cruise!
         Creating these from the templates is really starting from scratch

    adcptree.py kok0517  -d uhdas --cruisename kok0517 --configpath /home/data/kok0517/raw/config

Windows:

 example: (for pingdata:)
    adcptree.py vg0304

 example (for LTA data:)
    adcptree.py vg0404    --datatype lta


'''

import os
import sys
import glob
import shutil
import getopt

import pycurrents

def get_template_path():
    ## this is the new location for adcp templates 2015/01/18
    pycurrents_dir = os.path.split(pycurrents.__file__)[0]
    template_dir = os.path.join(pycurrents_dir, 'adcp', 'templates')
    if not os.path.exists(template_dir):
        raise IOError('adcp templates directory %s not found' % (template_dir))
    print('found adcp templates at ', template_dir)
    return template_dir

def copyall(globstr, fromlist, tolist, forcecopy = 0, verbose=False):
    try:
        filelist = glob.glob(os.path.join(fromlist[0], fromlist[1], globstr))
        if verbose:
            print(filelist)
    except:
        raise IOError('failed to make filelist from ', fromlist, globstr)
    for filename in filelist:
        newfilebase = os.path.split(filename)[-1]
        if len(tolist) == 2:
            todir = os.path.join(tolist[0], tolist[1])
        else:
            todir = tolist[0]
        fullnewfile = os.path.normpath(os.path.join(todir, newfilebase))

        if os.path.exists(fullnewfile):
            print('file exists: not copying %s to %s' % (newfilebase, todir))
            return
        else:
            shutil.copy(filename, fullnewfile)

#---------------------------------

def check_opts(val, name, allowed):
    if val not in allowed:
        print(' ')
        print(__doc__)
        print('\n\n\nname <%s> is unacceptable.\n' % (val))
        print('choose one of the following:\n')
        print(allowed)
        sys.exit()

#---------------------------------

def varvals(opts):
    strlist = []
    keys = list(opts.keys())           ## need to do this in two lines:
    keys.sort()                  ## (1) get keys, (2) sort it

    for key in keys:
        s = '%s   %s' % (key.ljust(30), str(opts[key]))
        strlist.append(s)
    s = '\n\n'
    strlist.append(s)

    print(' ')
    print(('\n'.join(strlist)))

#----------------------------------

def usage():
    print(__doc__)

#---------------------------------

def populate(opts, otherdemo):
    demopath    = opts['demopath']
    procdir     = opts['procdir']
    #docpath     = opts['docpath']
    uh_progs    = None    # not used
    datatype    = opts['datatype']
    #instclass   = opts['instclass']
    verbose   = opts['verbose']

    print('\n\n** data type is %s' % (datatype))

    dirlist = (
       'adcpdb',
       'cal',
       'cal/watertrk',
       'cal/botmtrk',
       'cal/heading',
       'cal/rotate',
       'contour',
       'edit',
       'grid',
       'load',
       'nav',
       'quality',
       'ping',
       'scan',
       'stick',
       'vector')

    cfg_star = None  # for uhdas only

    ## make directory shell
    for dirname in dirlist:
        fulldir = os.path.join(procdir, dirname)
        if os.path.exists(fulldir):
            print('directory exists: cannot make %s' %(fulldir))
            sys.exit()
        else:
            os.makedirs(fulldir, 0o777)
            #print('making directory %s' %(fulldir))

    ## copy cnt files
    for dirname in dirlist:
        copyall('*.cnt', (demopath, dirname), (procdir, dirname))
    if verbose:
        print('copying control files')

    # get the codas db definition files
    if datatype in ('lta', 'sta'):
        print('- copying additional files for data type %s' % (datatype))
        copyall('vmadcp.def', (otherdemo, 'load'), (procdir, 'load'), verbose=verbose)

    elif (datatype == 'uhdas'):
        print('- copying additional files for data type %s\n' % (datatype))
        copyall('vmadcp.def',  (otherdemo, 'load'), (procdir, 'load'), verbose=verbose)

        proc_config_dir = os.path.join(procdir,'config')
        os.mkdir(proc_config_dir)
        print('- config files for raw processing are in %s' % (proc_config_dir))
        cfg_star = os.path.join(opts['configpath'], '%(cruisename)s*' % opts )
        for f in glob.glob(cfg_star):
            shutil.copy(f, proc_config_dir)

    elif (datatype == 'ping'):
        copyall('*.def', (demopath, 'adcpdb'), (procdir, 'adcpdb'), verbose=verbose)
        copyall('*.def', (demopath, 'scan'), (procdir, 'scan'), verbose=verbose)

    else:
        raise IOError("datatype %s not supported" %(datatype))

    if opts['varvals']:
        varvals(opts)
    return [procdir, uh_progs, cfg_star]

    # End populate()


def main():

    opts = {}

    ## parse arguments before options
    if len(sys.argv) == 1:
        usage()
        return

    # get the processing directory
    if sys.argv[1][0] == '-':
        usage()
        print('---------------------------------------------------------')
        print('must set processing directory name before using switches')
        return
    else:
        #
        opts['procdir'] =  sys.argv[1]
        startswitches = 2

    ###
    opts['templates'] = get_template_path()
    opts['demopath'] = os.path.join(opts['templates'], 'demo')
    opts['instclass'] = 'nb'
    opts['pingtype'] = 'nb'
    opts['datatype'] = 'pingdata'
    opts['cruisename'] = None
    opts['configpath'] = 'config'
    opts['help'] = False
    opts['verbose'] = False
    opts['varvals'] = False


    try:
        options, args = getopt.getopt(
            sys.argv[startswitches:], 'i:n:p:d:vVht',
            ['datatype=', 'help', 'verbose', 'varvals', 'cruisename=',
             'configpath=', 'cruisedirpath='])
    except getopt.GetoptError:  # Before Python 2.x this was getopt.error
        print(__doc__)
        raise

    ## old style, old script
    for o, a in options:
        if o in ('-h', '--help'):
            usage()
        elif o in ('-v', '--verbose'):
            opts['verbose'] = True
        elif o in ('-V', '--varvals'):
            opts['varvals'] = True
        elif o in ('-d', '--datatype'):
            opts['datatype'] = a
        elif o in ('--cruisename'):
            opts['cruisename'] = a
        elif o in ('--configpath'):
            opts['configpath'] = a
        elif o in ('--cruisedirpath'):
            opts['procdir'] = os.path.abspath(os.path.join(a, opts['procdir']))

    if opts['cruisename'] is None and opts['datatype'] == 'uhdas':
        raise ValueError("cruisename option is compulsory, not optional")

    ## check for reasonable match between instrument, pingtype and datatype
    check_opts(opts['datatype'], 'datatype',
               ('pingdata', 'ping', 'sta', 'lta', 'enr', 'ens', 'enx', 'uhdas'))
    if opts['datatype'] == 'pingdata':
        opts['datatype'] = 'ping'

    ### end verbose
    further_instructions = ''

    otherdemo = None

    if opts['datatype'] in ('lta', 'sta', 'enx', 'ens'):
        # set default
        otherdemo = os.path.join(opts['templates'], 'vmdas_template')
        if not os.path.isdir(otherdemo):
            print('adcptree.py: cannot access source directory %s' % (otherdemo))
            return

    # add some variables if we are not processing pingdata files
    if opts['datatype'] in ('uhdas',):  #treat these all like uhdas
        otherdemo = os.path.join(opts['templates'], 'uhdas_template')
        print('otherdemo is %s' % (otherdemo))
        if not os.path.isdir(otherdemo):
            print('adcptree.py: cannot access source directory %s' % (otherdemo))
            return

        #cruisename = os.path.join(opts['configpath'], opts['cruisename'])

        if opts['varvals']:
            varvals(opts)

    [fullprocdir, uh_progs, cfg_star] = populate(opts, otherdemo)

    if len(further_instructions) > 0:
        instfile = os.path.join(fullprocdir, '%s_instructions.txt' % (opts['datatype']))
        print('\nwriting instructions to %s\n' % (instfile))
        fid = open(instfile,'w')
        fid.write(further_instructions)
        fid.close()
        print(further_instructions)

    if opts['datatype'] == 'uhdas':
        if len(glob.glob(cfg_star)) == 0:
            print('WARNING: No configuration files found using wildcard', cfg_star)
        else:
            print('copying config files using this wildcard expansion:', cfg_star)



if __name__ == "__main__":
    main()

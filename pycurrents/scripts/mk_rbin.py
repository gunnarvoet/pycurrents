#!/usr/bin/env python


import os
import sys
import glob
import subprocess
from optparse import OptionParser

from pycurrents.adcp.adcp_specs import adcps

## this is too hardwired -- should be rewritten.
## consolidate output message names

usage = (
  "Start in the cruise directory, with subdirectories raw and rbin.\n"
  "Sweep through all (or specified) raw directories,\n"
  "making rbin files in the parallel 'rbin' directory\n"

  "usage: uhdas\n"
  "%prog -d uhdas_dir -i inst_dir -m msg -o outdir -y 2005 -t uh\n"
  "\n "
  "eg: %prog -d uhdas_dir -y 2005",'\n'
  "\n"
  "\n"
  " NOTE: If uhdas logging includes monotonic time stamp, it is type 'uh';\n"
  "       Otherwise it is 'olduh', and is called by serasc2bin.py.\n"
  )


parser = OptionParser('\n'.join(usage))
parser.add_option("-y",  "--yearbase", dest="yearbase",
                  help="yearbase (required)")
parser.add_option("-l",  "--log_yearbase", dest="log_yearbase",
                  help="log_yearbase for generation 1 polar data (usually 2003). only works with -t olduh")
parser.add_option("-d",  "--uhdas_dir", dest="uhdas_dir",
                  help="uhdas base directory, contains 'raw' and 'rbin'")
parser.add_option("-i", "--ser_inst", dest="ser_inst",
                  help="serial instrument, eg. 'ashtech', 'posmv'")
parser.add_option("-m",  "--message", dest="message",
                  help="message name, eg. 'gps' or 'pmv' for posmv")
parser.add_option("-t",  "--type", dest="loggertype",
                  help="logger type: 'uh', 'olduh', 'vmdas', 'rvdas'")
parser.add_option("-o",  "--outdir", dest="outdir",
                  help="output directory: default is parallel rbin directory")
parser.add_option("--test", dest="test",
                  action="store_true",  default= False)

(options, args) = parser.parse_args()

if options.uhdas_dir is None:
    parser.error('must specify uhdas directory')
if options.yearbase is None:
    parser.error('must specify yearbase')

if options.loggertype is None:
    loggertype = 'uh'
else:
    loggertype = options.loggertype

## fixed values
if loggertype == 'uh':
    parser = 'asc2bin.py '
    gunzip      = 0
    gzip        = 0
else:
    gunzip      = 1
    gzip        = 1
    if loggertype == 'olduh':
        parser  = 'serasc2bin.py -t olduh '
    elif loggertype == 'seruh':
        parser  = 'serasc2bin.py -t uh '
    else:
        parser =  'serasc2bin.py -t %s ' % (loggertype)

## possible ser_insts and binary messages (list)
path_ext ={}
path_ext['gyro']     =   ['hdg',]            # gyro heading
path_ext['gyro27']   =   ['hdg',]            # gyro heading
path_ext['gyro39']   =   ['hdg',]            # gyro heading

path_ext['ashtech']  =   ['adu', 'gps']      # [attitudes, positions] from adu
path_ext['abxtwo']   =   ['adu', 'gps']      # [attitudes, positions] from adu

path_ext['posmv']    =   ['pmv', 'gps']      # [attitude, positions]  from posmv
path_ext['posmv1']   =   ['pmv', 'gps']      # [attitude, positions]  from posmv
path_ext['posmv2']   =   ['pmv', 'gps']      # [attitude, positions]  from posmv
path_ext['seapath']  =   ['sea', 'gps']  # [attitude, position]   from seapath
path_ext['gpsnav']   =   ['gps',]            # positions from some gps sensor
path_ext['simrad']   =   ['gps',]            # positions from simrad
path_ext['sndspd']   =   ['spd',]            # sound speed sensor
path_ext['phins']    =   ['hdg', 'ixrp', 'ixgps', 'ixsspd', 'ixalg']
path_ext['tss']      =   ['hdg', 'hnc', 'hnc_tss1', 'hdg_tss1', 'tss']

## old directory name       ## new directory name
oldpath_key = {}
oldpath_key['adu2']     =   'ashtech'    # positions from adu
oldpath_key['pcode']    =   'gpsnav'    # positions from pcode


# variables from options
yearbase    = options.yearbase
log_yearbase = yearbase
if options.log_yearbase is not None:
    log_yearbase = options.log_yearbase
uhdas_dir   = options.uhdas_dir
ser_inst    = options.ser_inst
outdir      = options.outdir

if __name__ == '__main__':

    cruiseid = os.path.basename(uhdas_dir)
    rawdir = os.path.join(uhdas_dir,'raw')
    if outdir is None:
        outdir = os.path.join(uhdas_dir,'rbin')
    else:
        if not os.path.exists(outdir):
            print('cannot find specified output directory %s' % (outdir))
            print('directory must exist before this program will work')
            sys.exit()
    print('about to write rbin files to subdirectories of %s' % (outdir))


    inst_dirs = []
    if ser_inst is None:
        # find all possible
        testdirs = glob.glob(os.path.join(uhdas_dir,'raw','*'))
        for ii in range(0,len(testdirs)):
            testdir = os.path.basename(testdirs[ii])
            if testdir not in adcps and testdir in list(path_ext.keys()):
                inst_dirs.append(testdir)
                print('found instrument directory: %s' % (testdir))
            if testdir in list(oldpath_key.keys()):
                print('found OBSOLETE instrument directory name: %s' % (testdir))
                print('rename %s to %s before continuing\n' % \
                      (testdir, oldpath_key[testdir]))
                sys.exit()
    else:
        # use the one given, check first
        inst_dir = os.path.join(rawdir, ser_inst)
        if os.path.exists(inst_dir):
            inst_dirs = [os.path.basename(inst_dir),]
            print('found instrument directory: %s' % (inst_dir))
        else:
            print('cannot find specified instrument directory %s' % (ser_inst))

    for inst_dir in inst_dirs:
        testdir = os.path.join(outdir, inst_dir)
        if os.path.exists(testdir):
            print('not making %s' % (testdir))
        else:
            print('making %s' % (testdir))
            if not options.test:
                os.mkdir(testdir)

    ##
    for diri in range(0,len(inst_dirs)):
        inst_dir = inst_dirs[diri]
        full_instdir = os.path.join(rawdir, inst_dir)
        filelist = glob.glob(os.path.join(full_instdir, '*'))
        filelist.sort()

        outdir_inst = os.path.join(outdir, inst_dir)
        if os.path.exists(outdir_inst):
            print('not making directory ', outdir)
        else:
            print('making  directory %s' % (outdir_inst))
            if not options.test:
                os.mkdir(outdir)


        if gunzip == 1:
            ## gunzip first
            cmd = 'gunzip %s' %  (os.path.join(full_instdir,'*.gz'))
            print('about to run: %s' % (cmd))
            if not options.test:
                subprocess.run(cmd.split())


        if options.message is None:
            messages = path_ext[inst_dir]
        else:
            messages = [options.message,]

        for msg in messages:
            print('message is ', msg)
            if parser == 'asc2bin':
                cmd = '%s -r  -y %s -m %s  -o %s %s/*' % \
                      (parser, yearbase, msg, outdir_inst, full_instdir)
            else:
                cmd = '%s -r  -y %s -l %s -m %s  -o %s %s/*' % \
                      (parser, yearbase, log_yearbase, msg, outdir_inst, full_instdir)

            print('about to run: %s' % (cmd))
            if not options.test:
                subprocess.run(cmd.split())

        if gzip == 1:
            ## gzip after
            cmd = 'gzip %s' %  (os.path.join(full_instdir,'*'))
            print('about to run: %s' % (cmd))
            if not options.test:
                subprocess.run(cmd.split())

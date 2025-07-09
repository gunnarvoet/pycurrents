"""
# quick_adcp.py documentation:
#
# print_vardoc():

# print_pingdata_commands():

# print_ltapy_commands()
# print_enrpy_commands()
# print_uhdaspy_commands():
# print_postproc_commands():


# print_expert():          ## goodies and hints for experts

"""

def print_pingdata_commands():
    # this is from adcp_py3demos/txtfiles/pingdemo_help.txt

    str = '''

## processing pingdata

(1) make the processing tree

adcptree.py pingdemo -d pingdata

(2) copy (or link) the data into the "ping" directory

cd pingdemo/ping
cp ../../../../pingdata/ping_demo/ping* .
cd ..

(3) save a control file

    create a quick_adcp.py control file
    windows:
        - you can create q_py.cnt with an editor to have the
          parts between (or including) the comments
        - it may be easier to call it "q_py.txt" to avoid
          fighting with your editor, which may try to set the suffix


    unix: this example  is written as a bash "heredoc" for
          cut-and-past ease, but you can create q_py.cnt with
          an editor to have the parts between (or including)
          the comments

cat << EOF > q_py.cnt

    ### q_py.cnt is

    --yearbase 1993
    --cruisename ademo
    --sonar nb150
    --dbname aship
    --datatype pingdata
    --datafile_glob pingdata.*
    --beamangle 30
    #--ref_method smoothr ## this is the default, and the only thing allowed
    ## these must match what is in the dataset
    --ub_type 720   # 1920 is more common; 720 is pretty old
    --ens_len 300



EOF


(4) run quick:

quick_adcp.py --cntfile q_py.cnt --auto

(5) check calibrations:


   **watertrack**
------------
Number of edited points:  15 out of  17
   amp   = 1.0239  + 0.0178 (t -  98.8)
   phase =  -1.86  + -0.9926 (t -  98.8)
            median     mean      std
amplitude   1.0230   1.0239   0.0164
phase      -1.9640  -1.8647   0.9435
------------


   **bottomtrack**
------------
unedited: 31 points
edited:   23 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   1.0292   1.0313   0.0183
phase      -2.5117  -2.3619   0.9646

------------

Split the difference:

quick_adcp.py --steps2rerun rotate:calib:navsteps --rotate_angle -2.1 --rotate_amp 1.03 --auto



   **watertrack**
------------
Number of edited points:  15 out of  17
   amp   = 0.9940  + 0.0172 (t -  98.8)
   phase =   0.24  + -0.9924 (t -  98.8)
            median     mean      std
amplitude   0.9930   0.9940   0.0161
phase       0.1350   0.2367   0.9394
------------


   **bottomtrack**
------------
unedited: 31 points
edited:   23 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   0.9989   1.0013   0.0179
phase      -0.4306  -0.2666   0.9689

------------



... proceed to edit, make web plots and matlab (or netcdf) files

done with processing.
Add  cruise_info.txt to the top of this file.
Edit with correct info



'''

    print(str)


#--end  print_pingdata_commands---------------------------------------------

def print_postproc_commands():
    # this is from adcp_py3demos/txtfiles/km1001c_postproc_os38nb.txt


   str = '''

===========================================
Cruise km1001c processing:

The os38nb at-sea processing directory was copied from
the "proc" directory of the km1001c cruise disk.

All postprocessing is done with full codas+python (i.e. using
numpy+matplotlib)

All commands are run from "os38nb" unless otherwise noted.

(1) Make directory km1001c for post-procssing

- copy proc/os38nb directory from cruise disk

     (i) copy the os38nb directory to "os38nb_postproc"
     (ii) make another copy called "os38nb_postproc_orig" for later comparison

- start editing a text file called os38nb.txt, with the
	contents of os38nb/cruise_info.txt at the top.
- keep notes down below, and fill in above later
   Look at the cruise track to see what we're expecting.

	plot_nav.py nav/a_km.gps

   - This is a cruise with a "patch test" to calibrate the
 multibeam.  There should be ample watertrack calibration
 points from the patch test.

(2) check accurate heading device (POSMV):
- look at figures in cal/rotate *hcorr.png for gaps
  (gaps would be red "+" signs -- there are none)


	 figview.py cal/rotate/*png

conclude: no action needed


(3) check calibration:


      (a)  look at heading correction: are there gaps? does it need to be patched?
      (b)  look at watertrack and bottom track calibrations: what can we expect?



(a)run this command, then add part (or all) of the
   record displayed, to the documetation:

      tail -20  cal/watertrk/adcpcal.out



  **watertrack**

  Number of edited points:  32 out of  36
   amp   = 1.0080  + -0.0027 (t -  30.3)
   phase =  -0.01  + 0.0589 (t -  30.3)
	  median     mean      std
  amplitude   1.0060   1.0080   0.0085   <--- slight scale factor
  phase       0.0775  -0.0058   0.4343   <--- no phase adjustment
  -----------------

  ===> look at the watertrack figures:

  figview.py cal/watertrk/*png


 (b) cal/botmtrk/btcaluv.out  (no bottom track)


 - action: watertrack suggests a slight scale factor
    might be applied after editing

 - this is "close enough" to allow editing at this point


(4) view the data


  dataviewer.py


(5)

  - update the navigations steps and redo calibration -- get
  the directory in line with modern tools and metadata


  This will fail:

       quick_adcp.py --steps2rerun calib --auto

#
#  - NOTE: quick_adcp.py will complain about missing some information.
#    At each error, include the information in the quick_adcp.py
#      command line until it runs.
#
#      ERROR                          solution: add to commands
#
#
#   ERROR -- must select "datatype"      "--datatype uhdas"
#   ERROR -- must set "sonar"            "--sonar os38nb"
#   ERROR -- must set "yearbase"         "--yearbase 2010"
#   ERROR -- must set "ens_len"          "--ens_len 300"
#
#   Look in the file adcpdb/a_km.cnh to determine the number of
#   seconds used for the averaging.  We need the column "SI" for
#   "sampling interval"
#
#   ERROR -- must set "cruisename"       "--cruisename  km1001c"
#
#   For post-processing, the cruise name is just used for titles
#
#
#   ERROR -- must set "beamangle"        "--beamangle 30"
#
#   Usually, beamangles are:
#	       os38, os75, os150                   30
#              pn45                                20
#	       wh75, wh150, wh300, wh600, wh1200   20
#	       bb75, bb150, bb300                  30
#	       nb150, nb300                        30
#
#
#
#  - now try again
#



    quick_adcp.py --steps2rerun navsteps:calib --datatype uhdas --sonar os38nb --beamangle 30 --yearbase 2010 --ens_len 300 --cruisename km1001c --auto




Now make sure all the edits have been applied and look at the calibration

   cd ..
   quick_adcp.py --steps2rerun apply_edit:navsteps:calib  --auto
   tail -20 cal/watertrk/adcpcal.out


   **watertrack**
   ------------
   Number of edited points:  32 out of  35
  amp   = 1.0080  + -0.0027 (t -  30.3)
  phase =  -0.01  + 0.0589 (t -  30.3)
	      median     mean      std
  amplitude   1.0060   1.0080   0.0085
  phase       0.0775  -0.0058   0.4343
   ------------


(6) Edit out any bad points or profiles, or the data below the bottom using


     dataviewer.py -e




(7) Apply final calibration


   There are 32 points, enough for reasonable statistics

 # A phase correction is not warranted because the
 # mean and median are under 0.1 degree.  If the phase
 # values above had said X.YY, then we would include
 # this in the quick_adcp.py command:
 #
 #       --rotate_angle  X.YY
 #
 # But a scale factor ("amplitude") should be applied:

  quick_adcp.py --steps2rerun rotate:apply_edit:navsteps:calib --rotate_amplitude 1.007  --auto


   **watertrack**
------------
Number of edited points:  32 out of  36
   amp   = 1.0011  + -0.0028 (t -  30.3)
   phase =  -0.01  + 0.0589 (t -  30.3)
            median     mean      std
amplitude   0.9990   1.0011   0.0084
phase       0.0810  -0.0081   0.4342
------------



   Looks good



Look at the figures too

 figview.py  cal/watertrk/wtcal1.png



(6) make web plots

      quick_web.py --interactive

- view with a browser, look at webpy/index.html


(7) extract data

  quick_adcp.py --steps2rerun matfiles --auto
  quick_adcp.py --steps2rerun netcdf --shipname "Kilo Moana" --auto

# or   adcp_nc.py adcpdb  contour/os38nb  km1001c_demo os38nb --ship_name Kilo Moana

Submit to JASADCP (Joint Archive for Shipboard ADCP)
      http://ilikai.soest.hawaii.edu/sadcp/


'''
   print(str)


def print_ltapy_commands():
    # this is from adcp_py3demos/txtfiles/ps0918_LTA_postproc.txt

    str = '''

(manual loading of LTA data into CODAS database, followed by postprocessing)

=======================================================
(1) find out information about the data


    starting in ps0918_ltaproc, run this command:

         vmdas_info.py --logfile lta_info.txt os ../../vmdas_data/ps0918/*LTA



The output says:

      - 3 files, all have data
      - averaging length: 300sec
      - instrument frequency 75
      - pingtypes: bb pings
      - bottom track was on for part of the cruise
      - beam angle 30 (normal for OS75)
      - transducer angle (EA) 1.18
      - messages available and what was used:

      N1R      HEHDT           <-- VmDAS primary heading

      N2R      GPGGA
      N2R      GPHDT
      N2R      PASHR,AT2       <-- VmDAS backup heading
      N2R      PASHR,ATT
      N2R      PASHR,POS

      N3R      GPGGA           <-- VmDAS primary position
      N3R      GPGLL


(2) set up processing directory:

     adcptree.py os75bb_manual_lta --datatype lta



(3) Look at vmdas_info.py again and note:
    - what kind of pings
    - averaging length
    - are filenames sorted in chronological order?
    - what was the heading source?


Start a text file "os75bb_lta.txt" adjacent to the processing directory,
"os75bb_lta" and put this information in it:

       --> these are 'bb' pings
       --> averaged over 300sec
       --> frequency is 75kHz, so "sonar" os "os75bb"
       --> primary heading was HEHDT
       --> there is an Ashtech, used as secondary heading


(4) Change directories to ADCP processing directory just created.
    All the rest of the work (except for editing the text file)
    will be done in this directory


    cd  os75bb_manual_lta


(5) create a quick_adcp.py control file

 create a quick_adcp.py control file

    windows:
        - you can create q_py.cnt with an editor to have the
          parts between (or including) the comments
        - it may be easier to call it "q_py.txt" to avoid
          fighting with your editor, which may try to set the suffix

    unix: this example  is written as a bash "heredoc" for
          cut-and-past ease, but you can create q_py.cnt with
          an editor to have the parts between (or including)
          the comments


cat << EOF > q_py.cnt

    ##### q_py.cnt is


     ### python processing

    --yearbase 2009             ## required, for decimal day conversion
                                ##     (year of first data)
    --cruisename ps0918         ## always required; used for titles
    --dbname aship              ## database name; in adcpdb.  eg. a0918
    --datatype lta              ## datafile type
    --sonar os75bb              ## instrument letters, frequency, [ping]
    --ens_len  300              ## specify correct ensemble length
    --pgmin 30

    --datadir ../../../vmdas_data/ps0918  ##use this option to avoid
                                ## copying or linking files

    #### end of q_py.cnt

EOF



(6) run quick_adcp.py:

   quick_adcp.py --cntfile q_py.cnt --auto



(7) Check calibrations

   **watertrack**
------------
Number of edited points:   2 out of   2
   amp   = 1.0040  + 0.1053 (t - 264.8)
   phase =   1.42  + 15.5789 (t - 264.8)
            median     mean      std
amplitude   1.0040   1.0040   0.0085
phase       1.4200   1.4200   1.2558
------------

codaspy:(os75bb_LTA.calibrated)-PY3$ catbt


   **bottomtrack**
------------
unedited: 36 points
edited:   33 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   0.9998   0.9998   0.0025
phase       1.3538   1.5970   0.5428

------------


(8)  apply rotation correction (no scale factor necessary)
     (all in one line)


     quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_angle 1.5  --auto


   **bottomtrack**
------------
unedited: 37 points
edited:   33 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   0.9995   0.9998   0.0026
phase      -0.1377   0.0900   0.5427

------------


 - this is "close enough" to allow editing at this point


(9)  edit bad data

   cd edit
   gautoedit.py

 # apply editing:

   cd ..
   quick_adcp.py --steps2rerun apply_edit:navsteps:calib  --auto


(10) make web plots

       quick_web.py --interactive

 - view with a browser, look at webpy/index.html

(11) extract data

   quick_adcp.py --steps2rerun matfiles --auto
   quick_adcp.py --steps2rerun netcdf --shipname "Point Sur" --auto

#    adcp_nc.py adcpdb  contour/os75bb  ps0918_demo os75bb



done with processing.
Add  cruise_info.txt to the top of this file.
Edit with correct info




'''
    print(str)



def print_enrpy_commands():
    # this is from adcp_pyproc/txtfiles/ps0918_enrproc_os75bb.txt

    str = '''

This 'help' refers to the adcp_py3demos  ps0918 cruise.
(manual steps to process ENR data, via uhdas-style directory)

=======================================================
(1) find out information about the data

Make a **project** directory (ps0918_vmdas)
From here:

        vmdas_info.py --logfile lta_manual_info.txt  os ../../vmdas_data/ps0918/*LTA
        vmdas_info.py --logfile enr_manual_info.txt  os ../../vmdas_data/ps0918/*ENR



The output says:

      - 3 files, all have data
      - averaging length: 300sec
      - instrument frequency 75
      - pingtypes: bb pings
      - bottom track was on for part of the cruise
      - beam angle 30 (normal for OS75)
      - transducer angle (EA) 1.18
      - messages available and what was used:

      N1R      HEHDT           <-- VmDAS primary heading

      N2R      GPGGA
      N2R      GPHDT
      N2R      PASHR,AT2       <-- VmDAS backup heading
      N2R      PASHR,ATT
      N2R      PASHR,POS

      N3R      GPGGA           <-- VmDAS primary position
      N3R      GPGLL


Look at the info files and note:
    - what kind of pings
    - averaging length
    - are filenames sorted in chronological order?
    - what was the heading source?


(2)  Start a text file "os75bb_ENR_manualproc.txt" adjacent to the processing directory,
     "os75bb_lta" and put this information in it:

       --> these are 'bb' pings
       --> averaged over 300sec
       --> frequency is 75kHz, so "sonar" os "os75bb"
       --> primary heading was HEHDT
       --> there is an Ashtech, used as secondary heading


(3) convert vmdas data to uhdas-style data

    mkdir config
    reform_vmdas.py --project_dir_path ./ --vmdas_dir_path ../../vmdas_data/ps0918 --uhdas_style_dir ../../uhdas_style_data  --cruisename ps0918_manual --start ..
    cd  config
    python3 vmdas2uhdas.py

(4) create the processing configuration file

   proc_starter.py reform_defs.py

   cd ..

(5a) set up processing directory:

     adcptree.py os75bb_manual --datatype uhdas --cruisename ps0918_manual
     cd os75bb_manual
     # make q_py.cnt

(5b) create a quick_adcp.py control file

 create a quick_adcp.py control file

    windows:
        - you can create q_py.cnt with an editor to have the
          parts between (or including) the comments
        - it may be easier to call it "q_py.txt" to avoid
          fighting with your editor, which may try to set the suffix

    unix: this example  is written as a bash "heredoc" for
          cut-and-past ease, but you can create q_py.cnt with
          an editor to have the parts between (or including)
          the comments


cat << EOF > q_py.cnt

    ##### q_py.cnt is

    --yearbase 2009             ## required, for decimal day conversion
                                ##     (year of first data)
    --cruisename ps0918_manual  ## *must* match prefix in config dir
    --dbname aship              ## database name; in adcpdb.  eg. a0918
                                ##
    --datatype uhdas            ## datafile type
    --sonar os75bb              ## specify instrument letters, frequency,
                                ##     (and ping type for ocean surveyors)
    --ens_len  300              ## averages of 300sec duration
                                ##
    --update_gbin               ## required for this kind of processing
    --configtype  python        ## file used in config/ dirctory is python
                                ##
    --ping_headcorr             ## ps0918_manual_proc.py says use HDT first,
                                ##    correct to ashtech
    --max_search_depth 1500     ## try to identify the bottom and eliminate
                                ##    data below the bottom IF topo says
                                ##    the bottom is shallower than 1000m

    #### end of q_py.cnt

EOF


(6) run quick_adcp.py:

   quick_adcp.py --cntfile q_py.cnt --auto



(7) Check calibrations

   **watertrack**
------------
Number of edited points:   2 out of   2
   amp   = 1.0030  + 0.1228 (t - 264.8)
   phase =  -0.01  + 3.2807 (t - 264.8)
            median     mean      std
amplitude   1.0030   1.0030   0.0099
phase      -0.0150  -0.0150   0.2645
------------


   **bottomtrack**
------------
unedited: 21 points
edited:   18 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   0.9996   1.0004   0.0044
phase       0.3090   0.3392   0.1713

------------


(8)  apply rotation correction (no scale factor necessary)
     (all in one line)


     quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_angle 0.32  --auto



   **bottomtrack**
------------
unedited: 20 points
edited:   16 points, 2.0 min speed, 2.5 max dev
            median     mean      std
amplitude   1.0002   1.0000   0.0024
phase      -0.0380  -0.0183   0.1113

------------


(9)  edit bad data

   dataviewer.py -e


 # apply editing:


   quick_adcp.py --steps2rerun apply_edit:navsteps:calib  --auto


(10) make web plots

       quick_web.py --interactive

 - view with a browser, look at webpy/index.html

(11) extract data

   quick_adcp.py --steps2rerun matfiles --auto
   quick_adcp.py --steps2rerun netcdf --shipname "Point Sur" --auto

#    adcp_nc.py adcpdb  contour/os75bb  ps0918_demo os75bb --ship_name Point Sur



done with processing.
Add  cruise_info.txt to the top of this file.
Edit with correct info


'''


    print(str)

#----- print_uhdaspy_commands -----------------------------------------------

def print_uhdaspy_commands():
    # this comes adcp_sphinxdoc/txtfiles/km1001c_fullproc_os38nb.txt

    str = '''



Process UHDAS data using Python
=============================================

(1)  directory setup: create a working directory for this cruise

      mkdir  km1001c_fullproc
      cd km1001c_fullproc



(1a) get some information about this cruise:

     uhdas_info.py --logfile uhdas_info.txt ../../uhdas_data/km1001c
     cat uhdas_info.txt


     We see:
     - positions from ashtech and posmv
     - headings from gyro, posmv and ashtech
     - 138 files; all present


(1b) configuration file for processing:


In order to use CODAS Python processing, we need to generate a
suitable configuration file, containing instructions for processing
such as transducer depth, transducer angle and ancillary data sources
(heading and attitude). This new file contains modern settings and
modern syntax for the specified ship: create a new
file, with modern syntax and variable names, and then edit as needed.


# In  km1001c_fullproc make a directory called 'config'


         mkdir config
         cd config

# and run:

         uhdas_proc_gen.py -s km

    # This creates a file called "km_proc.py"

    # copy to a new version for our cruise  (use the cruisename "km1001c"):

    cp km_proc.py km1001c_proc.py

   #Edit the file and add these four (4)
   # lines to the top of km1001c_proc.py


# full path to uhdas data directory (do not use relative path)
uhdas_dir = '/home/currents/programs/adcp_py3demos/uhdas_data/km1001c'
yearbase = 2010                  # usually year of first data logged
shipname = 'Kilo Moana' # for documentation
cruiseid = 'km1001c'              # for titles



    # go back one level
    cd ..


(2) now we can use that file.
    Set up the processing directory by typing:


      adcptree.py  os38nb --datatype uhdas --cruisename km1001c


NOTE: Now there is no error message about missing configuration files

(3) (a) change directories to ADCP processing directory just created

         cd  os38nb

    NOTE: there is a "config" directory and it has a copy of the file
          km1001c_proc.py that we created in #2

    (b)  create a quick_adcp.py control file

    unix: this example  is written as a bash "heredoc" for
          cut-and-past ease, but you can create q_py.cnt with
          an editor to have the parts between (or including)
          the comments

    windows:
        - you can create q_py.cnt with an editor to have the
          parts between (or including) the comments
        - it may be easier to call it "q_py.txt" to avoid
          fighting with your editor, which may try to set the suffix


cat << EOF > q_py.cnt

    ####----- begin q_py.cnt------------
    ## all lines after the first "#" sign are ignored

    ## python processing

      --yearbase    2010
      --cruisename  km1001c   # used to identify configuration files
                              #  *must* match prefix of files in config dir

      --update_gbin   ## NOTE: You should generally remake gbins
                      ## - you are not sure
                      ## - if parameters for averaging changed
                      ## - various other reasons.

                      ## ==> MAKE SURE you move the original gbin directory
                      ##     to another name first!!

#      --py_gbindirbase gbin # (will put them adjacent to q_py.cnt)

      --configtype python  ## <=== USE THE NEW FILE WE CREATED

      --sonar       os38nb
      --dbname      aship
      --datatype    uhdas
      --ens_len     300

      --ping_headcorr        ## applies heading correction.
                             ##     settings found in config files

      --max_search_depth 3000   ## use  topography for editing?
                                ## 0 = "always use amplitude to guess the bottom;
                                ##          flag data below the bottom as bad
                                ## -1 = "never search for the bottom"
                                ## positive integer: use ADCP amp to autodetect
                                ##    the bottom.  Only do this in "deep water",
                                ##    i.e. topo says bottom is deeper than this

EOF


   (c)  run quick_adcp.py:

        quick_adcp.py --cntfile q_py.cnt

---------

(4) review the data

    (a) check calibration:heading correction device:

             figview.py cal/rotate/*png

              conclude: no action needed


    (b) check calibration:

      **watertrack**
   ------------
   Number of edited points:  34 out of  35
      amp   = 1.0074  + -0.0033 (t -  30.3)
      phase =   0.05  + 0.1635 (t -  30.3)
               median     mean      std
   amplitude   1.0080   1.0074   0.0064
   phase       0.0900   0.0511   0.4541

   -------------------


   (c) look at the data:

              dataviewer.py



(5)  edit "gautoedit"

    cd edit
    gautoedit.py


    # apply editing:


      cd ..
      quick_adcp.py --steps2rerun apply_edit:navsteps:calib  --auto

    # check editing -- looks OK

          dataviewer.py

(6)

    - check calibrations again


    **watertrack**
------------
Number of edited points:  34 out of  35
   amp   = 1.0071  + -0.0020 (t -  30.3)
   phase =   0.05  + 0.1809 (t -  30.3)
            median     mean      std
amplitude   1.0080   1.0071   0.0058
phase       0.0900   0.0494   0.4431
------------


   still need scale factor:


    quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_amplitude 1.007 --auto


    **watertrack**
------------
Number of edited points:  34 out of  35
   amp   = 1.0001  + -0.0018 (t -  30.3)
   phase =   0.05  + 0.1840 (t -  30.3)
            median     mean      std
amplitude   1.0010   1.0001   0.0058
phase       0.0935   0.0496   0.4439
------------




   phase correction is very small:


       quick_adcp.py --steps2rerun rotate:navsteps:calib --rotate_angle 0.06 --auto


    **watertrack**
------------
Number of edited points:  34 out of  35
   amp   = 1.0001  + -0.0018 (t -  30.3)
   phase =  -0.01  + 0.1828 (t -  30.3)
            median     mean      std
amplitude   1.0010   1.0001   0.0057
phase       0.0365  -0.0095   0.4437
------------

OK, done

(7)

make plots:



    quick_web.py --interactive

    - or, to use the same sections as were used in the postprocessing demo

      mkdir webpy
      cp ../../km1001c_postproc/os38nb/webpy/sectinfo.txt webpy
      quick_web.py --redo

    - view with a browser, look at webpy/index.html



(8) extract data


    quick_adcp.py --steps2rerun matfiles --auto
    quick_adcp.py --steps2rerun netcdf --shipname "Kilo Moana" --auto

#    adcp_nc.py adcpdb  contour/os38nb  km1001c_demo os38nb



----


done with processing.
Add  os38nb/cruise_info.txt to the top of this file.
Edit with correct info


'''


    print(str)


#----- print_expert -----------------------------------------------


def print_expert():

    str = '''


--dday_bailout       :  bail out at this time (good for testing); must
                     :            use with --incremental to add more data


#-------------- for uhdas processing --------
--max_search_depth   :  use  topography for editing?
                     :  0 = "always use amplitude to guess the bottom;
                     :           flag data below the bottom as bad
                     :  -1 = "never search for the bottom"
                     :  positive integer: use ADCP amp to autodetect
                     :     the bottom.  Only do this in "deep water",
                     :     i.e. topo says bottom is deeper than this
                     : This impacts single-ping editing

--incremental        :  for uhdas incremental mode; only generates the last
                     :        few figures; can be used after --dday_bailout
                     :        to step through the dataset

--pingpref           : (only activated with these choices for --sonar:
                     :    os150, os75, os38 (i.e. without the pingtype specified)
                     :   - used to choose default ping type if interleaved
                     :   - otherwise it uses whatever is there
                     :   (whereas eg. os75bb would only use bb pings)

--py_gbindirbase     :  gbin root, defaults to uhdas_dir/gbin for python

                              #------------
xducer_dx, xducer_dy :  The next two variables use the offset
                     :  between transducer and gps to "realign"
                     :  the positions closer to the adcp.
                     :  SINGLEPING processing: translated positions are
                     :  if 0
                     :       in load/*.gps2 --> (catnav) --> nav/*.gps
                     :  if dx!=0 or dy!=0
                     :       in load/*.gpst2 --> (catnav) --> nav/*.agt

                     :  POSTPROCESSING: run with "--steps2rerun"
                     :      and specify "navsteps:calib"
                     :      translates fixfile (.gps or .ags)
                     :      to txy_file .agt

                     : THESE ARE ADDITIVE (add to dbinfo, recaclulate)
#defaults:
--xducer_dx 0        :  positive starboard distance from GPS to ADCP
--xducer_dy 0        :  positive forward distance from GPS to ADCP


## new experimental output of ascii files with reference layer values
## for each ping (load/*uvwref.txt) containing [dday, u, v, w]
## Defaults:
--uvwref_start None  # if integer, this is the start of the slice into bins
--uvwref_end   None  # if integer, this is the end of the slice into bins

## these two combine in RefSmooth to create tuv.asc for "put_tuv"

--refuv_source 'nav' :   default = ship velocities from fixfile
                     :   otherwise EXPERIMENTAL:
                     :       specify 'uvship' to use
                     :       ship speeds from "*.uvship" file,
                     :       (- averaged from only those pings used)
                     :       (- only exists for recent software)
                     :            ==> was "use_uvship" <==

--refuv_smoothwin 3  :   default blackman filter half-width = 3
                     :       (use 3 ensembles on each side for
                     :       reference-layer smoothing
                     :   0: no smoothing
                     :   1: "just use this one point" (no smoothing)
                     :   2: less smoothing
                     :   3: default
                     :   (goes into Refsm as bl_half_width)

--gbin_gap_sec  15   : if the instrument is triggered, gaps may
                     : occur in ping times.  It is dangerous to
                     : make this too big.  usually it should be
                     : 3-7 sec, depending on frequency.  Shoot
                     : for 100-300 pings in your averages
 '''

    print(str)


#----end print_expert -----------------------------------------------------



def print_vardoc():
    # update this from the comments in quick_adcp.py

    str = '''
 - - - - - - - - - - - - - - - - - - - - - - - - - - - -- - - - - - - - - - -

 These are relevant to any codas processing of shipboard ADCP data


 Options are specified on the command line or in a file.  (see below)

    help           = False       # print help

    varvals        = False       # print values about to be used, then exit
                                 #   eg. quick_adcp.py --cntfile q_py.cnt --varvals
    vardoc         = False       # detailed use for each variable
    commands       = None        # print specific help

#                        === directories and files ===
#
#     variable         default   # description
#     -------         ---------- # -----------------
#


#---- required -----



    datatype         = None
                                 # choose what kind of data logging (and
                                 #   hence which kind of data files
                                 #   are being processed)
                                 #
                                 # default is "pingdata"
                                 #
                                 #  name          what
                                 #  ----          ----
                                 #  "pingdata"     implies DAS2.48 (or 2.49) NB
                                 #
                                 #  "uhdas"        implies known directory
                                 #                     structure for access
                                 #                     to raw data
                                 #  "lta", "sta"   VmDAS averages
                                 #

    sonar              = None    # eg. nb150, wh300, os75bb, os38nb

    yearbase           = None    # 4 digits (acquisition year)

    ens_len            = None    # seconds in an ensemble; default set in dbinfo

    cruisename         = None    # used for plot titles; required
                                 # cruise name is the same as procdir name
# required in post-processing;

    beamangle         = None     # degrees (integer).

                                 # Reference layer smoothing:
                                 # three possibilities:
                                 # (1) bin-based reference layer; "smoothr"
                                 # (2) refavg decomposition (timeseries,
                                 #       baroclinic, minimize error) "refsm"
                                 # (3) use_uvship: use average of ship speeds from
                                 #       good profiles only. limitations:
                                 #       - uhdas single-ping processing only
                                 #       - must be set at the time of averaging

    dbname           = None      #  traditionally
                                 #   - start with "a"
                                 #   - then append  4 characters
                                 # defined as the 'XXX' in 'adcpdb/XXXdir.blk'


##  ---- end of required parameters ---

    cntfile            = None    # override defaults with values from this
                                 #   control file.  Format is the same as
                                 #   command line options, but whitespace is
                                 #   unimportant.  Do not quote wildcard
                                 #   characters in the cnt file (whereas
                                 #   you would for the command line)
                                 # Defaults are overridden by this cntfile
                                 # Commandline options can override either.

# additional parameters ---


    datadir         = None       # data path. defaults are:
                                 #     (1) relative to scan or load directory
                                 #     (2) full path
                                 #  ../ping       (for LTA, ENS, pingdata)
                                 #
                                 # for NON-UHDAS processing only.
                                 # use "sonar" and cruise_cfg.m for UHDAS


    datafile_glob         = None #look for sequential data files.
                                 # (not for UHDAS data)
                                 #    defaults are:
                                 #  pingdata.???  (for pingdata)
                                 #  *.LTA         (for LTA files)
                                 #  *.ENS         (for ENS files)



   data_filelist        = None   # use data file paths in this text file


    pingpref                     # (only activated with these choices for --sonar:
                                 #    os150, os75, os38 (i.e. without the pingtype specified)
                                 #   - used to choose default ping type if interleaved
                                 #   - otherwise it uses whatever is there
                                 #   (whereas eg. os75bb would only use bb pings)

#-----
                                 # Reference layer smoothing:
                                 # two possibilities:
                                 # (1) old:  "smoothr"
                                 #     - bin-based reference layer;
                                 #     - simple averaging
                                 # (2) default: "refsm"
                                 #     - refavg decomposition
                                 #     - calculates timeseries+baroclinic,
                                 #     - minimize error "refsm"
                                 #
                                 #     additionally, supports:
                                 #     - navigation from 'gps' or from
                                 #       translated positions, based on
                                 #       transducer offset from ADCP
                                 #     - ship speed from
                                 #         - 'nav' (traditional calculation
                                 #            of ship speed (from first
                                 #            difference of positions from
                                 #             ensemble end-times)
                                 #         - 'uvship' (new, EXPERIMENTAL)
                                 #            average of ship speeds from
                                 #            pings used, calculted during
                                 #            single-ping processing


    # these two are set in quick_setup.py (check_ref_method)
    ref_method = 'refsm'         ##  Default: use "refsm" for reference layer
                                 #       - positions inputted with "put_txy"
                                 #       - ship speeds inputted with "put_tuv"
                                 ##  other choice: use "smoothr" for reference layer
                                 #       - ship speed and position inputted with "putnav"
                                 #   Plots are done with smoothr, regardless


       ## these two combine in RefSmooth to create tuv.asc for "put_tuv"
    refuv_source = 'nav'         # default = uvship from position file
                                 # otherwise EXPERIMENTAL:
                                 #     specify 'uvship' to use
                                 #     ship speeds from "uvship", i.e.
                                 #     averaged from only those pings used
    refuv_smoothwin = 3          # default blackman filter half-width = 3
                                 #     (use 2*N-1  ensembles on each side for
                                 #            reference-layer smoothing
                                 # (goes into Refsm as bl_half_width)
                                 # 0: no smoothing
                                 # 1: just use one point (same as "no smoothing")
                                 # 2: (less smoothing)

                                 #------------
     # xducer_dx, xducer_dy      # The next two variables use the offset
                                 # between transducer and gps to "realign"
                                 # the positions closer to the adcp.
                                 # POSTPROCESSING: run with "--steps2rerun"
                                 #     and specify "navsteps:calib"
                                 #     new fix file is dbname.agt
                                 # SINGLE-PING PYTHON PROCESSING: creates
                                 #     .gps2 and .gpst2 files in load,
                                 #     and cats to .gpst2 to dbname.gpst
                                 #     for the fix file
                                 #
    xducer_dx         = 0        # positive starboard distance from GPS to ADCP
                                 # This option is usually not necessary
                                 #
    xducer_dy         = 0        # positive forward distance from GPS to ADCP
                                 # This option is usually not necessary


    fixfile = None               # override the default fix file. defaults are:
                                 # if datatype is pingdata, default is
                                 # [dbname].ags (for pingdata)
                                 # [dbname].gps (for LTA, ENS, or uhraw)
                                 # fixfile is used as input to
                                 #       - smoothr
                                 #       - xducer_dx, xducer_dy



########

    ub_type          = '1920'    # For NB DAS only: User buffer type:
                                 # 720 for demo; 1920 for recent cruises



#
#           === processing options ===
#
#    variable         default     # description
#    -------       ----------     -----------------

    rotate_amplitude = 1         # run "rotate" on the entire database with
                                 #     amplitude (scale factor) = 1.0
    rotate_angle = 0             # run "rotate" on the entire database with
                                 #   this angle (phase), usially a tweak from
                                 #   bottom track or watertrack calibration

    rl_startbin = 2              # first bin for reference layer: 1-nbins
    rl_endbin = 20               # last bin for reference layer : 1-nbins

    pgmin = 50                   # only accept PG greater than this value
                                 # --> don't go below 30 <--
                                 # default is 50 for pre-averaged datatypes
                                 #      ('pingdata', 'lta', and 'sta')
                                 # default is 20 for single-ping datatypes
                                 #   ('uhdas', 'enr', 'ens', 'enx')


    slc_bincutoff = 0            # default=disabled (0).  Apply a shallow low
                                 # correlation cutoff only above this bin (1-nbins)

    slc_deficit = 0              #  default=disabled (0). Flag bins shallower than
                                 # slc_bincutoff with correlation less
                                 # than (max - slc_deficit)


    find_pflags = False          #  automatically find profile flags
                                 #  apply editing (dbupdate, etc)
                                 #  You should be familiar with gautoedit
                                 #      before using this...



   #          === REPROCESSING options ===
   #
   #
   #   variable         default     # description
   #   -------       ----------     -----------------

    steps2rerun         = ''     # colon-separated list of the following:
                                 # 'rotate:apply_edit:navsteps:calib:matfiles:netcdf'
                                 # designed for batch mode; assumes codasdb
                                 #  already in place, operates on entire
                                 #  database.
                                 #
                                 # 'rotate' is:
                                 #   apply amplitude and phase corrections
                                 #   using these (if specified):
                                 #      rotate_angle (contstant angle)
                                 #      rotate_amplitude (scale factor)
                                 # Apply time-dependent correction manually
                                 #
                                 # 'navsteps' is:
                                 #   [adcpsect+refabs+smoothr+refplots]
                                 #   and reference layer smoothing by
                                 #   refsm (default; uses put_txy, put_tuv)
                                 #   or smoothr (uses putnav)
                                 #
                                 # 'apply_edit' is:
                                 #   badbin, dbupdate, set_lgb, setflags
                                 #
                                 # 'calib' is:
                                 #   botmtrk (refabsbt, btcaluv)
                                 #   watertrk (adcpsect, timslip, adcpcal)
                                 #
                                 # 'matfiles' is:
                                 #   adcpsect for vector and contour
                                 #   Always use  "sonar" for defaults
                                 #   (specify top_plotbin for better results
                                 #    IF you have codas python extensions)
                                 #   or use "firstdepth" to tweak top values
                                 #
                                 # 'netcdf' is:
                                 #   run adcp_nc.py to extract short form netcdf
                                 #
                                 # 'write_report' is:
                                 #    write a summary of cruise metadata
                                 #   - lands in "cruise_info.txt"
                                 #    ONLY use this option to generate a cruise
                                 #    report for a cruise without one; check for
                                 #    "cruise_info.txt" before running in this mode

###  === Data extraction options ===


    numbins  = 128               # max number of bins to extract for editing

    firstdepth  = None           # depth of shallowest bin for adcpsect extraction

## === specialized processing options  ===

    auto  = False                # 1: whiz along (do not prompt); do all
                                 #    requested steps (default is all step)
                                 #    0 to prompt at each step


      ############## for UHDAS  processing only ####################
      #                 batch or incremental                       #


    proc_engine = 'python'       # default -- no choice
                                 # "python" : requires matplotlib;
                                 #            matlab is not used

    cfgpath = 'config'           # UHDAS only
                                 # Find cfg files (*_cfg.m, *_proc.m) here.
                                 # NOTE: path should be absolute or can be
                                 #   relative root processing directory
                                 #   (if relative, rendered absolute
                                 #   before being used, to remove ambiguity)
                                 # NOTE: cruisename is the prefix for these files
    configtype = 'python'        # default (no choice) 'python' python processing


    badbeam  = None              # badbeam for 3-beam data (beam=1,2,3,4)

    beam_order = None            # if remapping is needed, colon-delimited list
                                 # eg) 1:2:4:3    (RDI beam numbers)

    max_search_depth  = 0        # use predicted topography as follows:
                                 # 0 = always use amp to identify the bottom
                                 #     and remove velocities below the bottom
                                 # -1 = never look for the bottom using amplitude
                                 #      therefore never edit data below the 'bottom'
                                 # positive integer:
                                 #  - if predicted topo is deeper than this
                                 #     depth, then we are in deep water and do
                                 #     not expect to find the bottom. Therefore
                                 #     DO NOT try and identify the bottom
                                 #         (eg. do not idenfity strong
                                 #         scattering layers in deep water)
                                 #  - impacts weak-profile editing
                                 #  - used to be "use_topo4edit" with a search
                                 #     depth of 1000


    max_BLKprofiles= 300         # max number of profiles per block.  Might
                                 #  want to make smaller to test incremental
                                 #  processing (must be 512 or less)

    update_gbin  = False         # UHDAS; update gbin files


    py_gbindirbase  = None       # defaults to uhdas_dir/gbin for python IO

    gbin_gap_sec = 15            # if the instrument is triggered, gaps may
                                 # occur in ping times.  It is dangerous to
                                 # make this too big.  usually it should be
                                 # 3-7 sec, depending on frequency.  Shoot
                                 # for 100-300 pings in your averegs

      ############## for UHDAS  processing only, incremental ##################


    dday_bailout  = None         # may be useful for testing (UHDAS only)
                                 #   (bail out of averaging at this time)


    ping_headcorr = False        # UHDAS only.  apply heading corrections on-the-fly


                                 # installation for other backends

    top_plotbin  = None          # shallowest bin to use for data extraction
                                 # bins are 1,2,3,...
                                 # --> overrides 'firstdepth' if both ar chosen
                                 # --> requires codas python extensions
                                                                  #
 '''
    print(str)


#-------------- end print_vardoc ------------------------------------------

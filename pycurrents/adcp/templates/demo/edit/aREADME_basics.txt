                 Gui interface for ADCP autoedit package

           ====================================================
                  "gautoedit", pronounced "gee! autoedit"
           ====================================================



See "autoedit.html" for a better description of the editing process.

---------
Jules Hummon; Dec 2000 (called aREADME.verbose)
              May 2002, consolidating and clarifying, written for refsm ref 
              layer; tailored for "demo"

gautoedit requires Matlab 5.3 or higher
quick_adcp.prl requires perl 4.0 or higher

aREADME_basics.txt contents:
(I)    Introduction                            
(II)   Directions (easy start)        
(III) description of some useful autoedit programs

=======================================================================
=========================== (I) Introduction ==========================
=======================================================================

This document describes two new programs in the CODAS3 suite of
processing code, "gautoedit" and "quick_adcp.prl".  I will describe
their use in the context of the "demo" cruise, which is already
well-documented (see "process.txt").

*** New editing: "gautoedit" (a matlab gui tool for editing ADCP data
                              in a CODAS database)

This editing package arose from a need to apply some new editing
parameters to a large number of cruises, many of which contained
varying (but generally large) amounts of bad data.  The editing
scheme was patterned after the original waterfall editing used in
conjuction with codas processing: i.e. (1) view a time range with some
editing criteria, (2) list the ascii flag information to disk, (3)
move on to the next segment and repeat.  After you are finished
listing all the ascii flag information to the disk, you apply the
flags to the database.  With both kinds of editing, the results are not
seen in the database until you apply the editing to the database.  With
both kinds of editing, you can view the effects of the editing about
to be applied and can view the data with or without the
already-applied flags (if there are any).  

You should already be familiar with the original interactive editing
which used waterfall plots in matlab before using autoedit (see
process.txt).  One reason for this requirement is that you can (from
autoedit) jump back into the old waterfall editing and zap profiles or
bins.  It is very easy to get confused if you are not familiar with
the old waterfall editing tool.  The other reason is that the scheme
is the same: data are tagged for rejection using editing criteria
which are similar between the two schems, and the approach is the
same: view, list, view next group, list, [repeat until the end], apply
flags; check results.


*** Standardized processing: "quick_adcp.prl" (query-driven program to
    set up and run adcp processing steps)

Quick_adcp.prl is a command-line perl program that will set up and run
all the standard processing steps for a Narrowband shipboard ADCP
cruise, with various defaults accessible through switches on the
command line.  It is designed for batch-processing (i.e. the whole
time range of the specified pingdata files).  You can use it to
quickly process a cruise to a point where you can look at the database
to evaluate whether processing needs more intervention.  If your
cruise requires special treatment (eg. a time shift, no ashtech, etc)
you can stop the process at any point and do something manually, and
then go back to quick_adcp.prl and start after that step.  

Other advantages of using quick_adcp.prl:
(1) standardized file names
(2) records of what was done are left on the disk
(3) sets up the files for gautoedit 
(4) contains documentation:
    quick_adcp.prl --help     (lists commandline arguments and usage)
    quick_adcp.prl --howto    (tells how to get started)
    quick_adcp.prl --overview (lists quick_adcp.prl processing steps)
    quick_adpc.prl --config_info (some tips on customization)

*** Two more potentailly useful little scripts:
- linkping.prl (unix only) links a list of pingdata files from a
  source directory to the ping/ subdirectory as unique, sequentially
  numbered filenames.  This is particularly useful if there are repeated
  filenames (eg. from two legs, both starting at pingdata.000).
- scanping.prl goes through a list of specified pingdata files and
  scans them (i.e. writes scanping.tmp and runs "scanping
  scanping.tmp").  This is particularly useful if you want the time
  range of the data, or if you have a bunch of pingdata files with
  unknown time ranges that need to be sorted out (scanping.prl on each
  individually with a unique output name)

----
Note about names:

(1) Nomenclature: You have a directory root called "programs" which
    contains our "matlab" and "codas3" subdirectories.  I will refer to
    this as PROGRAMS when I identify paths.

(2) You have to run adcptree to start a processing directory; I will
    refer to the cruisename  as "demo" 

(3)  These perl programs reside in  PROGRAMS/codas3/bin/scripts.  Add
    this to your path.  To run, type "perl -S " followed by the perl
    script name, followed by any switches.  EG:
           perl -S  quick_adpc.prl --help


========================================================================
===================== (II)  directions==================================
========================================================================

If you have run quick_adcp.prl, you have two programs in your ADCP processing 
tree in the edit/ directory:


asetup.m            (basic information to configure gautoedit)
aflagit_setup.m     (parameters used to set editing criteria defaults)

If you are processing this cruise with quick_adpc.prl, use the
"-zapsetup" switch and it will automatically create an appropriate
"setup.m" file.   If you are not processing this cruise with
quick_adcp.prl, then copy the templates for these files from
PROGRAMS/matlab/autoedit, and edit them for your cruise.  You also
need to edit setup.m (for the original interactive editing programs).


Approach: You either have good data and want to automate the
old-fashioned editing (eg. Kaimimoana), or you have lousy data and
want to cavalierly eliminate anything of dubious character
(eg. N.B. Palmer).  The example is for decent data.  (Examples of
aflagit_setup.m for good and bad cruises are in goodcruise_ex/ and
badcruise_ex/, respectively)


in matlab, to start the gui tool, go the the edit/ subdirectory of your
ADCP processing directory and run:     
gautoedit 

This gui runs asetup (to get path info, dates,...) and aflagit_setup
(sets the editing parameters) and sets up gui tool to
let you view the effects of the editing on a range of days, adjust the
parameters and/or go into the old-fashioned editing scheme to trim
bins or profiles, allows you to list the chosen flags, and move on.
This tool was developed as a way to view and screen entire datasets
for gross abnormalities and identify issues to deal with later.

suggested iteration:
- adjust the parameters which control bin and profile flagging
- "show now" to see the data
- "list flags to disk" to add the flags from the current panel to the 
   ascii (a*.asc) files.  
-  "show next" to see the next group in time
tweaking:
- "find PG [blk, prf]" will let you identify time, block, profile, and 
      bin from the Percent Good data (for your notes)
- "old edit" lets you identify a [block, profile] location in the Percent
      Good data and puts you into the older interactive editing scheme.
      You can access commands from the command line 
      **NOTE:  Make sure you "list" on the command line so your flags to to 
               update the appropriate ascii files
      **NOTE:  You must edit setup.m before you try to use "zap" editing
               so it can find your database


NOTE that the reference layer and percent good cutoff
can be changed in this program to let you choose what value will work
best for a given time range.  HOWEVER in general we have used one PG
and one reference layer for an entire cruise.  These parameters are
set in other control files that are run when applying the editing and
running the nav steps)

More details are contained in the html documentation, at 
PROGRAMS/codas3/adcp/doc/edit_html/autoedit.html  or at
http://currents.soest.hawaii.edu/adcp_doc/edit_doc/edit_html/autoedit.html




APPLY THE RESULTS:


--> apply the editing from gautoedit:
      dbupdate ../adcpdb/dbname abottom.asc 
      dbupdate ../adcpdb/dbname abadprf.asc 
      badbin   ../adcpdb/dbname abadbin.asc 
--> apply the editing from waterfall editing:
      dbupdate ../adcpdb/dbname bottom.asc 
      dbupdate ../adcpdb/dbname badprf.asc 
      badbin   ../adcpdb/dbname badbin.asc 
--> always run these two in this order after applying any editing
      set_lgb ../adcpdb/dbname 
      setflags setflags.cnt 


--> rerun the nav steps:
     cd ../nav
     (run these steps to redo watertrack calibrations and redo
          reference layer plots.)

     adcpsect       as_nav.tmp
     refabs         refabs.tmp
     smoothr        smoothr.tmp

     (run these to update navigation)

     (in matlab)
     refsm       
     (from the command line)
     putnav         putnav.tmp


     cd ../edit


examine the results, reiterate if necessary

README:
=======
# TODO: update accordingly with naming convention

In this package, "Forms" are standalone mini-GUIs that facilitate the use of the
extensive UHDAS toolbox.

Usually, a "Form" has one purpose and is related to one particular task only,
hence is different to a GUI per se.

From a coding perspective, "Forms" are mostly self-contained except for some
generic function pulled from lib.

There are 5 Forms in this package:
1. vmdas_converter_form.py: Converts Vmdas’ LTA and STA data files to
   UHDAS-style data  as well as prepare ENR files for conversion
2. reform_vmdas_form.py: Reformats VmDAS’ ENR data into UHDAS-style data
3. proc_starter_form.py: Creates a UHDAS configuration file for processing
   UHDAS-style data
4. uhdas_proc_gen_form.py: Creates a new UHDAS configuration file for
   processing native UHDAS data
5. adcp_tree_form.py: Sets up a processing directory architecture based
   on existing *_proc.files
In essence,  these forms have been designed for converting “raw input data”
into “dataviewer ready” data. They can be called independently or one can use
the adcp_database_maker.py form for more guidance. The adcp_database_maker.py
form shall navigate the user between different scenarii
(see detail here: https://currents.soest.hawaii.edu/docs/adcp_doc/codas_doc/adcp_py3demos/adcp_database_maker_demos/index.html)
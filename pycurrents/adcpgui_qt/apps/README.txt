README:
=======

In this package, "Apps" are standalone interactive GUIs that facilitate the use
of the extensive UHDAS toolbox.

Usually, an "App" has one purpose and is related to one particular task only,
hence is different to a traditional GUI per se.

From a coding perspective, "Apps" are mostly self-contained except for some
generic function pulled from lib.

Similarly to the dataviewer GUI, the "Apps" are built around a MVP design pattern:
   - See pycurrents/adcpgui_qt/lib/images/...
         ...Model_View_presenter_GUI_Design_Pattern.png
   - See https://www.codeproject.com/Articles/228214/...
         ...Understanding-Basics-of-UI-Design-Pattern-MVC-MVP

The "Apps" codes are also leveraging some of the components of the
dataviewer GUI's components

There are 2 main Apps in this package:
1. figview.py: Crawls/searches and displays picture like files (*.png, *.jpg,...)
2. patch_hcorr_app.py: Allows manual editing and interpolation throughout
   ship’s heading feeds
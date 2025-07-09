#!/usr/bin/env python3

import os
import sys
import tempfile
import subprocess
import logging

from argparse import ArgumentParser
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QSettings, QPoint, QDir, Qt
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QImageReader, QIcon, QPalette, QPixmap, QImage, QGuiApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QTransform, QAction
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QMainWindow, QSplitter, QStatusBar
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QListWidgetItem, QMenu
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QMessageBox, QFileDialog, QWidget, QLabel
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QSizePolicy, QScrollArea, QVBoxLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QListWidget, QLineEdit, QApplication
from pycurrents.system.misc import Bunch  # BREADCRUMB: common lib
from pycurrents.adcpgui_qt.lib.qtpy_widgets import iconUHDAS
from pycurrents.system.logutils import setLoggerFromOptions

# Standard logging
_log = logging.getLogger(__name__)

help_text = """
figview.py: Crawls/searches and displays picture like files (*.png, *.jpg,...)
            No directory browsing, unix only.

usage:

figview.py [--dpi NUM] [--type type1:type2] [dirname]

        dpi: if figures are postscript or PDF, convert with this dpi
        type: colon-delimited list of filetypes to view
        dir: optional -- look in dir for these files (default is ./),
             can be specified with the first argument in the list

examples

figview.py --help                              # print usage
figview.py dirname                             # all png files below dirname
figview.py image1 [image2] [image3]            # display specific images
figview.py dirname  image1 [...]               # all png files below dirname
                                               # plus specified image(s)
figview.py dirname and image(s) --type gif     # all gif files below here
figview.py dirname and image(s) --type png:ps  # all png and postscript
                                               # files in dir
figview.py dirname and image(s) --all          # all image files below here
                                               # including 'bmp', 'gif',
                                               # 'ico', ' jpeg', 'jpg','mng',
                                               # 'pbm', ' pgm', 'png', 'ppm',
                                               # 'svg', 'svgz', 'tga', 'tif',
                                               # 'tiff', ' xbm', 'xpm', 'ps'
                                               # and 'pdf'
"""

# Header
__version__ = 'Beta 1.0'
__author__ = 'Dr. Thomas Roc, UHDAS Group'

# Global variables
DEFAULT_EXTENSIONS = ['.' + ext.data().decode('utf-8') for ext in
                      QImageReader.supportedImageFormats()]
ADDED_EXTENSIONS = ['.ps', '.pdf']
# - Extending list in order to cover more formats
DEFAULT_EXTENSIONS.extend(ADDED_EXTENSIONS)
PS_PDF_FILES = {}
# - Path substitute
SUB = '..'


class MyMainWindow(QMainWindow):
    def __init__(self, followlinks=False, images=[], dirpath='./',
                 extensions=DEFAULT_EXTENSIONS, dpi=72, parent=None):
        """
        This class inherits from QMainWindow class and is the backbone
        of the application. It contains all the widgets of the
        application, connects of all the signals and passes on
        arguments and options.

        Args:
            followlinks: option for the 'populate' method of
                         the ImageViewer widget, bool
            images: option for the ImageFileList widget list of strings
            dirpath: attribute of the ImageViewer widget
                     path of the start-up directory, str
            extensions: attribute of the ImageViewer widget
                        file extensions to display, list of str
            dpi: option of the 'convertps' method, number of DPI, int
            parent: standard, option, parent class
        """
        super().__init__(parent)
        # Main window attributes
        self.setWindowTitle('FigView')
        self.setWindowIcon(QIcon(iconUHDAS))
        # Define main window's widgets
        #  - Two main panels
        self.imageFileList = ImageFileList(followlinks, dirpath, extensions)
        self.imageViewer = ImageViewer(dpi)
        #  - Adding horizontal splitter to main window
        self.horizontalSplitter = QSplitter(Qt.Horizontal)
        self.horizontalSplitter.addWidget(self.imageFileList)
        self.horizontalSplitter.addWidget(self.imageViewer)
        # Not sure if I need the next line
        self.setCentralWidget(self.horizontalSplitter)
        #  - Toolbar
        self._create_actions()
        self._create_menus()
        #  - Status bar
        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)

        # Settings and standard restoring
        settings = QSettings()
        #   - splitter settings
        self.horizontalSplitter.setStretchFactor(0, 1)
        self.horizontalSplitter.setStretchFactor(1, 9)
        #  - save default values for later
        settings.setValue('MainWindow/State', self.saveState())
        settings.setValue('Splitter', self.horizontalSplitter.saveGeometry())
        #  - resize window
        sg = QGuiApplication.primaryScreen().geometry()
        self.resize(sg.width() // 2, sg.height() // 2)
        position = settings.value("MainWindow/Position", QPoint(0, 0))
        self.move(position)
        #  - restore to default values
        self.restoreState(settings.value("MainWindow/State"))
        self.horizontalSplitter.restoreState(settings.value("Splitter"))

        # Connecting main window to specific keyboard entries and
        #  actions/updates
        self.imageFileList.userEntry.returnPressed.connect(
            self._update_user_extensions)
        self.imageFileList.list.currentItemChanged.connect(self._update_image)
        self.horizontalSplitter.splitterMoved.connect(self._update_image)

        # Kick-start/start-up actions
        #  - in case images have been specified at the command level
        if images:
            for image in images:
                item = QListWidgetItem(self.imageFileList.list)
                item.setText(image)
                item.setIcon(QIcon(image))
            self._update_image()
        else:
            self._update_extensions()

    # Create actions and connect them buttons and keyboard shortcuts
    def _create_actions(self):
        """
        This method defines all the actions that the user could make
        through the interface
        """
        # File menu
        self.openAct = QAction("&Open...", self,
                               shortcut="Ctrl+O", triggered=self.open)
        self.exitAct = QAction("Exit", self, triggered=self.close)
        self.exitAct.setShortcuts(["Ctrl+Q", "Ctrl+C"])
        # View menu
        self.rotateClockWise = QAction("Rotate Clock Wise (-90 deg.)", self,
                                       shortcut="Ctrl+r",
                                       triggered=self.rotate_clockW)
        self.rotateAnticlockWise = QAction("Rotate Anticlock Wise (90 deg.)",
                                           self, shortcut="Ctrl+Shift+r",
                                           triggered=self.rotate_antiCW)
        self.zoomInAct = QAction("Zoom In (25%)", self,
                                 shortcut="Ctrl++", triggered=self.zoom_in)
        self.zoomOutAct = QAction("Zoom Out (25%)", self,
                                  shortcut="Ctrl+-", triggered=self.zoom_out)
        self.normalSizeAct = QAction("&Normal Size", self,
                                     shortcut="Ctrl+N",
                                     triggered=self.normal_size)
        self.fitToWindowAct = QAction("Toggle &Fit-to-Window mode", self,
                                      shortcut="Ctrl+F",
                                      triggered=self.fit_to_window)
        # Help menu
        self.helpAct = QAction("Short cuts", self, triggered=self.help)

    # Set up toolbar
    def _create_menus(self):
        """
        This method creates the menu of the toolbar and
        connects it to its relative actions
        """
        # File menu
        self.fileMenu = QMenu("File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAct)
        # View menu
        self.viewMenu = QMenu("View", self)
        self.viewMenu.addAction(self.rotateClockWise)
        self.viewMenu.addAction(self.rotateAnticlockWise)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.zoomInAct)
        self.viewMenu.addAction(self.zoomOutAct)
        self.viewMenu.addAction(self.normalSizeAct)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.fitToWindowAct)
        # Help menu
        self.helpMenu = QMenu("Help", self)
        self.helpMenu.addAction(self.helpAct)
        # Constructor
        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.viewMenu)
        self.menuBar().addMenu(self.helpMenu)

    # Actions related buttons and keyboard shortcuts events
    def help(self):
        """
        This method defines the content of the interface's help text
        """
        QMessageBox.about(self,
                          "About Image Viewer",
                          "<p><b>---Short Cuts---</b></p>"
                          "<p>Ctrl++ = zoom in</p>"
                          "<p>Ctrl+- = zoom out</p>"
                          "<p>Ctrl+r = rotate image clockwise</p>"
                          "<p>Ctrl+Shift+r = rotate image anti clockwise</p>"
                          "<p>Ctrl+n = image's normal size</p>"
                          "<p>Ctrl+f = toggle in and out of"
                          " fit-to-window mode</p>")

    def zoom_in(self):
        """
        This methods zooms in the displayed images by 25%
        """
        self.imageViewer.scaleFactor *= 1.25
        self.imageViewer.zoomFactor = 1.25
        self._update_image()

    def zoom_out(self):
        """
        This methods zooms out the displayed images by 25%
        """
        self.imageViewer.scaleFactor *= 0.8
        self.imageViewer.zoomFactor = 0.8
        self._update_image()

    def normal_size(self):
        """
        This methods sets the displayed images in their normal sizes
        """
        if self.imageViewer.fitToWindow:
            self.fit_to_window()
        else:
            self.imageViewer.scaleFactor = 1.0
            self.imageViewer.zoomFactor = 1.0
            self._update_image()

    def fit_to_window(self):
        """
        This method toggles the fit-to-window mode
        """
        self.imageViewer.fitToWindow = not self.imageViewer.fitToWindow
        self.imageViewer.scaleFactor = 1.0
        self.imageViewer.zoomFactor = 1.0
        if self.imageViewer.fitToWindow:
            self.zoomInAct.setEnabled(False)
            self.zoomOutAct.setEnabled(False)
            self.normalSizeAct.setEnabled(False)
        else:
            self.zoomInAct.setEnabled(True)
            self.zoomOutAct.setEnabled(True)
            self.normalSizeAct.setEnabled(True)
        self._update_image()

    def rotate_clockW(self):
        """
        This method rotates displayed images by -90 degrees
        """
        self.imageViewer.rotation -= 90
        if self.imageViewer.rotation <= -360:
            self.imageViewer.rotation = 0
        self._update_image()

    def rotate_antiCW(self):
        """
        This method rotates displayed images by 90 degrees
        """
        self.imageViewer.rotation += 90
        if self.imageViewer.rotation >= 360:
            self.imageViewer.rotation = 0
        self._update_image()

    def open(self):
        """
        This method redefine the 'dirpath' attribute of
        the ImageFileList widget (=working directory)
        """
        folderName = QFileDialog.getExistingDirectory(
            self, "Open Folder", QDir.currentPath(),
            options=QFileDialog.DontUseNativeDialog)
        self.imageFileList.dirpath = str(folderName)
        self._update_extensions()

    # Actions related with update/widgets refresh events
    def _update_extensions(self):
        """
        This method updates the images list displayed
        in the ImageFileList widget
        """
        # Update the user entry and list
        self.imageFileList.populate()
        if not self.imageFileList.images_list:  # IndexError fix
            self.imageFileList.extensions = DEFAULT_EXTENSIONS
            self.imageFileList.populate()
            # Check if message has been displayed previously
            info_message = 'No such file extension. Back to default...'
            if not self.imageFileList.userEntry.text() == info_message:
                self.imageFileList.userEntry.setText(info_message)
                return
        self.imageFileList.userEntry.clear()
        self.imageFileList.userEntry.clearFocus()
        self.imageFileList.list.setFocus()
        # _update image
        self._update_image()

    def _update_user_extensions(self):
        """
        This method updates the images list displayed
        in the ImageFileList widget
        """
        # Update the user entry and list
        userExtensions = "%s" % self.imageFileList.userEntry.text()
        self.imageFileList.define_extensions(userExtensions)
        self._update_extensions()

        return

    def _update_image(self):
        """
        This method updates the image displayed in the ImageViewer widget
        """
        try:
            imagePath = self.imageFileList.list.currentItem().text().replace(
                SUB, self.imageFileList.dirpath)
            # Error generated when imageList.currentItem == None
            # = nothing selected on list
        except AttributeError:
            imagePath = self.imageFileList.list.item(0).text().replace(
                SUB, self.imageFileList.dirpath)
        self.imageViewer.display(imagePath)
        # Update status bar
        self.statusBar.clearMessage()
        self.statusBar.showMessage(
            'Work Dir.: {0} | Rotation: {1} deg. | Scale factor: {2} | '\
            'Fit-to-window mode: {3}'
            .format(self.imageFileList.dirpath,
                    self.imageViewer.rotation,
                    round(self.imageViewer.scaleFactor, 1),
                    self.imageViewer.fitToWindow))

    # Actions related with resizing widget
    # N.B: This one permit to keep the aspect ratio of image
    #      when fit-to-win mode on and refresh after resizing
    #      and needed as there is no such thing as "resized signal"
    #      for QMainWindow class
    def resizeEvent(self, resizeEvent):
        if self.imageViewer.fitToWindow:
            self._update_image()


class ImageViewer(QWidget):
    def __init__(self, dpi, parent=None):
        """
        Image viewer class, inherited from QWidget, uses QLabel to
        display QPixmap

        Args:
            dpi: number of dpi for ps and pdf conversion, int
            parent: standard, option, parent class
        """
        super().__init__(parent)
        # Attributes
        self.scaleFactor = 1.0
        self.zoomFactor = 1.0
        self.rotation = 0
        self.fitToWindow = False
        self.dpi = dpi
        # Define QLabel image space
        self.imageLabel = QLabel()
        self.imageLabel.setBackgroundRole(QPalette.Base)
        self.imageLabel.setSizePolicy(QSizePolicy.Ignored,
                                      QSizePolicy.Ignored)
        # Scroll area
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidget(self.imageLabel)
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.scrollArea)
        self.setLayout(self.layout)

    def display(self, unicode_path_image):
        """
        This method display the given image

        Args:
            unicode_path_image: path to image to display,
                                str, unicode
        """
        # Widget actions
        #  - Define pixmap
        imageExt = os.path.splitext(str(unicode_path_image))[1]
        if imageExt not in ADDED_EXTENSIONS:
            pixmap = QPixmap.fromImage(QImage(unicode_path_image))
        # special treatment for added extensions (i.e. ps and pdf)
        else:
            pixmap = QPixmap.fromImage(
                QImage(convertps(unicode_path_image, dpi=self.dpi)))
        #  - Rotate
        if not self.rotation == 0:
            pixmap = self.rotate(pixmap)
        #  - Scale
        if not self.scaleFactor == 1.0:
            self.scale_image(pixmap)
        #  - Display
        if self.fitToWindow:  # special treat if "fit-to-window" mode on
            self.scrollArea.setWidgetResizable(True)
            # Keep aspect ratio
            self.imageLabel.setScaledContents(False)
            self.imageLabel.setPixmap(
               pixmap.scaled(self.imageLabel.width(),
                             self.imageLabel.height(),
                             Qt.KeepAspectRatio))
        else:
            self.scrollArea.setWidgetResizable(False)
            # Keep scale to content
            self.imageLabel.setPixmap(pixmap)
            self.imageLabel.setScaledContents(True)
        if self.scaleFactor == 1.0:  # special treat if "normal size" on
            self.imageLabel.adjustSize()

    def scale_image(self, pixmap):
        """
        This method scales the displayed image based
        on the scaleFactor attributes
        """
        self.imageLabel.resize(self.scaleFactor
                               * pixmap.size())

    def rotate(self, pixmap):
        """
        This method rotates any given pixmap accordingly
        with the "_rotation" attribute

        Args:
            pixmap: QPixmap object

        Returns: Rotated QPixmap object

        """
        rm = QTransform()
        rm.rotate(self.rotation)
        newPixmap = pixmap.transformed(rm)

        return newPixmap


class ImageFileList(QWidget):
    def __init__(self, followlinks, dirpath, extensions, parent=None):
        """
        ImageFileList class inherits from Qwidget and contains
        a QListWidget and a QlineEdit.

        Args:
            followlinks: option for the 'populate' method, bool
            dirpath: path of the start-up directory, str
            extensions: file extensions to display, list of str
            parent: standard, option, parent class
        """

        super().__init__(parent)
        # Attributes
        self.followlinks = followlinks
        self.extensions = extensions
        self.dirpath = dirpath
        self.images_list = None
        # Define list widget and entry
        self.list = QListWidget()
        self.userEntry = QLineEdit()
        self.userEntry.setPlaceholderText(
            "Specify image extension(s): *.png, *.jpg,...")
        # Panels' Layout-put file list and entry together in same panel
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.list)
        self.layout.addWidget(self.userEntry)

    def populate(self):
        """
        This method sets and refreshes the list of images based
        on the '_dirpath' attribute (=working directory).
        """
        # In case we're repopulating, clear the list
        self.list.clear()
        # Create a list item for each image file,
        # setting the text and icon appropriately
        self.fetch_images()
        for image in self.images_list:
            item = QListWidgetItem(self.list)
            item.setText(image)
            item.setIcon(QIcon(image))

    def fetch_images(self):
        """
        This method changes the attribute "image_list"
        to all supported images in self.dirpath.
        """
        filenames = fetch_images(self.extensions, self.dirpath,
                                 self.followlinks)
        images = []
        for fn in filenames:
            if fn.lower().endswith(tuple(self.extensions)):  #tuple = quick fix
                relativeName = os.path.join(self.dirpath, fn).replace(
                    self.dirpath, SUB)
                images.append(relativeName)
        self.images_list = sorted(images)

    def define_extensions(self, extensionsText):
        """
        This method defines the list of extensions to be handle by
        the widget and changes the '_extensions' attribute accordingly.

        Args:
            extensionsText: ['jpg, 'png, ... ], list of unicode strings
        """
        self.extensions = []
        for extension in DEFAULT_EXTENSIONS:
            if extension[1:] in extensionsText.lower():  # discard "." in ext.
                self.extensions.append(extension)


### Library of functions ###
def fetch_images(extensions, dirpath, followlinks):
    """
    This method changes the attribute "image_list"
    to all supported images in dirpath.
    """
    # Start with an empty list
    images = []
    # Find the matching files for each valid
    # extension and add them to the images list
    for extension in extensions:
        for dirpath, dirnames, filenames in os.walk(dirpath,
                                                    topdown=False,
                                                    followlinks=followlinks):
            for fn in filenames:
                if fn.lower().endswith(extension):
                    absName = os.path.join(os.path.abspath(dirpath), fn)
                    images.append(absName)
    return sorted(images)


def convertps(infilename, dpi=120):
    """
    This function manages the converting ps and pdf files into
    temporary png images. It also manages existing temporary files
    so the conversions don't have to be repeated.

    Args:
        infilename: path to file, unicode string
        dpi: number of dpi per converted png, int

    Returns: path to temporary image, unicode string

    """

    if str(infilename) not in list(PS_PDF_FILES.keys()):
        tmpfilename = tempfile.mktemp(suffix='.png')
        PS_PDF_FILES[infilename] = tmpfilename
        gs_pdf_ps_to_png(infilename, tmpfilename, dpi)
        return tmpfilename
    else:
        return PS_PDF_FILES[infilename]


def gs_pdf_ps_to_png(pdffilepath, outfilename, resolution):
    """
    This function converts ps and pdf files into temporary png images.

    Args:
        pdffilepath: path to ps or pdf, unicode string
        outfilename: path to output file, unicode string
        resolution: dpi, int

    """
    # Change the "-rXXX" option to set the PNG's resolution.
    # http://ghostscript.com/doc/current/Devices.htm#File_formats
    # For other commandline options see
    # http://ghostscript.com/doc/current/Use.htm#Options
    arglist = ["gs",
               "-dBATCH",
               "-dNOPAUSE",
               "-sOutputFile=%s" % outfilename,
               "-sDEVICE=png16m",
               "-r%s" % resolution,
               str(pdffilepath)]
    subprocess.call(arglist, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main(test=False, options=Bunch()):
    # Parsing command line inputs
    if not test:
        # - Defining options and arg
        parser = ArgumentParser(usage=help_text)
        parser.add_argument(dest='startdir', metavar='dirname',
                            type=str, nargs='*',
                            default=[os.getcwd()],
                            help='path(s) to images or folder, with or'
                                 'without wildcards or files extension(s)')
        parser.add_argument("--dpi", default=72, dest='dpi', type=int,
                            help='number of dpi for ps and pdf conversion')
        parser.add_argument("--type", default=['.png'],
                            dest='extensions',
                            help='file extension(s) to display')
        parser.add_argument("--all", nargs='?', const=DEFAULT_EXTENSIONS,
                            dest='extensions',
                            help='display all file extensions')
        parser.add_argument("-f", "--followlinks", default=False, nargs='?',
                            const=False, dest="followlinks",
                            help='follow symbolic links? True/False')
        help = "Switches on debug level logging and writes in ./debug.log"
        parser.add_argument("--debug", dest="debug", action='store_true',
                            default=False, help=help)
        # - Mashing arguments
        options = parser.parse_args()
    else:
        if not options:
            msg = 'YOUR options DICTIONNARY IS EMPTY!'
            msg += '\nAddress and try again'
            _log.error(msg)
    # set-up logger
    setLoggerFromOptions(options)
    # Listing images to display
    # - defining images suffix(es)
    if isinstance(options.extensions, str):
        options.extensions = ['.'+ext for ext in options.extensions.split(':')]
    # - crawling down/searching folder tree
    listDirpaths = []
    listImages = []
    options.startdir = [os.path.abspath(fname) for fname in options.startdir]
    for entry in options.startdir:
        if os.path.isdir(entry):
            listDirpaths.append(entry)
            extraIm = fetch_images(options.extensions,
                                   entry, options.followlinks)
            listImages.extend([os.path.abspath(fname) for fname in extraIm])
        if os.path.isfile(entry):
            listDirpaths.append(os.path.split(entry)[0])
            if os.path.splitext(entry)[1] in options.extensions:
                listImages.append(entry)
    # - shortening path names by replacing the common path by SUB
    options.startdir = os.path.commonprefix(listDirpaths)
    if not os.path.isdir(options.startdir):
        options.startdir = os.path.dirname(options.startdir)
    listImages = [fname.replace(options.startdir, SUB)
                  for fname in listImages]
    # Kick-start application
    app = QApplication(sys.argv)
    figview = MyMainWindow(followlinks=options.followlinks,
                           images=listImages, dirpath=options.startdir,
                           dpi=options.dpi, extensions=options.extensions)
    figview.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

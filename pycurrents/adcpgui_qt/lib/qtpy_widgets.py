# Standard Logging
import logging
import os
import sys
from functools import wraps
# The following line has the side effect of setting the QT_API environment
# variable, currently to "pyqt5" (lower case). (qtconsole 5.6.1, conda-forge)
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.lib import guisupport

from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import Qt, QSize
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QIntValidator, QValidator, QDoubleValidator
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QFont, QIcon, QCursor
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QWidget, QFrame, QStyleFactory, QLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QScrollArea, QApplication, QSizePolicy
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QPushButton, QLabel,  QCheckBox, QMessageBox
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QLineEdit, QComboBox, QSpinBox
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QStyleOptionSlider, QSlider, QStyle
from pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout
from pycurrents.adcpgui_qt.lib.qt_compat.QtGui import QRegularExpressionValidator, QGuiApplication
from pycurrents.adcpgui_qt.lib.qt_compat.QtCore import QRegularExpression

# Standard logging
_log = logging.getLogger(__name__)

### Styles & Formatting ###
# Global style
if sys.version_info[0] < 3:
    globalStyle = QStyleFactory().create("Cleanlooks")
else:
    globalStyle = QStyleFactory().create("Fusion")
#  N.B.: only 'Windows' and 'Fusion' are available in py36 yet more
#        options exist: plastique, cde, motif, sgi, windows, cleanlooks, mac
#  N.B.: 'Fusion' actually does not exist for py 2.7
# style keywords
backGroundKey = "background-color: "
borderKey = "border:2px solid "
# Color Palette
orange = "rgb(255, 69, 0); "
beige = "rgb(246, 242, 225); "
blue = "rgb(203, 245, 246); "
green = "rgb(210, 250, 205); "
purple = "rgb(236, 205, 250); "
red = "rgb(253, 123, 123); "
silver = "rgb(218, 218, 218); "
grey = "rgb(206, 206, 206); "
darkGrey = "rgb(100, 100, 100); "
brightRed = "rgb(255, 60, 60); "
brightBlue = "rgb(75, 87, 255); "
brightGreen = "rgb(87, 230, 95); "
backGroundBeige = "rgb(250, 250, 230); "  # "rgb(246, 242, 225); "
backGroundGreen = "rgb(230, 250, 225); "  # "rgb(210, 250, 205); "
backGroundBlue = "rgb(220, 245, 245); "  # "rgb(203, 245, 246); "
backGroundRed = "rgb(255, 180, 180); "  # "rgb(253, 123, 123); "
backGroundPurple = "rgb(240, 230, 240); "  # "rgb(236, 205, 250); "
# Default background colors
silverBackGroundColor = backGroundKey + silver
whiteBackGroundColor = backGroundKey + "white; "
# mode color themes
modeColor = {"compare": backGroundKey + backGroundGreen,
             "view": backGroundKey + backGroundBeige,
             "edit": backGroundKey + backGroundBlue,
             "patch": backGroundKey + backGroundRed,
             "single ping": backGroundKey + backGroundPurple}
# Round corner
roundCorners = "border-radius: 6px; "
# Imported picture
adcpgui_qtPath = os.path.dirname(__file__)
leftArrow = adcpgui_qtPath + "/images/backward.png"
rightArrow = adcpgui_qtPath + "/images/forward.png"
iconUHDAS = adcpgui_qtPath + "/images/uhdasicon_bordertrimmed.png"


### Custom widgets ###
class CustomButton(QPushButton):
    def __init__(self, icon_path=None, background_color=None, parent=None):
        """
        Custom class inheriting from QPushButton
        Args:
            icon_path: path to icon image, str
            background_color: rgb color, str (see above)
            parent: parent QWidget
        """
        super().__init__(parent=parent)
        if icon_path:
            icon = QIcon(icon_path)
            try:  # issue with qtpy portability or cannot read icons
                iconSize = 2 * icon.availableSizes()[0]
            except IndexError:
                iconSize = QSize(50, 50)
            self.setIcon(icon)
            self.setIconSize(iconSize)
        if background_color:
            self.setStyleSheet(background_color)


class CustomPushButton(QPushButton):
    """
    Custom class similar to QPushButton yet with bold font
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        boldFont = QFont()
        boldFont.setBold(True)
        self.setFont(boldFont)

class ClickableSlider(QSlider):
    """
    Custom slider that moves to the clicked position and starts dragging.
    https://stackoverflow.com/questions/52689047/moving-qslider-to-mouse-click-position
    """

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setValue(self.pixelPosToRangeValue(event.pos()))
            self.setSliderDown(True)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():
            self.setValue(self.pixelPosToRangeValue(event.pos()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setSliderDown(False)
        super().mouseReleaseEvent(event)

    def pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

        if self.orientation() == Qt.Horizontal:
            sliderMin, sliderMax = gr.x(), gr.right() - sr.width() + 1
            p = pos.x() - sr.width() // 2
        else:
            sliderMin, sliderMax = gr.y(), gr.bottom() - sr.height() + 1
            p = pos.y() - sr.height() // 2

        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin,
                                              sliderMax - sliderMin, opt.upsideDown)

class CustomLabel(QLabel):
    def __init__(self, label, style='', color='', parent=None):
        """
        Custom class inheriting from QLabel
        Args:
            label: str, text to display
            style: str, style of heading, i.e. 'h1', 'h2', 'h3'
            color: str, color, e.g. 'green', 'red', 'yellow', etc.
            parent: parent QWidget
        """
        super().__init__(label, parent=parent)
        style = style.lower()
        self.setStyleSheet("color: " + darkGrey)
        if style == 'h1':
            font = QFont("?", 14, QFont.Bold, italic=True)
            self.setFont(font)
        if style == 'h2':
            font = QFont("?", 12, QFont.Bold, italic=True)
            self.setFont(font)
        if style == 'h3':
            font = QFont("?", 10, QFont.Bold, italic=True)
            self.setFont(font)
        if color:
            self.setStyleSheet('color: %s' % color)


class CustomEntry(QLineEdit):
    def __init__(self, size=50, entry_type=float, value=None,
                 min_value=0.0, max_value=9999.99,
                 background_color=whiteBackGroundColor, parent=None):
        """
        Custom class inheriting from QLineEdit
        Args:
            size: int, size of the entry box in p_int
            entry_type: type, input's type, i.e. int, float, etc
            value: int, float, str, default value to display in entry box
            min_value: minimum value that can be typed in, float
            max_value: maximum value that can be typed in, float
            background_color: background color of the box,
                              ex. backGroundKey + green, see styles for more
                              options
            parent: parent QWidget
        """
        super().__init__(parent)
        if entry_type is float:
            self.setValidator(QDoubleValidator(min_value, max_value, 3))
        elif entry_type is int:
            validator = QIntValidator(int(min_value), int(max_value))
            self.setValidator(validator)
        else:
            self.setValidator(QDoubleValidator(min_value, max_value, 2))
        self.setAlignment(Qt.AlignRight)
        self.setFixedWidth(size)
        self.setFixedHeight(QFont("?", 20).pointSize())
        self.setStyleSheet(background_color)
        if value is not None:
            if entry_type is float:
                self.setText("{0:.2f}".format(value))
            else:
                self.setText("{0}".format(value))

    def check_state(self):
        """
        Actions to take when input is punched in
        """
        sender = self.sender()
        validator = sender.validator()
        state = validator.validate(sender.text(), 0)[0]
        if state == QValidator.Acceptable:
            color = green
        elif state == QValidator.Intermediate:
            color = beige
        else:
            color = red
        sender.setStyleSheet('QLineEdit { ' + backGroundKey + color + ' }')


class CustomDropdown(QComboBox):
    def __init__(self, variables, index=None, parent=None):
        """
        Custom class inheriting from QComboBox
        Args:
            variables: list, list of variables to display in dropdown menu
            index: int, list index of the variable to display by default
            parent: parent QWidget
        """
        super().__init__(parent)
        self.addItems(variables)
        if index:
            self.setCurrentIndex(index)


class CustomDropdownCompareMode(QWidget):
    def __init__(self, variables, sonars, index=None, parent=None):
        """
        Custom class inheriting from QComboBox for compare mode
        Args:
            variables: list, list of variables to display in dropdown menu
            sonars: list of str, sonars available for display
                         in dropdown menu
            index: int, list index of the variable to display by default
            parent: parent QWidget
        """
        super().__init__(parent)
        # Widgets
        self.variables = CustomDropdown(variables, index=index, parent=self)
        self.sonars = CustomDropdown(sonars,
                                          index=index % len(sonars),
                                          parent=self)
        self.layout = QHBoxLayout(self)
        self.setLayout(self.layout)
        # Layout
        self.layout.addWidget(self.sonars, 1)
        self.layout.addWidget(QLabel(':'))
        self.layout.addWidget(self.variables, 1)
        # Style
        self.layout.setContentsMargins(0, 0, 0, 0)


class CustomSpinbox(QSpinBox):
    def __init__(self, range=None, step=None, value=None, prefix=None,
                 parent=None):
        """
        Custom class inheriting from QSpinBox
        Args:
            range: int or float, max value
            step: int or float, step for iteration
            value: int or float, default value to start from
            prefix: str, text to add before value for aesthetic purposes
            parent: parent QWidget
        """
        super().__init__(parent)
        self.lineEdit().setReadOnly(True)
        if range:
            self.setRange(1, range)
        if step:
            self.setSingleStep(step)
        if prefix:
            self.setPrefix(prefix)
        if value:
            self.setValue(value)
        self.setStyleSheet(whiteBackGroundColor)


class CustomCheckboxEntryLabel(QWidget):
    def __init__(self, label, has_checkbox=True, value=None, enabled=True,
                 background_color=whiteBackGroundColor, parent=None):
        """
        Custom class encapsulating a checkbox, a user entry and a label
        in the same widget
        Args:
            label: str, label to display at the right of the entry box
            has_checkbox: bool, has a visible checkbox ?
            enabled: bool, is the checkbox enabled ?
            value: default value, float
            background_color: background color, str
            parent: parent QWidget
        """
        super().__init__(parent)
        # Widgets
        self.color = background_color
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(1, 0, 1, 0)
        self.layout.setSizeConstraint(QLayout.SetFixedSize)
        self.checkbox = QCheckBox(self)
        self.entry = CustomEntry(entry_type=int, value=value, size=40,
                                 background_color=background_color)
        # Layout
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.entry)
        self.label = QLabel(label)
        self.layout.addWidget(self.label)
        self.layout.addStretch()
        # Style
        keepSpaceInLayout = QSizePolicy()
        keepSpaceInLayout.setRetainSizeWhenHidden(True)
        self.checkbox.setSizePolicy(keepSpaceInLayout)
        # States & values
        if not has_checkbox:
            self.checkbox.hide()
            self.checkbox.setChecked(True)
            self.checkbox.setEnabled(False)
        else:
            # Connect checkbox to check_state
            self.checkbox.stateChanged.connect(self.check_state)
            if enabled:
                self.check_state(True)
                self.checkbox.setChecked(True)
            else:
                self.check_state(False)
                self.checkbox.setChecked(False)

    def check_state(self, checked):
        """
        Actions to take when checkbox is ticked/unticked
        Args:
            checked: bool
        """
        if checked:
            self.entry.setEnabled(True)
            self.entry.setStyleSheet(self.color)
        else:
            self.entry.setEnabled(False)
            self.entry.setStyleSheet(backGroundKey + grey)


class CustomCheckboxEntries(QWidget):
    def __init__(self, label, value=None, enabled=True, parent=None):
        """
        Custom class encapsulating an autoscale checkbox, two user entries
        (i.e min/max) and a label in the same widget
        Args:
            label: str, label to display above the entry boxes
            enabled: bool, is the checkbox enabled ?
            value: default values, [float, float], [min., max.]
            parent: parent QWidget
        """
        super().__init__(parent)
        # Widgets
        self.entryMin = CustomEntry(size=40, entry_type=int, value=value[1])
        self.entryMax = CustomEntry(size=40, entry_type=int, value=value[0])
        self.checkboxAutoscale = QCheckBox("auto-scale")
        widgets = [CustomLabel(label, style='h3'),
                   self.checkboxAutoscale,
                   QLabel("min"), self.entryMin,
                   QLabel("max"), self.entryMax]
        if parent:
            parent.layout = CustomPanelGridLayout2(widgets, parent)
        # States & values
        # Connect checkbox to check_state
        self.checkboxAutoscale.stateChanged.connect(self.check_state)
        if enabled:
            self.check_state(True)
            self.checkboxAutoscale.setChecked(True)
        else:
            self.check_state(False)
            self.checkboxAutoscale.setChecked(False)

    def check_state(self, checked):
        """
        Actions to take when checkbox is ticked/unticked
        Args:
            checked: bool
        """
        if checked:
            self.entryMin.setEnabled(False)
            self.entryMax.setEnabled(False)
        else:
            self.entryMin.setEnabled(True)
            self.entryMax.setEnabled(True)


class CustomCheckboxDropdown(QWidget):
    def __init__(self, label, items, checkbox=False, parent=None):
        super().__init__(parent)
        Layout = QGridLayout(parent)
        Layout.addWidget(CustomLabel(label, style='h3', parent=parent),
                         0, 0, 1, 1)
        if checkbox:
            self.checkbox = QCheckBox('Enable', parent=parent)
            Layout.addWidget(self.checkbox, 0, 1, 1, 1)
        label = QLabel("(feed, message)")
        label.setFont(QFont("?", 10, italic=True))
        Layout.addWidget(label, 1, 0, 1, 1)
        self.dropDown = QComboBox(parent=parent)
        self.dropDown.addItems(items)
        Layout.addWidget(self.dropDown, 1, 1, 1, 1)
        # Connection
        if checkbox:
            self.checkbox.stateChanged.connect(self.check_state)
            # Start disabled
            self.check_state(False)

    def check_state(self, checked):
        """
        Actions to take when checkbox is ticked/unticked
        Args:
            checked: bool
        """
        if checked:
            self.dropDown.setEnabled(True)
        else:
            self.dropDown.setEnabled(False)


class CustomFrame(QFrame):
    def __init__(self, label=None, parent=None):
        """
        Custom class inheriting from QFrame.
        This frame has a grey outline around it.
        Args:
            label: str, dedicated name for the frame
            parent: parent QWidget
        """
        super().__init__(parent)
        if label:
            self.setObjectName(label)
            outline = borderKey + grey + roundCorners
            self.setStyleSheet("#%s{%s} " % (label, outline))


class CustomScrollTab(QScrollArea):
    def __init__(self, parent=None):
        """
        Custom class inhereting from QScrollArea
        Args:
            parent: parent QWidget
        """
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.container = QWidget(self)
        self.setWidget(self.container)
        self.layout = QVBoxLayout(self.container)


class CustomPanelVLayout(QVBoxLayout):
    def __init__(self, widgets, parent):
        """
        Custom class inheriting from QVBoxLayout
        Args:
            widgets: list of QWidgets to add in order vertically to the layout
            parent: parent QWidget
        """
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft)
        for w in widgets:
            self.addWidget(w)
        self.stretch = self.addStretch(1)
        parent.setLayout(self)


class CustomPanelGridLayout(QGridLayout):
    def __init__(self, widgets, parent):
        """
        Custom class inheriting from QGridLayout
        Args:
            widgets: list of QWidgets to add in a specific order to the layout
            parent: parent QWidget
        """
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft)
        self.addWidget(widgets[0], 0, 0, 1, 2)
        self.addWidget(widgets[1], 1, 0)
        self.addWidget(widgets[2], 2, 0)
        self.addWidget(widgets[3], 1, 1)
        self.addWidget(widgets[4], 2, 1)
        parent.setLayout(self)


class CustomPanelGridLayout2(QGridLayout):
    def __init__(self, widgets, parent):
        """
        Custom class inheriting from QGridLayout
        Args:
            widgets: list of QWidgets to add in a specific order to the layout
            parent: parent QWidget
        """
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft)

        self.addWidget(widgets[0], 0, 0, 1, 2)
        self.addWidget(widgets[1], 1, 0, 1, 2)
        self.addWidget(widgets[2], 2, 0)
        self.addWidget(widgets[3], 3, 0)
        self.addWidget(widgets[4], 2, 1)
        self.addWidget(widgets[5], 3, 1)
        parent.setLayout(self)


class CustomDialogBox(QWidget):
    """
    Custom class creating pop-up message window leveraging QMessageBox
    """
    def __init__(self, message):
        super().__init__()
        self.setWindowIcon(QIcon(iconUHDAS))
        # move to screen center
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        widget_geometry = self.geometry()
        x = int((screen_geometry.width() / 2) - (widget_geometry.width() / 2))
        y = int((screen_geometry.height() / 2))  # + (widget_geometry.height() / 2))
        self.move(x, y)
        # Show a message box
        result = QMessageBox.question(
            self, '---WARNING---', message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)
        if result == QMessageBox.Yes:
            self.answer = True
        else:
            self.answer = False


class CustomInfoBox(QWidget):
    """
    Custom class creating pop-up message window leveraging QMessageBox
    """
    def __init__(self, message):
        super().__init__()
        self.setWindowIcon(QIcon(iconUHDAS))
        # Show a message box
        QMessageBox.information(
            self, '---INFO---', message, QMessageBox.Ok, QMessageBox.Ok)


class ConsoleWidget(RichJupyterWidget):
    """
    Code base borrowed from:
    https://stackoverflow.com/questions/11513132/embedding-ipython-qt-console-in-a-pyqt-application
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        msg = "\nThe following variables/models are cached in memory:\n"
        self.font_size = 6
        self.kernel_manager = kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel()
        kernel_manager.kernel.gui = 'qt'
        kernel_manager.kernel.shell.banner1 += msg
        self.kernel_client = kernel_client = self._kernel_manager.client()
        kernel_client.start_channels()

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()
            guisupport.get_app_qt().exit()

        self.exit_requested.connect(stop)

    def kick_start(self):
        """
        Set default behavior
        """
        # Print the variables in namespace (see msg above)
        self.execute_command('whos')
        # Import pylab functionality
        self.execute_command('%pylab')

    def push_vars(self, variableDict):
        """
        Given a dictionary containing name / value pairs, push those variables
        to the Jupyter console widget
        """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clear(self):
        """
        Clears the terminal
        """
        self._control.clear()

    def print_text(self, text):
        """
        Prints some plain text to the console
        """
        # FIXME - does not seem to work
        self._append_plain_text(text)

    def execute_command(self, command):
        """
        Execute a command in the frame of the console widget
        """
        self._execute(command, False)


class CruisenameValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        """
        Regular expression based validator for cruise names.
        Criterion:
         - upper or lower case letters or digits
         - no special characters but "_" and "-"
        Args:
            parent: parent QWidget
        """
        rx = QRegularExpression("^[A-Za-z0-9_-]*$")
        super().__init__(rx, parent=parent)


class FileNameValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        """
        Regular expression based validator for file names.
        Criterion:
         - upper or lower case letters or digits
         - no special characters but "_", "-", "/" and "."
        Args:
            parent: parent QWidget
        """
        rx = QRegularExpression("^[A-Za-z0-9_-/.]*$")
        super().__init__(rx, parent=parent)


class DBNameValidator(QRegularExpressionValidator):
    def __init__(self, parent=None):
        """
        Regular expression based validator for database names.
        Criterion:
         - upper or lower case letters or digits
         - no special characters but "_"
         - starts with "a"
        Args:
            parent: parent QWidget
        """
        rx = QRegularExpression("^[a][A-Za-z0-9_]{1,15}$")
        super().__init__(rx, parent=parent)


class CustomSeparator(QFrame):
    def __init__(self, parent=None):
        """
        Custom class creating a separation on the GUI
        Args:
            parent: PySide6 or PyQt5 parent widget
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)

### Custom Decorators ###
def waiting_cursor(func):
    """
    Changes mouse cursor to hour glass when func running. Decorator.

    Args:
        func: python function
    """
    @wraps(func)
    def func_wrapper(*args, **kwargs):
        make_busy_cursor()
        try:
            func(*args, **kwargs)
        except:  # Super permissive in purpose
            restore_cursor()
            raise
        else:
            restore_cursor()

    func_wrapper.__wrapped__ = func
    return func_wrapper


def waitingNinactive_cursor(func):
    """
    Changes mouse cursor to inactive hour glass when func running. Decorator.

    Args:
        func: python function
    """
    @wraps(func)
    def func_wrapper(controlWin, *args, **kwargs):
        make_busy_cursor()
        try:
            func(controlWin, *args, **kwargs)
        finally:
            restore_cursor()

    func_wrapper.__wrapped__ = func
    return func_wrapper


### Local lib
def make_busy_cursor():
    QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))


def restore_cursor():
    QApplication.restoreOverrideCursor()



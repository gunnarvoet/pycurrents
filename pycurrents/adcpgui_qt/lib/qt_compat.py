"""
This is essentially a stripped down version of matplotlib's qt compat
https://github.com/matplotlib/matplotlib/blob/c4ff4736c4f42d75b8d740b93e02f24fa5ef560f/lib/matplotlib/backends/qt_compat.py
it handles importing the correct version of Qt, either PyQt5 or Pyside6
the script also regularizes the API presented by the Qt provider
"""

import os
import sys

QT_API_PYSIDE6 = "PySide6"
QT_API_PYQT5 = "PyQt5"
QT_API_ENV = os.environ.get("QT_API", "")

# Check if there's already a provider imported
if "PySide6.QtCore" in sys.modules:
    QT_API = QT_API_PYSIDE6
elif "PyQt5.QtCore" in sys.modules:
    QT_API = QT_API_PYQT5
# If no provider is imported already check env var
elif QT_API_ENV.lower() in ["pyside6", "pyqt5"]:
    QT_API = QT_API_ENV
# Default to pyside6 if it's present otherwise us PyQt5
else:
    try:
        import PySide6  # noqa: F401
        QT_API = QT_API_PYSIDE6
    except ModuleNotFoundError:
        try:
            import PyQt5  # noqa: F401
            QT_API = QT_API_PYQT5
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "A suitable Qt provider was not found. Please install either PyQt5 or PySide6"
            )

if QT_API.lower() == QT_API_PYSIDE6.lower():
    from PySide6 import QtCore, QtGui, QtWidgets

elif QT_API.lower() == QT_API_PYQT5.lower():
    from PyQt5 import QtCore, QtGui, QtWidgets

    QtGui.QRegularExpressionValidator = QtGui.QRegExpValidator
    QtGui.QShortcut = QtWidgets.QShortcut
    QtGui.QAction = QtWidgets.QAction
    QtWidgets.QApplication(sys.argv)
    QtCore.Signal = QtCore.pyqtSignal
    QtCore.Slot = QtCore.pyqtSlot
    QtCore.Property = QtCore.pyqtProperty
    QtCore.QRegularExpression = QtCore.QRegExp

else:
    raise ImportError(f"Unsupported QT_API: {QT_API}")

# Explicitly expose these as module-level objects to allow `from qt_compat.QtWidgets import QPushButton`
sys.modules["pycurrents.adcpgui_qt.lib.qt_compat.QtCore"] = QtCore
sys.modules["pycurrents.adcpgui_qt.lib.qt_compat.QtGui"] = QtGui
sys.modules["pycurrents.adcpgui_qt.lib.qt_compat.QtWidgets"] = QtWidgets

__all__ = ["QtCore", "QtGui", "QtWidgets"]

from __future__ import annotations

import sys

from PySide6 import QtGui, QtWidgets

from .gui.main_window import MainWindow
from .gui.style import STYLE


def light_palette() -> QtGui.QPalette:
    palette = QtGui.QPalette()
    colors = {
        QtGui.QPalette.ColorRole.Window: "#f4f8f8",
        QtGui.QPalette.ColorRole.WindowText: "#172528",
        QtGui.QPalette.ColorRole.Base: "#ffffff",
        QtGui.QPalette.ColorRole.AlternateBase: "#f3f7f7",
        QtGui.QPalette.ColorRole.Text: "#172528",
        QtGui.QPalette.ColorRole.Button: "#ffffff",
        QtGui.QPalette.ColorRole.ButtonText: "#172528",
        QtGui.QPalette.ColorRole.Highlight: "#d9ecee",
        QtGui.QPalette.ColorRole.HighlightedText: "#285f66",
        QtGui.QPalette.ColorRole.PlaceholderText: "#7b8c8e",
    }
    for role, color in colors.items():
        palette.setColor(role, QtGui.QColor(color))
    return palette


def main() -> int:
    # QOpenGLWidget requires its core-profile format before QApplication exists.
    # Keep startup usable enough to report optional viewer dependency problems in
    # Stage 2 rather than failing before the main window appears.
    try:
        from .gui.molecular_viewer_3d import configure_opengl

        configure_opengl()
    except ImportError:
        pass
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Scymol")
    app.setOrganizationName("Scymol")
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()

"""Toolbar for the molecule drawer widget."""

import math

from PySide6 import QtCore, QtGui, QtWidgets


ATOM_COLORS = {
    "C": QtGui.QColor(25, 25, 25),
    "O": QtGui.QColor(25, 25, 25),
    "N": QtGui.QColor(25, 25, 25),
    "S": QtGui.QColor(25, 25, 25),
    "H": QtGui.QColor(25, 25, 25),
}

ICON_BLACK = QtGui.QColor(25, 25, 25)


class SketchToolBar(QtWidgets.QToolBar):
    symSelected = QtCore.Signal(str)
    clearClicked = QtCore.Signal()
    copySmilesClicked = QtCore.Signal()
    pasteSmilesClicked = QtCore.Signal()
    savePngClicked = QtCore.Signal()
    saveSvgClicked = QtCore.Signal()
    cleanClicked = QtCore.Signal()
    undoClicked = QtCore.Signal()
    chainModeSelected = QtCore.Signal(bool)
    unitedAtomToggled = QtCore.Signal(bool)
    snapGridClicked = QtCore.Signal()
    cyclohexaneModeSelected = QtCore.Signal(bool)
    benzeneModeSelected = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(22, 22))
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setStyleSheet(
            """
            QToolBar {
                spacing: 4px;
                padding: 6px;
                border: 0;
                background: #f6f7f7;
            }
            QToolButton {
                min-width: 30px;
                min-height: 28px;
                padding: 3px;
                border: 1px solid transparent;
                border-radius: 5px;
                background: transparent;
            }
            QToolButton:hover {
                border-color: #cfd6d6;
                background: #ffffff;
            }
            QToolButton:checked {
                border-color: #83b9bf;
                background: #dceff0;
            }
            QToolButton:pressed {
                background: #cfe4e6;
            }
            """
        )

        self.atom_group = QtWidgets.QButtonGroup(self)
        self.atom_group.setExclusive(True)

        for sym in ["C", "O", "N", "S", "H"]:
            button = self._make_tool_button(
                text=sym,
                tooltip=f"Atom: {sym}",
                icon=self._text_icon(sym, ATOM_COLORS[sym]),
                checkable=True,
            )
            button.clicked.connect(lambda _, s=sym: self.symSelected.emit(s))
            self.atom_group.addButton(button)
            self.addWidget(button)

            if sym == "C":
                button.setChecked(True)

        self.addSeparator()

        self.chain_btn = self._make_tool_button(
            text="Cn",
            tooltip="Draw carbon chain",
            icon=self._chain_icon(),
            checkable=True,
        )
        self.chain_btn.toggled.connect(self._chain_toggled)
        self.addWidget(self.chain_btn)

        self.cyclohexane_btn = self._make_tool_button(
            text="C6",
            tooltip="Place cyclohexane ring",
            icon=self._ring_icon(aromatic=False),
            checkable=True,
        )
        self.cyclohexane_btn.toggled.connect(self._cyclohexane_toggled)
        self.addWidget(self.cyclohexane_btn)

        self.benzene_btn = self._make_tool_button(
            text="c6",
            tooltip="Place aromatic six-membered ring",
            icon=self._ring_icon(aromatic=True),
            checkable=True,
        )
        self.benzene_btn.toggled.connect(self._benzene_toggled)
        self.addWidget(self.benzene_btn)

        self.united_atom_btn = self._make_tool_button(
            text="UA",
            tooltip="Toggle united atom labels",
            icon=self._text_icon("UA", ICON_BLACK, point_size=9),
            checkable=True,
        )
        self.united_atom_btn.toggled.connect(self.unitedAtomToggled.emit)
        self.addWidget(self.united_atom_btn)

        self.addSeparator()

        self.snap_grid_btn = self._make_tool_button(
            text="Grid",
            tooltip="Snap components to grid",
            icon=self._grid_icon(),
        )
        self.snap_grid_btn.clicked.connect(self.snapGridClicked.emit)
        self.addWidget(self.snap_grid_btn)

        for text, tooltip, icon, signal in [
            (
                "Copy",
                "Copy SMILES",
                self._smiles_icon(direction="out"),
                self.copySmilesClicked,
            ),
            (
                "Paste",
                "Paste SMILES",
                self._smiles_icon(direction="in"),
                self.pasteSmilesClicked,
            ),
            (
                "Clean",
                "Clean and arrange the sketch",
                self._text_icon("2D", ICON_BLACK, point_size=8),
                self.cleanClicked,
            ),
            (
                "PNG",
                "Save PNG",
                self._text_icon("PNG", ICON_BLACK, point_size=8),
                self.savePngClicked,
            ),
            (
                "SVG",
                "Save SVG",
                self._text_icon("SVG", ICON_BLACK, point_size=8),
                self.saveSvgClicked,
            ),
            (
                "Undo",
                "Undo",
                self._undo_icon(),
                self.undoClicked,
            ),
            (
                "Clear",
                "Clear sketch",
                self._clear_icon(),
                self.clearClicked,
            ),
        ]:
            button = self._make_tool_button(text=text, tooltip=tooltip, icon=icon)
            button.clicked.connect(signal.emit)
            self.addWidget(button)

    def _make_tool_button(self, text, tooltip, icon=None, checkable=False):
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.setAutoRaise(False)

        if icon is not None:
            button.setIcon(icon)

        return button

    @staticmethod
    def _text_icon(text, color, point_size=11):
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(color)
        font = QtGui.QFont("Arial", point_size, QtGui.QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _chain_icon():
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QtGui.QPen(
                ICON_BLACK,
                2.0,
                QtCore.Qt.PenStyle.SolidLine,
                QtCore.Qt.PenCapStyle.RoundCap,
            )
        )
        points = [
            QtCore.QPointF(4, 18),
            QtCore.QPointF(9, 10),
            QtCore.QPointF(15, 18),
            QtCore.QPointF(21, 10),
            QtCore.QPointF(25, 16),
        ]

        for first, second in zip(points, points[1:]):
            painter.drawLine(QtCore.QLineF(first, second))

        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _ring_icon(aromatic=False):
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(ICON_BLACK, 2.0))
        center = QtCore.QPointF(14, 14)
        radius = 9.0
        polygon = QtGui.QPolygonF(
            [
                QtCore.QPointF(
                    center.x() + radius * math.cos(math.radians(30 + i * 60)),
                    center.y() + radius * math.sin(math.radians(30 + i * 60)),
                )
                for i in range(6)
            ]
        )
        painter.drawPolygon(polygon)

        if aromatic:
            painter.setPen(QtGui.QPen(ICON_BLACK, 1.4))
            painter.drawEllipse(QtCore.QPointF(14, 14), 4.8, 4.8)

        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _grid_icon():
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(ICON_BLACK, 1.5))

        for x in (7, 14, 21):
            painter.drawLine(x, 5, x, 23)

        for y in (7, 14, 21):
            painter.drawLine(5, y, 23, y)

        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _smiles_icon(direction):
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QtGui.QPen(
                ICON_BLACK,
                1.7,
                QtCore.Qt.PenStyle.SolidLine,
                QtCore.Qt.PenCapStyle.RoundCap,
                QtCore.Qt.PenJoinStyle.RoundJoin,
            )
        )

        center = QtCore.QPointF(13, 14)
        radius = 7.5
        polygon = QtGui.QPolygonF(
            [
                QtCore.QPointF(
                    center.x() + radius * math.cos(math.radians(30 + i * 60)),
                    center.y() + radius * math.sin(math.radians(30 + i * 60)),
                )
                for i in range(6)
            ]
        )
        painter.drawPolygon(polygon)
        painter.drawPoint(QtCore.QPointF(10.5, 12.5))
        painter.drawPoint(QtCore.QPointF(15.5, 12.5))
        painter.drawArc(QtCore.QRectF(9.5, 11.5, 7.0, 7.0), 205 * 16, 130 * 16)

        if direction == "in":
            painter.drawLine(QtCore.QLineF(22, 8, 18, 12))
            painter.drawLine(QtCore.QLineF(22, 8, 22, 13))
            painter.drawLine(QtCore.QLineF(22, 8, 17, 8))
        else:
            painter.drawLine(QtCore.QLineF(18, 12, 22, 8))
            painter.drawLine(QtCore.QLineF(22, 8, 22, 13))
            painter.drawLine(QtCore.QLineF(22, 8, 17, 8))

        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _undo_icon():
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QtGui.QPen(
                ICON_BLACK,
                2.0,
                QtCore.Qt.PenStyle.SolidLine,
                QtCore.Qt.PenCapStyle.RoundCap,
                QtCore.Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawArc(QtCore.QRectF(7, 8, 15, 13), 25 * 16, 250 * 16)
        painter.drawLine(QtCore.QLineF(8, 14, 4, 10))
        painter.drawLine(QtCore.QLineF(8, 14, 12, 10))
        painter.end()
        return QtGui.QIcon(pixmap)

    @staticmethod
    def _clear_icon():
        pixmap = QtGui.QPixmap(28, 28)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(
            QtGui.QPen(
                ICON_BLACK,
                2.0,
                QtCore.Qt.PenStyle.SolidLine,
                QtCore.Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(QtCore.QLineF(9, 9, 19, 19))
        painter.drawLine(QtCore.QLineF(19, 9, 9, 19))
        painter.end()
        return QtGui.QIcon(pixmap)

    def _chain_toggled(self, checked):
        if checked and self.cyclohexane_btn.isChecked():
            self.cyclohexane_btn.blockSignals(True)
            self.cyclohexane_btn.setChecked(False)
            self.cyclohexane_btn.blockSignals(False)
            self.cyclohexaneModeSelected.emit(False)

        if checked and self.benzene_btn.isChecked():
            self.benzene_btn.blockSignals(True)
            self.benzene_btn.setChecked(False)
            self.benzene_btn.blockSignals(False)
            self.benzeneModeSelected.emit(False)

        self.chainModeSelected.emit(checked)

    def _cyclohexane_toggled(self, checked):
        if checked and self.chain_btn.isChecked():
            self.chain_btn.blockSignals(True)
            self.chain_btn.setChecked(False)
            self.chain_btn.blockSignals(False)
            self.chainModeSelected.emit(False)

        if checked and self.benzene_btn.isChecked():
            self.benzene_btn.blockSignals(True)
            self.benzene_btn.setChecked(False)
            self.benzene_btn.blockSignals(False)
            self.benzeneModeSelected.emit(False)

        self.cyclohexaneModeSelected.emit(checked)

    def _benzene_toggled(self, checked):
        if checked and self.chain_btn.isChecked():
            self.chain_btn.blockSignals(True)
            self.chain_btn.setChecked(False)
            self.chain_btn.blockSignals(False)
            self.chainModeSelected.emit(False)

        if checked and self.cyclohexane_btn.isChecked():
            self.cyclohexane_btn.blockSignals(True)
            self.cyclohexane_btn.setChecked(False)
            self.cyclohexane_btn.blockSignals(False)
            self.cyclohexaneModeSelected.emit(False)

        self.benzeneModeSelected.emit(checked)

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6 import QtCore, QtWidgets

from ..analysis import NumericDataset, column_statistics, downsample_xy


class DataPlotWidget(QtWidgets.QWidget):
    """Compact numeric-table and plotting workspace for one simulation result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataset: NumericDataset | None = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        controls = QtWidgets.QHBoxLayout()
        self.x_column = QtWidgets.QComboBox()
        self.y_column = QtWidgets.QComboBox()
        self.chart_type = QtWidgets.QComboBox()
        self.chart_type.addItem("Line", "line")
        self.chart_type.addItem("Scatter", "scatter")
        controls.addWidget(QtWidgets.QLabel("X"))
        controls.addWidget(self.x_column, 1)
        controls.addWidget(QtWidgets.QLabel("Y"))
        controls.addWidget(self.y_column, 1)
        controls.addWidget(self.chart_type)
        root.addLayout(controls)

        self.summary = QtWidgets.QLabel("Select a numeric result file.")
        self.summary.setObjectName("note")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.table = QtWidgets.QTableWidget()
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        splitter.addWidget(self.table)

        plot_container = QtWidgets.QWidget()
        plot_layout = QtWidgets.QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(7, 5), constrained_layout=True)
        self.figure.patch.set_facecolor("white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas, 1)
        splitter.addWidget(plot_container)
        splitter.setSizes([390, 760])
        root.addWidget(splitter, 1)

        self.x_column.currentIndexChanged.connect(self._redraw)
        self.y_column.currentIndexChanged.connect(self._redraw)
        self.chart_type.currentIndexChanged.connect(self._redraw)

    def set_loading(self, path):
        self.dataset = None
        self.summary.setText(f"Reading numeric data from {path.name}…")
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.figure.clear()
        self.canvas.draw_idle()

    def set_dataset(self, dataset: NumericDataset):
        self.dataset = dataset
        self._populate_table()
        self.x_column.blockSignals(True)
        self.y_column.blockSignals(True)
        self.x_column.clear()
        self.y_column.clear()
        for name in dataset.columns:
            self.x_column.addItem(name, name)
            self.y_column.addItem(name, name)
        preferred_x = self._preferred_x(dataset.columns)
        self.x_column.setCurrentIndex(dataset.columns.index(preferred_x))
        preferred_y = next(
            (name for name in dataset.columns if name != preferred_x),
            dataset.columns[-1],
        )
        self.y_column.setCurrentIndex(dataset.columns.index(preferred_y))
        self.x_column.blockSignals(False)
        self.y_column.blockSignals(False)
        self._redraw()

    def _populate_table(self):
        if self.dataset is None:
            return
        maximum_rows = 2000
        shown = min(len(self.dataset.values), maximum_rows)
        self.table.setColumnCount(len(self.dataset.columns))
        self.table.setHorizontalHeaderLabels(self.dataset.columns)
        self.table.setRowCount(shown)
        for row in range(shown):
            for column, value in enumerate(self.dataset.values[row]):
                self.table.setItem(
                    row, column, QtWidgets.QTableWidgetItem(f"{value:.8g}")
                )
        self.table.resizeColumnsToContents()

    @staticmethod
    def _preferred_x(columns):
        for candidate in ("Step", "TimeStep", "Timestep", "Time", "time"):
            if candidate in columns:
                return candidate
        return columns[0]

    def _redraw(self, *_):
        if self.dataset is None or not self.x_column.count() or not self.y_column.count():
            return
        x_name = self.x_column.currentData()
        y_name = self.y_column.currentData()
        if not x_name or not y_name:
            return
        x, y = downsample_xy(
            self.dataset.column(x_name), self.dataset.column(y_name)
        )
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.set_facecolor("#fbfcfc")
        axes.grid(True, color="#d9e3e4", linewidth=0.7, alpha=0.9)
        if self.chart_type.currentData() == "scatter":
            axes.scatter(x, y, s=12, alpha=0.8, color="#4b8a92")
        else:
            axes.plot(x, y, linewidth=1.25, color="#4b8a92")
        axes.set_title(self.dataset.path.name)
        axes.set_xlabel(x_name)
        axes.set_ylabel(y_name)
        self.canvas.draw_idle()

        stats = column_statistics(self.dataset.column(y_name))
        table_note = (
            f" · table shows first 2,000/{len(self.dataset.values):,} rows"
            if len(self.dataset.values) > 2000
            else ""
        )
        self.summary.setText(
            f"{self.dataset.path.name} · {y_name}: n={stats['count']:,}, "
            f"mean={stats['mean']:.6g}, σ={stats['std']:.6g}, "
            f"min={stats['min']:.6g}, max={stats['max']:.6g}{table_note}"
        )

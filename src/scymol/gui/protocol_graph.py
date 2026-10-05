from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..lammps import generate_protocol_script
from ..models import ProtocolEdge, ProtocolGraph, ProtocolNode
from ..protocol import (
    default_protocol,
    load_protocol_preset,
    parse_loop_values,
    protocol_paths,
    save_protocol_preset,
    topological_nodes,
    validate_graph,
    validate_loop_expression,
)
from ..schemas import NODE_SCHEMAS, coerce_value, default_parameters
from .base import StagePage


NODE_WIDTH = 184
NODE_HEIGHT = 82

ADVANCED_FIELDS = {
    "Initialization": {
        "pair_modify", "kspace_style", "bond_style", "angle_style",
        "dihedral_style", "improper_style", "special_bonds",
    },
    "Minimization": {
        "energy_tolerance", "force_tolerance", "dmax", "thermo_every", "dump_every",
    },
    "Velocities": {"distribution", "momentum", "rotation"},
    "NVT": {"temperature_damping", "drag", "thermo_every", "dump_every"},
    "NPT": {
        "temperature_damping", "pressure_damping", "drag", "thermo_every",
        "dump_every", "set_cubic",
    },
    "NVE": {"thermo_every", "dump_every"},
    "Deformation": {
        "deform_every", "temperature_damping", "drag", "wall_skin",
        "wall_force_constant", "thermo_every", "dump_every", "average_every",
        "average_repeats", "average_frequency",
    },
}

FIELD_HELP = {
    "timestep": "Integration timestep. In LAMMPS real units this is femtoseconds.",
    "steps": "Number of integration steps in this protocol stage.",
    "temperature_start": "Target temperature at the start of this stage.",
    "temperature_end": "Target temperature at the end of this stage.",
    "temperature": "Temperature used to create the velocity distribution.",
    "temperature_damping": "Thermostat relaxation time; normally many timesteps.",
    "pressure_start": "Target pressure at the start of this stage.",
    "pressure_end": "Target pressure at the end of this stage.",
    "pressure_damping": "Barostat relaxation time; normally longer than thermostat damping.",
    "thermo_every": "Write thermodynamic output every N steps.",
    "dump_every": "Write a trajectory frame every N steps.",
    "random_seed": "Positive seed controlling the generated velocities.",
    "structure_data": "LAMMPS data file read by this protocol.",
    "stop_at": (
        "Automatically derive a signed strain rate so the usable length along the "
        "deformation axis matches the first transverse box dimension at the end of the run."
    ),
    "strain_style": "True strain uses trate; engineering strain uses erate.",
    "deform_every": "Apply the box deformation every N timesteps.",
    "wall_skin": "Offset of each compression wall from the box boundary.",
    "wall_force_constant": "LAMMPS fix-indent force constant for both compression walls.",
    "average_every": "Sample deformation properties every N timesteps.",
    "average_repeats": "Number of samples combined into each deformation output row.",
    "average_frequency": "Write averaged deformation properties every N timesteps.",
}

POSITIVE_FIELDS = {
    "timestep", "steps", "temperature", "temperature_start", "temperature_end",
    "temperature_damping", "pressure_damping", "thermo_every", "dump_every",
    "deform_every", "random_seed", "max_iterations", "max_evaluations", "dmax",
    "wall_skin",
    "wall_force_constant", "average_every", "average_repeats", "average_frequency",
}


class EdgeItem(QtWidgets.QGraphicsPathItem):
    def __init__(self, source: "NodeItem", target: "NodeItem | None" = None):
        super().__init__()
        self.source = source
        self.target = target
        self.temporary_end: QtCore.QPointF | None = None
        self.setZValue(-5)
        self.setPen(QtGui.QPen(QtGui.QColor("#94b4b8"), 2.4))
        self.setAcceptHoverEvents(True)
        self.arrow = QtWidgets.QGraphicsPolygonItem(self)
        self.arrow.setBrush(QtGui.QBrush(QtGui.QColor("#94b4b8")))
        self.arrow.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
        source.out_edges.append(self)
        if target:
            target.in_edges.append(self)
        self.update_path()

    def update_path(self):
        start = self.source.output_pos()
        end = self.target.input_pos() if self.target else (self.temporary_end or start + QtCore.QPointF(80, 0))
        offset = max(65.0, abs(end.x() - start.x()) * 0.45)
        path = QtGui.QPainterPath(start)
        path.cubicTo(
            QtCore.QPointF(start.x() + offset, start.y()),
            QtCore.QPointF(end.x() - offset, end.y()),
            end,
        )
        self.setPath(path)
        angle = path.angleAtPercent(1.0)
        radians = angle * 3.141592653589793 / 180.0
        direction = QtCore.QPointF(__import__("math").cos(radians), -__import__("math").sin(radians))
        normal = QtCore.QPointF(-direction.y(), direction.x())
        base = end - direction * 12
        self.arrow.setPolygon(QtGui.QPolygonF([end, base + normal * 5, base - normal * 5]))

    def hoverEnterEvent(self, event):
        self.setPen(QtGui.QPen(QtGui.QColor("#d26868"), 3))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setPen(QtGui.QPen(QtGui.QColor("#94b4b8"), 2.4))
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event):
        action = QtGui.QAction("Delete connection")
        menu = QtWidgets.QMenu()
        menu.addAction(action)
        if menu.exec(event.screenPos()) == action:
            self.scene().delete_edge(self)


class OutputSocket(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, node: "NodeItem"):
        super().__init__(-7, -7, 14, 14, node)
        self.node = node
        self.setPos(NODE_WIDTH / 2, 0)
        self.setBrush(QtGui.QColor("#4b8a92"))
        self.setPen(QtGui.QPen(QtGui.QColor("#326d74"), 1.5))
        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event):
        self.scene().begin_edge(self.node, self.mapToScene(event.pos()))
        event.accept()

    def mouseMoveEvent(self, event):
        self.scene().move_edge(self.mapToScene(event.pos()))
        event.accept()

    def mouseReleaseEvent(self, event):
        self.scene().finish_edge(self.mapToScene(event.pos()))
        event.accept()


class NodeItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, model: ProtocolNode):
        super().__init__(-NODE_WIDTH / 2, -NODE_HEIGHT / 2, NODE_WIDTH, NODE_HEIGHT)
        self.model = model
        self.execution_index: int | None = None
        self.in_edges: list[EdgeItem] = []
        self.out_edges: list[EdgeItem] = []
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setPen(QtGui.QPen(QtGui.QColor("#657d80"), 1.5))
        self.setBrush(QtGui.QColor(NODE_SCHEMAS[model.kind]["color"]))
        self.loop_border = QtWidgets.QGraphicsRectItem(
            self.rect().adjusted(-6, -6, 6, 6), self
        )
        loop_pen = QtGui.QPen(QtGui.QColor("#4b8a92"), 2.2)
        loop_pen.setStyle(QtCore.Qt.PenStyle.DashLine)
        self.loop_border.setPen(loop_pen)
        self.loop_border.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
        self.loop_border.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.loop_border.setZValue(-1)
        self.title = QtWidgets.QGraphicsTextItem(self)
        self.title.setDefaultTextColor(QtGui.QColor("#172321"))
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.kind_label = QtWidgets.QGraphicsTextItem(self)
        self.kind_label.setDefaultTextColor(QtGui.QColor("#536b6e"))
        self.loop_badge = QtWidgets.QGraphicsTextItem(self)
        self.loop_badge.setDefaultTextColor(QtGui.QColor("#2f747c"))
        badge_font = self.loop_badge.font()
        badge_font.setBold(True)
        badge_font.setPointSizeF(max(7.0, badge_font.pointSizeF() - 1.0))
        self.loop_badge.setFont(badge_font)
        self.input_marker = QtWidgets.QGraphicsEllipseItem(-6, -6, 12, 12, self)
        self.input_marker.setPos(-NODE_WIDTH / 2, 0)
        self.input_marker.setBrush(QtGui.QColor("#f9fbfa"))
        self.input_marker.setPen(QtGui.QPen(QtGui.QColor("#657d80"), 1.2))
        self.output_socket = OutputSocket(self)
        self.refresh()

    def refresh(self):
        prefix = f"{self.execution_index:02d}  " if self.execution_index else ""
        self.title.setPlainText(prefix + self.model.name)
        self.kind_label.setPlainText(self.model.kind)
        self.title.setPos(-self.title.boundingRect().width() / 2, -31)
        self.kind_label.setPos(-self.kind_label.boundingRect().width() / 2, 4)
        try:
            loop_count = len(parse_loop_values(self.model.loop_values))
        except ValueError:
            loop_count = 0
        self.loop_badge.setPlainText(f"↻ i ×{loop_count}" if loop_count else "↻ i")
        self.loop_badge.setPos(
            NODE_WIDTH / 2 - self.loop_badge.boundingRect().width() - 5,
            NODE_HEIGHT / 2 - self.loop_badge.boundingRect().height() - 2,
        )
        self.loop_border.setVisible(self.model.loop_enabled)
        self.loop_badge.setVisible(self.model.loop_enabled)
        self.setBrush(QtGui.QColor(NODE_SCHEMAS[self.model.kind]["color"]))

    def set_execution_index(self, index: int):
        self.execution_index = index
        self.refresh()

    def input_pos(self):
        return self.input_marker.mapToScene(self.input_marker.rect().center())

    def output_pos(self):
        return self.output_socket.mapToScene(self.output_socket.rect().center())

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.setPen(
                QtGui.QPen(
                    QtGui.QColor("#4b8a92") if bool(value) else QtGui.QColor("#657d80"),
                    3.2 if bool(value) else 1.5,
                )
            )
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.model.x, self.model.y = value.x(), value.y()
            for edge in self.in_edges + self.out_edges:
                edge.update_path()
            scene = self.scene()
            if scene and not scene.loading:
                scene.graphChanged.emit()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        duplicate = menu.addAction("Duplicate node")
        delete = menu.addAction("Delete node")
        selected = menu.exec(event.screenPos())
        if selected == duplicate:
            self.scene().duplicate_node(self)
        elif selected == delete:
            self.scene().delete_node(self)


class GraphScene(QtWidgets.QGraphicsScene):
    graphChanged = QtCore.Signal()
    nodeSelected = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-2500, -1800, 5000, 3600)
        self.setBackgroundBrush(QtGui.QColor("#27383b"))
        self.graph = ProtocolGraph()
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self.dragging_edge: EdgeItem | None = None
        self.loading = False
        self.selectionChanged.connect(self._selection_changed)
        self.graphChanged.connect(self.refresh_stage_numbers)

    def load_graph(self, graph: ProtocolGraph):
        self.loading = True
        self.clear()
        self.graph = graph
        self.node_items = {}
        self.edge_items = []
        for node in graph.nodes:
            item = NodeItem(node)
            item.setPos(node.x, node.y)
            self.addItem(item)
            self.node_items[node.id] = item
        for edge in list(graph.edges):
            if edge.source in self.node_items and edge.target in self.node_items:
                item = EdgeItem(self.node_items[edge.source], self.node_items[edge.target])
                self.addItem(item)
                self.edge_items.append(item)
        self.loading = False
        self.refresh_stage_numbers()

    def refresh_stage_numbers(self):
        try:
            ordered = topological_nodes(self.graph)
        except ValueError:
            ordered = sorted(self.graph.nodes, key=lambda node: (node.y, node.x))
        for index, node in enumerate(ordered, start=1):
            item = self.node_items.get(node.id)
            if item is not None:
                item.set_execution_index(index)

    def add_node(self, kind: str, position: QtCore.QPointF | None = None):
        position = position or QtCore.QPointF(len(self.graph.nodes) * 35, len(self.graph.nodes) * 25)
        node = ProtocolNode(kind=kind, name=kind, parameters=default_parameters(kind), x=position.x(), y=position.y())
        self.graph.nodes.append(node)
        item = NodeItem(node)
        item.setPos(position)
        self.addItem(item)
        self.node_items[node.id] = item
        self.clearSelection()
        item.setSelected(True)
        self.graphChanged.emit()
        return item

    def duplicate_node(self, item: NodeItem):
        node = ProtocolNode(
            kind=item.model.kind,
            name=item.model.name + " copy",
            parameters=dict(item.model.parameters),
            loop_enabled=item.model.loop_enabled,
            loop_values=item.model.loop_values,
            loop_expressions=dict(item.model.loop_expressions),
            x=item.pos().x() + 35,
            y=item.pos().y() + 110,
        )
        self.graph.nodes.append(node)
        duplicate = NodeItem(node)
        duplicate.setPos(node.x, node.y)
        self.addItem(duplicate)
        self.node_items[node.id] = duplicate
        self.graphChanged.emit()

    def delete_node(self, item: NodeItem):
        for edge in list(item.in_edges + item.out_edges):
            self.delete_edge(edge, emit=False)
        self.graph.nodes = [node for node in self.graph.nodes if node.id != item.model.id]
        self.node_items.pop(item.model.id, None)
        self.removeItem(item)
        self.graphChanged.emit()

    def delete_selected(self):
        for item in list(self.selectedItems()):
            if isinstance(item, NodeItem):
                self.delete_node(item)

    def delete_edge(self, item: EdgeItem, emit=True):
        if item in item.source.out_edges:
            item.source.out_edges.remove(item)
        if item.target and item in item.target.in_edges:
            item.target.in_edges.remove(item)
        if item in self.edge_items:
            self.edge_items.remove(item)
        self.graph.edges = [
            edge for edge in self.graph.edges
            if not (edge.source == item.source.model.id and item.target and edge.target == item.target.model.id)
        ]
        self.removeItem(item)
        if emit:
            self.graphChanged.emit()

    def begin_edge(self, source: NodeItem, position: QtCore.QPointF):
        self.dragging_edge = EdgeItem(source)
        self.dragging_edge.temporary_end = position
        self.addItem(self.dragging_edge)
        self.dragging_edge.update_path()

    def move_edge(self, position: QtCore.QPointF):
        if self.dragging_edge:
            self.dragging_edge.temporary_end = position
            self.dragging_edge.update_path()

    def finish_edge(self, position: QtCore.QPointF):
        edge = self.dragging_edge
        self.dragging_edge = None
        if not edge:
            return
        target = self.node_at(position)
        valid = (
            target is not None
            and target is not edge.source
            and not target.in_edges
            and not self._path_exists(target.model.id, edge.source.model.id)
        )
        if valid:
            edge.target = target
            target.in_edges.append(edge)
            edge.temporary_end = None
            self.edge_items.append(edge)
            self.graph.edges.append(ProtocolEdge(edge.source.model.id, target.model.id))
            edge.update_path()
            self.graphChanged.emit()
        else:
            if edge in edge.source.out_edges:
                edge.source.out_edges.remove(edge)
            self.removeItem(edge)

    def node_at(self, position: QtCore.QPointF):
        for item in self.items(position):
            while item:
                if isinstance(item, NodeItem):
                    return item
                item = item.parentItem()
        return None

    def _path_exists(self, source_id: str, target_id: str) -> bool:
        adjacency: dict[str, list[str]] = {node.id: [] for node in self.graph.nodes}
        for edge in self.graph.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        stack = [source_id]
        seen = set()
        while stack:
            current = stack.pop()
            if current == target_id:
                return True
            if current not in seen:
                seen.add(current)
                stack.extend(adjacency.get(current, []))
        return False

    def _selection_changed(self):
        selected = [item for item in self.selectedItems() if isinstance(item, NodeItem)]
        self.nodeSelected.emit(selected[0] if selected else None)


class GraphView(QtWidgets.QGraphicsView):
    def __init__(self, scene: GraphScene):
        super().__init__(scene)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        self.scale(1.15 if event.angleDelta().y() > 0 else 1 / 1.15, 1.15 if event.angleDelta().y() > 0 else 1 / 1.15)


class NodeInspector(QtWidgets.QWidget):
    nodeChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        title = QtWidgets.QLabel("Node inspector")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        self.description = QtWidgets.QLabel("Select a protocol node to edit it.")
        self.description.setWordWrap(True)
        root.addWidget(self.description)
        self.validation = QtWidgets.QLabel("")
        self.validation.setObjectName("inlineValidation")
        self.validation.setWordWrap(True)
        self.validation.setVisible(False)
        root.addWidget(self.validation)
        self.form_widget = QtWidgets.QWidget()
        forms_layout = QtWidgets.QVBoxLayout(self.form_widget)
        forms_layout.setContentsMargins(0, 0, 0, 0)
        self.common_widget = QtWidgets.QWidget()
        self.form = QtWidgets.QFormLayout(self.common_widget)
        forms_layout.addWidget(self.common_widget)
        self.advanced_toggle = QtWidgets.QToolButton()
        self.advanced_toggle.setText("Advanced settings")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.advanced_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        forms_layout.addWidget(self.advanced_toggle)
        self.advanced_widget = QtWidgets.QWidget()
        self.advanced_form = QtWidgets.QFormLayout(self.advanced_widget)
        self.advanced_form.setContentsMargins(10, 0, 0, 0)
        self.advanced_widget.setVisible(False)
        forms_layout.addWidget(self.advanced_widget)
        forms_layout.addStretch()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self.form_widget)
        root.addWidget(scroll, 1)
        preview_title = QtWidgets.QLabel("Generated node script")
        preview_title.setObjectName("sectionTitle")
        root.addWidget(preview_title)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setObjectName("scriptPreview")
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(190)
        root.addWidget(self.preview)
        self.item: NodeItem | None = None
        self.editors = {}
        self.expression_editors = {}
        self.expression_buttons = {}
        self.loop_checkbox: QtWidgets.QCheckBox | None = None
        self.loop_values_editor: QtWidgets.QLineEdit | None = None
        self.loop_note: QtWidgets.QLabel | None = None
        self.units = "real"
        self.advanced_toggle.toggled.connect(self._toggle_advanced)

    def set_units(self, units: str):
        self.units = units or "real"

    def _toggle_advanced(self, expanded: bool):
        self.advanced_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        self.advanced_widget.setVisible(expanded)

    def set_node(self, item: NodeItem | None):
        self.item = item
        for form in (self.form, self.advanced_form):
            while form.rowCount():
                form.removeRow(0)
        self.editors = {}
        self.expression_editors = {}
        self.expression_buttons = {}
        self.loop_checkbox = None
        self.loop_values_editor = None
        self.loop_note = None
        if not item:
            self.description.setText("Select a protocol node to edit it.")
            self.preview.clear()
            self.validation.setVisible(False)
            self.advanced_toggle.setVisible(False)
            return
        node = item.model
        self.description.setText(NODE_SCHEMAS[node.kind]["description"])
        self.advanced_toggle.setVisible(bool(ADVANCED_FIELDS.get(node.kind)))
        self.advanced_toggle.setChecked(False)
        name = QtWidgets.QLineEdit(node.name)
        name.textChanged.connect(self._name_changed)
        self.form.addRow("Name", name)
        self.editors["__name__"] = name
        if node.kind != "Initialization":
            self.loop_checkbox = QtWidgets.QCheckBox(
                "Repeat this stage with LAMMPS variable i"
            )
            self.loop_checkbox.setChecked(node.loop_enabled)
            self.loop_checkbox.toggled.connect(self._loop_toggled)
            self.form.addRow("Loop", self.loop_checkbox)
            self.loop_values_editor = QtWidgets.QLineEdit(node.loop_values)
            self.loop_values_editor.setPlaceholderText("1 2 3 4")
            self.loop_values_editor.setToolTip(
                "LAMMPS index values separated by spaces or commas."
            )
            self.loop_values_editor.textChanged.connect(self._loop_values_changed)
            self.form.addRow("i values", self.loop_values_editor)
            self.loop_note = QtWidgets.QLabel(
                "For an expression, enable ƒ(i) beside a numeric field and use "
                "LAMMPS syntax such as 298.15 + 10*v_i."
            )
            self.loop_note.setObjectName("note")
            self.loop_note.setWordWrap(True)
            self.form.addRow("", self.loop_note)
        for field_name, spec in NODE_SCHEMAS[node.kind]["fields"].items():
            editor = self._make_editor(field_name, spec, node.parameters.get(field_name, spec[1]))
            self.editors[field_name] = editor
            form = self.advanced_form if field_name in ADVANCED_FIELDS.get(node.kind, set()) else self.form
            field_widget = editor
            if node.kind != "Initialization" and spec[0] in {"int", "float"}:
                field_widget = QtWidgets.QWidget()
                field_layout = QtWidgets.QHBoxLayout(field_widget)
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.setSpacing(5)
                expression_button = QtWidgets.QToolButton()
                expression_button.setText("ƒ(i)")
                expression_button.setCheckable(True)
                expression_button.setToolTip(
                    "Use a raw LAMMPS equal-style expression for this field."
                )
                expression_editor = QtWidgets.QLineEdit(
                    node.loop_expressions.get(field_name, "")
                )
                expression_editor.setPlaceholderText("Example: 298.15 + 10*v_i")
                expression_editor.setToolTip(
                    "LAMMPS evaluates this expression. Refer to the iterator as v_i."
                )
                expression_button.setChecked(field_name in node.loop_expressions)
                field_layout.addWidget(editor, 1)
                field_layout.addWidget(expression_editor, 1)
                field_layout.addWidget(expression_button)
                self.expression_editors[field_name] = expression_editor
                self.expression_buttons[field_name] = expression_button
                expression_button.toggled.connect(
                    lambda checked, field=field_name: self._expression_toggled(
                        field, checked
                    )
                )
                expression_editor.textChanged.connect(
                    lambda text, field=field_name: self._expression_changed(field, text)
                )
            form.addRow(self._field_label(field_name), field_widget)
        self._refresh_loop_controls()
        self._validate_fields()
        self.refresh_preview()

    def _loop_toggled(self, enabled: bool):
        if not self.item:
            return
        self.item.model.loop_enabled = bool(enabled)
        self.item.refresh()
        self._refresh_loop_controls()
        self._validate_fields()
        self.refresh_preview()
        self.nodeChanged.emit()

    def _loop_values_changed(self, text: str):
        if not self.item:
            return
        self.item.model.loop_values = text
        self.item.refresh()
        self._validate_fields()
        self.refresh_preview()
        self.nodeChanged.emit()

    def _refresh_loop_controls(self):
        if not self.item:
            return
        enabled = self.item.model.loop_enabled
        if self.loop_values_editor is not None:
            self.loop_values_editor.setVisible(enabled)
            label = self.form.labelForField(self.loop_values_editor)
            if label is not None:
                label.setVisible(enabled)
        if self.loop_note is not None:
            self.loop_note.setVisible(enabled)
            label = self.form.labelForField(self.loop_note)
            if label is not None:
                label.setVisible(enabled)
        for field_name, button in self.expression_buttons.items():
            active = enabled and button.isChecked()
            button.setEnabled(enabled)
            self.editors[field_name].setVisible(not active)
            self.expression_editors[field_name].setVisible(active)

    def _expression_toggled(self, field_name: str, enabled: bool):
        if not self.item:
            return
        expression_editor = self.expression_editors[field_name]
        if enabled:
            if not expression_editor.text().strip():
                expression_editor.setText(str(self._editor_value(self.editors[field_name])))
            self.item.model.loop_expressions[field_name] = expression_editor.text().strip()
        else:
            self.item.model.loop_expressions.pop(field_name, None)
        self._refresh_loop_controls()
        self._validate_fields()
        self.refresh_preview()
        self.nodeChanged.emit()

    def _expression_changed(self, field_name: str, text: str):
        if not self.item or not self.expression_buttons[field_name].isChecked():
            return
        self.item.model.loop_expressions[field_name] = text.strip()
        self._validate_fields()
        self.refresh_preview()
        self.nodeChanged.emit()

    @staticmethod
    def _editor_value(editor):
        if isinstance(editor, QtWidgets.QCheckBox):
            return editor.isChecked()
        if isinstance(editor, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            return editor.value()
        if isinstance(editor, QtWidgets.QComboBox):
            return editor.currentText()
        return editor.text()

    def _make_editor(self, field_name, spec, value):
        kind = spec[0]
        if kind == "bool":
            widget = QtWidgets.QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(self._field_changed)
        elif kind == "int":
            widget = QtWidgets.QSpinBox()
            minimum = 1 if field_name in POSITIVE_FIELDS else -2_147_483_648
            widget.setRange(minimum, 2_147_483_647)
            widget.setValue(int(value))
            widget.valueChanged.connect(self._field_changed)
        elif kind == "float":
            widget = QtWidgets.QDoubleSpinBox()
            minimum = 0.0 if field_name in POSITIVE_FIELDS else -1e12
            widget.setRange(minimum, 1e12)
            widget.setDecimals(6)
            widget.setValue(float(value))
            suffix = self._unit_suffix(field_name)
            if suffix:
                widget.setSuffix(f" {suffix}")
            widget.valueChanged.connect(self._field_changed)
        elif kind == "choice":
            widget = QtWidgets.QComboBox()
            widget.addItems(spec[2])
            widget.setCurrentText(str(value))
            widget.currentTextChanged.connect(self._field_changed)
        else:
            widget = QtWidgets.QLineEdit(str(value))
            widget.textChanged.connect(self._field_changed)
        widget.setToolTip(FIELD_HELP.get(field_name, self._default_help(field_name)))
        return widget

    def _field_label(self, field_name: str) -> str:
        label = field_name.replace("_", " ").title()
        unit = self._unit_suffix(field_name)
        return f"{label} ({unit})" if unit else label

    def _unit_suffix(self, field_name: str) -> str:
        if field_name in {"timestep", "temperature_damping", "pressure_damping"}:
            return {"real": "fs", "metal": "ps", "lj": "reduced"}.get(self.units, "")
        if field_name.startswith("temperature") or field_name == "temperature":
            return "K"
        if field_name.startswith("pressure"):
            return {"real": "atm", "metal": "bar", "lj": "reduced"}.get(self.units, "")
        if field_name in {"dmax", "wall_skin"}:
            return "Å" if self.units in {"real", "metal"} else "reduced"
        if field_name == "energy_tolerance":
            return {"real": "kcal/mol", "metal": "eV", "lj": "reduced"}.get(self.units, "")
        if field_name == "force_tolerance":
            return {"real": "kcal/mol/Å", "metal": "eV/Å", "lj": "reduced"}.get(self.units, "")
        return ""

    @staticmethod
    def _default_help(field_name: str) -> str:
        return f"LAMMPS parameter: {field_name.replace('_', ' ')}."

    def _name_changed(self, text: str):
        if self.item:
            self.item.model.name = text.strip() or self.item.model.kind
            self.item.refresh()
            self.refresh_preview()
            self.nodeChanged.emit()

    def _field_changed(self, *_):
        if not self.item:
            return
        node = self.item.model
        for field_name, editor in self.editors.items():
            if field_name == "__name__":
                continue
            if isinstance(editor, QtWidgets.QCheckBox):
                value = editor.isChecked()
            elif isinstance(editor, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                value = editor.value()
            elif isinstance(editor, QtWidgets.QComboBox):
                value = editor.currentText()
            else:
                value = editor.text()
            node.parameters[field_name] = coerce_value(node.kind, field_name, value)
        self.refresh_preview()
        self._validate_fields()
        self.nodeChanged.emit()

    def _validate_fields(self):
        if not self.item:
            return
        node = self.item.model
        problems = []
        if node.loop_enabled:
            try:
                parse_loop_values(node.loop_values)
            except ValueError as exc:
                problems.append(str(exc))
            for field_name, expression in node.loop_expressions.items():
                try:
                    validate_loop_expression(expression)
                except ValueError as exc:
                    problems.append(
                        f"{field_name.replace('_', ' ')} {exc}"
                    )
        for field_name in POSITIVE_FIELDS:
            if field_name in node.parameters and float(node.parameters[field_name]) <= 0:
                problems.append(f"{field_name.replace('_', ' ')} must be positive")
        steps = node.parameters.get("steps")
        for interval in ("thermo_every", "dump_every"):
            if steps and node.parameters.get(interval, 0) > steps:
                problems.append(f"{interval.replace('_', ' ')} exceeds total steps")
        if node.kind == "Deformation":
            every = int(node.parameters.get("average_every", 1))
            repeats = int(node.parameters.get("average_repeats", 999))
            frequency = int(node.parameters.get("average_frequency", 1000))
            if min(every, repeats, frequency) < 1:
                problems.append("deformation averaging values must be positive")
            elif frequency % every:
                problems.append("average frequency must be a multiple of average every")
            if min(every, repeats, frequency) >= 1 and every * repeats > frequency:
                problems.append("average repeats do not fit inside average frequency")
        self.validation.setVisible(bool(problems))
        self.validation.setText(" · ".join(problems))
        self.validation.setProperty("state", "failed" if problems else "complete")
        self.validation.style().unpolish(self.validation)
        self.validation.style().polish(self.validation)
        for field_name, editor in self.editors.items():
            invalid = any(field_name.replace("_", " ") in problem for problem in problems)
            editor.setProperty("invalid", invalid)
            editor.style().unpolish(editor)
            editor.style().polish(editor)
        if self.loop_values_editor is not None:
            invalid_loop = any("iterator" in problem for problem in problems)
            self.loop_values_editor.setProperty("invalid", invalid_loop)
            self.loop_values_editor.style().unpolish(self.loop_values_editor)
            self.loop_values_editor.style().polish(self.loop_values_editor)
        for field_name, editor in self.expression_editors.items():
            label = field_name.replace("_", " ")
            invalid = any(label in problem for problem in problems)
            editor.setProperty("invalid", invalid)
            editor.style().unpolish(editor)
            editor.style().polish(editor)

    def refresh_preview(self):
        if not self.item:
            return
        try:
            stage_numbers = {
                self.item.model.id: self.item.execution_index or 1,
            }
            self.preview.setPlainText(
                generate_protocol_script(
                    [self.item.model],
                    self.item.model.name,
                    stage_numbers=stage_numbers,
                )
            )
        except Exception as exc:
            self.preview.setPlainText(f"Cannot preview this node.\n\n{exc}")


class ProtocolEditor(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        palette = QtWidgets.QFrame()
        palette.setObjectName("sidePanel")
        palette_layout = QtWidgets.QVBoxLayout(palette)
        heading = QtWidgets.QLabel("Protocol nodes")
        heading.setObjectName("sectionTitle")
        palette_layout.addWidget(heading)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter nodes…")
        palette_layout.addWidget(self.search)
        self.node_list = QtWidgets.QListWidget()
        self.node_list.addItems(NODE_SCHEMAS)
        palette_layout.addWidget(self.node_list, 1)
        self.add_button = QtWidgets.QPushButton("Add selected node")
        self.starter_button = QtWidgets.QPushButton("Load starter protocol")
        self.load_button = QtWidgets.QPushButton("Load protocol…")
        self.save_button = QtWidgets.QPushButton("Save protocol…")
        palette_layout.addWidget(self.add_button)
        palette_layout.addWidget(self.starter_button)
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(self.load_button)
        preset_row.addWidget(self.save_button)
        palette_layout.addLayout(preset_row)

        center = QtWidgets.QWidget()
        center_layout = QtWidgets.QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        tools = QtWidgets.QHBoxLayout()
        self.undo_button = QtWidgets.QPushButton("Undo")
        self.redo_button = QtWidgets.QPushButton("Redo")
        self.delete_button = QtWidgets.QPushButton("Delete selected")
        self.fit_button = QtWidgets.QPushButton("Fit graph")
        self.layout_button = QtWidgets.QPushButton("Arrange")
        tools.addWidget(self.undo_button)
        tools.addWidget(self.redo_button)
        tools.addWidget(self.delete_button)
        tools.addWidget(self.layout_button)
        tools.addWidget(self.fit_button)
        tools.addStretch()
        tools.addWidget(QtWidgets.QLabel("Drag from a node’s right socket to another node"))
        center_layout.addLayout(tools)
        self.validation_banner = QtWidgets.QLabel("")
        self.validation_banner.setObjectName("inlineValidation")
        self.validation_banner.setWordWrap(True)
        self.validation_banner.setVisible(False)
        center_layout.addWidget(self.validation_banner)
        self.scene = GraphScene()
        self.view = GraphView(self.scene)
        center_layout.addWidget(self.view, 1)

        inspector_frame = QtWidgets.QFrame()
        inspector_frame.setObjectName("sidePanel")
        inspector_layout = QtWidgets.QVBoxLayout(inspector_frame)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        self.inspector = NodeInspector()
        inspector_layout.addWidget(self.inspector)
        splitter.addWidget(palette)
        splitter.addWidget(center)
        splitter.addWidget(inspector_frame)
        splitter.setSizes([190, 720, 350])
        root.addWidget(splitter)

        self.add_button.clicked.connect(self.add_selected_kind)
        self.node_list.itemDoubleClicked.connect(lambda _: self.add_selected_kind())
        self.delete_button.clicked.connect(self.scene.delete_selected)
        self.fit_button.clicked.connect(self.fit_graph)
        self.layout_button.clicked.connect(self.arrange)
        self.starter_button.clicked.connect(self.load_starter)
        self.load_button.clicked.connect(self.load_protocol)
        self.save_button.clicked.connect(self.save_protocol)
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.search.textChanged.connect(self.filter_nodes)
        self.scene.nodeSelected.connect(self.inspector.set_node)
        self.scene.graphChanged.connect(self._record_change)
        self.inspector.nodeChanged.connect(self._record_change)
        self._history_timer = QtCore.QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(250)
        self._history_timer.timeout.connect(self._finalize_history_step)
        self._undo_stack: list[ProtocolGraph] = []
        self._redo_stack: list[ProtocolGraph] = []
        self._snapshot = deepcopy(self.scene.graph)
        self._pending_before: ProtocolGraph | None = None
        self._restoring = False
        self.undo_action = QtGui.QAction(self)
        self.undo_action.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.addAction(self.undo_action)
        self.redo_action = QtGui.QAction(self)
        self.redo_action.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.addAction(self.redo_action)
        self._update_history_actions()

    @property
    def graph(self):
        return self.scene.graph

    def load_graph(self, graph: ProtocolGraph):
        self._restoring = True
        self.scene.load_graph(graph)
        self._restoring = False
        self._history_timer.stop()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._pending_before = None
        self._snapshot = deepcopy(self.scene.graph)
        self._refresh_units()
        self.show_validation([])
        self._update_history_actions()
        QtCore.QTimer.singleShot(0, self.fit_graph)

    def _record_change(self):
        if self._restoring:
            return
        if self._pending_before is None:
            self._pending_before = deepcopy(self._snapshot)
            self._redo_stack.clear()
        self._history_timer.start()
        self._refresh_units()
        self.show_validation([])
        self._update_history_actions()
        self.changed.emit()

    def _finalize_history_step(self):
        if self._pending_before is None:
            return
        current = deepcopy(self.scene.graph)
        if current != self._pending_before:
            self._undo_stack.append(self._pending_before)
            if len(self._undo_stack) > 100:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
        self._snapshot = current
        self._pending_before = None
        self._update_history_actions()

    def undo(self):
        self._finalize_history_step()
        if not self._undo_stack:
            return
        self._redo_stack.append(deepcopy(self.scene.graph))
        self._apply_history(self._undo_stack.pop())

    def redo(self):
        self._finalize_history_step()
        if not self._redo_stack:
            return
        self._undo_stack.append(deepcopy(self.scene.graph))
        self._apply_history(self._redo_stack.pop())

    def _apply_history(self, graph: ProtocolGraph):
        self._restoring = True
        self.scene.load_graph(deepcopy(graph))
        self._restoring = False
        self._snapshot = deepcopy(self.scene.graph)
        self._pending_before = None
        self.inspector.set_node(None)
        self._refresh_units()
        self.show_validation([])
        self._update_history_actions()
        self.fit_graph()
        self.changed.emit()

    def _update_history_actions(self):
        self.undo_button.setEnabled(bool(self._undo_stack or self._pending_before))
        self.redo_button.setEnabled(bool(self._redo_stack))
        self.undo_action.setEnabled(self.undo_button.isEnabled())
        self.redo_action.setEnabled(self.redo_button.isEnabled())

    def _refresh_units(self):
        units = "real"
        for node in self.scene.graph.nodes:
            if node.kind == "Initialization":
                units = str(node.parameters.get("units", "real"))
                break
        self.inspector.set_units(units)

    def show_validation(self, errors: list[str]):
        self.validation_banner.setVisible(bool(errors))
        self.validation_banner.setText("Protocol needs attention · " + " · ".join(errors) if errors else "")
        self.validation_banner.setProperty("state", "failed" if errors else "complete")
        self.validation_banner.style().unpolish(self.validation_banner)
        self.validation_banner.style().polish(self.validation_banner)

    def add_selected_kind(self):
        item = self.node_list.currentItem()
        if item:
            center = self.view.mapToScene(self.view.viewport().rect().center())
            self.scene.add_node(item.text(), center)

    def load_starter(self):
        if self.scene.graph.nodes:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Replace protocol?",
                "Replace the current graph with the Initialization–Minimization–Velocities–NVT starter protocol?",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self._restoring = True
        self.scene.load_graph(default_protocol())
        self._restoring = False
        self._record_change()
        self.fit_graph()

    def save_protocol(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save protocol",
            "protocol.scymol-protocol.json",
            "Scymol protocol (*.scymol-protocol.json);;JSON files (*.json)",
        )
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_name(target.name + ".scymol-protocol.json")
        try:
            save_protocol_preset(self.scene.graph, target)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot save protocol", str(exc))

    def load_protocol(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load protocol",
            "",
            "Scymol protocol (*.scymol-protocol.json *.json);;All files (*)",
        )
        if not path:
            return
        if self.scene.graph.nodes:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Replace protocol?",
                "Replace the current protocol with the selected saved protocol?",
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        try:
            graph = load_protocol_preset(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot load protocol", str(exc))
            return
        self.load_graph(graph)
        self.changed.emit()

    def arrange(self):
        try:
            paths = protocol_paths(self.scene.graph)
        except ValueError:
            return
        seen = set()
        for row, path in enumerate(paths):
            for column, node in enumerate(path):
                item = self.scene.node_items[node.id]
                if node.id not in seen:
                    item.setPos(column * 225, row * 130)
                    seen.add(node.id)
        self.fit_graph()

    def fit_graph(self):
        rect = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        if not rect.isEmpty():
            self.view.fitInView(rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def filter_nodes(self, text: str):
        text = text.lower().strip()
        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            item.setHidden(text not in item.text().lower())


class ProtocolPage(StagePage):
    def __init__(self, parent=None):
        super().__init__(
            "3 · Protocol",
            "Build sequential or branching LAMMPS routines graphically. Fixed project phases stay outside the graph; variable simulation logic stays inside it.",
            "Validate and preview protocol",
            parent,
        )
        self.compact_header()
        self.use_workspace_layout()
        self.editor = ProtocolEditor()
        self.layout.addWidget(self.editor, 1)
        self.editor.changed.connect(self._protocol_changed)

    def load_graph(self, graph: ProtocolGraph):
        self.editor.load_graph(graph)
        self.set_status(
            "Needs validation",
            "pending",
            "Review the protocol graph, then validate it before preparing the simulation.",
        )

    def _protocol_changed(self):
        self.set_status(
            "Needs validation",
            "pending",
            "Protocol settings changed; validate the graph again.",
        )
        self.changed.emit()

    def validate_and_preview(self):
        errors = validate_graph(self.editor.graph)
        self.editor.show_validation(errors)
        if errors:
            self.set_status("Needs attention", "failed", " ".join(errors))
            return False
        paths = protocol_paths(self.editor.graph)
        total_nodes = len(self.editor.graph.nodes)
        self.set_status(
            "Ready",
            "complete",
            f"{total_nodes} nodes · {len(paths)} executable protocol path(s)",
        )
        return True

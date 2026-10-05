import math

from PySide6 import QtCore, QtGui, QtWidgets
from rdkit import Chem
from rdkit.Chem import Draw, rdDepictor, rdMolDescriptors

from .constants import (
    BOND_LEN,
    BOND_PICK_TRIM_FRACTION,
    BOND_TYPES,
    COMPONENT_GRID_GAP,
    NEAR_ATOM,
    NEAR_BOND,
    SNAP,
    SYM2Z,
    UNITED_ATOM_ZOOM_THRESHOLD,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_STEP,
)
from .model import History, MoleculeModel
from .settings import SETTINGS

ATOM_STYLES = {
    # CPK-inspired colors with visually normalized radii in screen pixels.
    "H": {"fill": "#ffffff", "outline": "#9aa3a0", "text": "#58615f", "radius": 7.0},
    "C": {"fill": "#555d5b", "outline": "#303735", "text": "#ffffff", "radius": 10.0},
    "N": {"fill": "#4267d5", "outline": "#29469f", "text": "#ffffff", "radius": 10.2},
    "O": {"fill": "#d94b4b", "outline": "#a52d2d", "text": "#ffffff", "radius": 10.4},
    "F": {"fill": "#70b84b", "outline": "#477f2e", "text": "#173f20", "radius": 9.7},
    "P": {"fill": "#e68a36", "outline": "#a85b1d", "text": "#ffffff", "radius": 11.3},
    "S": {"fill": "#e0bd32", "outline": "#9e8015", "text": "#3f3509", "radius": 11.8},
    "Cl": {"fill": "#58aa43", "outline": "#337629", "text": "#ffffff", "radius": 11.2},
    "Br": {"fill": "#9d4f3f", "outline": "#6f3026", "text": "#ffffff", "radius": 11.8},
    "I": {"fill": "#7853a6", "outline": "#503477", "text": "#ffffff", "radius": 12.2},
}
DEFAULT_ATOM_STYLE = {
    "fill": "#ee78b7",
    "outline": "#a9477d",
    "text": "#3d1730",
    "radius": 10.5,
}
ATOM_CIRCLE_SCALE = 1.25
ATOM_COLORS = {
    symbol: QtGui.QColor(style["outline"])
    for symbol, style in ATOM_STYLES.items()
}

RING_TEMPLATES = {
    "cyclohexane": {
        "orders": (1, 1, 1, 1, 1, 1),
        "aromatize_existing": False,
    },
    "benzene": {
        "orders": (2, 1, 2, 1, 2, 1),
        "aromatize_existing": True,
    },
}


def _median(values):
    if not values:
        return None

    values = sorted(values)
    mid = len(values) // 2

    if len(values) % 2:
        return values[mid]

    return 0.5 * (values[mid - 1] + values[mid])


class MoleculeCanvas(QtWidgets.QWidget):
    changed = QtCore.Signal()
    smilesChanged = QtCore.Signal(str)
    statusSummaryChanged = QtCore.Signal(str, str, float)
    componentSelected = QtCore.Signal(int)
    activeToolChanged = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.model = MoleculeModel()
        self.history = History()

        self.active_sym = "C"

        self.down_model = None
        self.down_view = None
        self.start_atom = None
        self.dragging = False
        self.preview = None

        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms = set()

        self.hover_atom = None
        self.hover_bond = None

        self.moving_selection = False
        self.selection_moved = False
        self.move_anchor_model = None
        self.move_original_positions = {}

        self.show_h = False
        self.show_carbon_dots = False
        self.united_atom_requested = False
        self.read_only = False
        self.selection_only = False
        self.bead_overlays = []
        self.bead_summary_mode = False
        self.atom_circle_mode = False
        self.locked_atoms = set()
        self.aa_dynamic = bool(SETTINGS["aa_dynamic"])
        self.status_update_delay_ms = int(SETTINGS["status_update_delay_ms"])

        self.pan_x = 0.0
        self.pan_y = 0.0
        self.scale = 1.6

        self.panning = False
        self.pan_anchor = None

        self.active_tool = "draw"
        self.chain_preview = None
        self._cyclohexane_cursor = None
        self.component_labels = []
        self.component_label_provider = None
        self._component_label_cache = {}
        self._prepared_smiles_cache = {}
        self._united_atom_label_cache = {}
        self._united_atom_label_cache_dirty = True

        self._spatial_index_dirty = True
        self._spatial_cell = BOND_LEN
        self._atom_bins = {}
        self._bond_bins = {}

        self._view_cache_dirty = True
        self._view_cache = None
        self._view_cache_signature = None

        self._font_scale = None
        self._font = QtGui.QFont("Arial", 14, QtGui.QFont.Weight.Bold)
        self._small_font = QtGui.QFont("Arial", 9)
        self._chain_count_font = QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Bold)

        self._atom_pen_cache = {}

        self._bond_pen = QtGui.QPen(
            QtGui.QColor(35, 35, 35),
            1,
            QtCore.Qt.PenStyle.SolidLine,
            QtCore.Qt.PenCapStyle.RoundCap,
        )
        self._preview_pen = QtGui.QPen(
            QtGui.QColor(110, 110, 110),
            1,
            QtCore.Qt.PenStyle.DashLine,
            QtCore.Qt.PenCapStyle.RoundCap,
        )
        self._hover_pen = QtGui.QPen(QtGui.QColor(176, 230, 219), 1.0)
        self._sel_pen = QtGui.QPen(QtGui.QColor(215, 150, 190), 1.0)

        self._white_brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        self._black_brush = QtGui.QBrush(QtGui.QColor(25, 25, 25))
        self._hover_fill = QtGui.QBrush(QtGui.QColor(176, 230, 219, 70))
        self._sel_fill = QtGui.QBrush(QtGui.QColor(230, 175, 210, 75))
        self._chain_count_fill = QtGui.QBrush(QtGui.QColor(255, 255, 255, 235))
        self._chain_count_pen = QtGui.QPen(QtGui.QColor(95, 95, 95), 1.0)
        self._empty_brush = QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush)

        self._smiles_emit_timer = QtCore.QTimer(self)
        self._smiles_emit_timer.setSingleShot(True)
        self._smiles_emit_timer.timeout.connect(self._emit_smiles_changed)

    def _make_cyclohexane_cursor(self):
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor(35, 35, 35), 2.0))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        center = QtCore.QPointF(16, 16)
        radius = 10.5
        polygon = QtGui.QPolygonF(
            [
                QtCore.QPointF(
                    center.x() + radius * math.cos(math.pi / 6 + i * math.pi / 3),
                    center.y() + radius * math.sin(math.pi / 6 + i * math.pi / 3),
                )
                for i in range(6)
            ]
        )
        painter.drawPolygon(polygon)
        painter.end()

        return QtGui.QCursor(pixmap, 16, 16)

    def _update_tool_cursor(self):
        if self.active_tool in ("cyclohexane", "benzene"):
            if self._cyclohexane_cursor is None:
                self._cyclohexane_cursor = self._make_cyclohexane_cursor()

            self.setCursor(self._cyclohexane_cursor)
        else:
            self.unsetCursor()

    def _tool_is(self, tool):
        return self.active_tool == tool

    def _set_active_tool(self, tool):
        self.active_tool = tool
        self._clear_drag_state(clear_start=False, clear_chain=True)
        self._clear_move_state()
        self._update_tool_cursor()
        self.activeToolChanged.emit(tool)
        self.update()

    def _clear_drag_state(self, clear_start=True, clear_chain=False):
        self.down_model = None
        self.down_view = None
        self.dragging = False
        self.preview = None

        if clear_start:
            self.start_atom = None

        if clear_chain:
            self.chain_preview = None

    def _clear_move_state(self):
        self.moving_selection = False
        self.selection_moved = False
        self.move_anchor_model = None
        self.move_original_positions = {}

    def sizeHint(self):
        return QtCore.QSize(1000, 700)

    @staticmethod
    def _event_xy(event):
        pos = event.position()
        return pos.x(), pos.y()

    def push_state(self):
        self.history.push(
            self.model.atoms,
            self.model.bonds,
            self.model.next_aid,
            self.selected_atom,
            self.selected_bond,
            self.selected_atoms,
        )

    def invalidate_view_cache(self):
        self._view_cache_dirty = True

    def invalidate_spatial_index(self):
        self._spatial_index_dirty = True

    def invalidate_model_caches(self):
        self.invalidate_view_cache()
        self.invalidate_spatial_index()
        self._united_atom_label_cache_dirty = True

    def _spatial_key(self, x, y):
        return int(math.floor(x / self._spatial_cell)), int(math.floor(y / self._spatial_cell))

    def _near_spatial_keys(self, x, y, radius):
        cx, cy = self._spatial_key(x, y)
        spread = max(1, int(math.ceil(radius / self._spatial_cell)))

        for ix in range(cx - spread, cx + spread + 1):
            for iy in range(cy - spread, cy + spread + 1):
                yield ix, iy

    def rebuild_spatial_index(self):
        atom_bins = {}
        bond_bins = {}

        for aid, (x, y, _) in self.model.atoms.items():
            atom_bins.setdefault(self._spatial_key(x, y), []).append(aid)

        for key in self.model.bonds:
            a, b = tuple(key)

            if a not in self.model.atoms or b not in self.model.atoms:
                continue

            x1, y1, _ = self.model.atoms[a]
            x2, y2, _ = self.model.atoms[b]
            xmin = min(x1, x2) - NEAR_BOND
            xmax = max(x1, x2) + NEAR_BOND
            ymin = min(y1, y2) - NEAR_BOND
            ymax = max(y1, y2) + NEAR_BOND
            ix0, iy0 = self._spatial_key(xmin, ymin)
            ix1, iy1 = self._spatial_key(xmax, ymax)

            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    bond_bins.setdefault((ix, iy), []).append(key)

        self._atom_bins = atom_bins
        self._bond_bins = bond_bins
        self._spatial_index_dirty = False

    def ensure_spatial_index(self):
        if self._spatial_index_dirty:
            self.rebuild_spatial_index()

    def connected_component_from_atom(self, aid):
        if aid not in self.model.atoms:
            return set()

        adjacency = {}

        for key in self.model.bonds:
            a, b = tuple(key)

            if a not in adjacency:
                adjacency[a] = []

            if b not in adjacency:
                adjacency[b] = []

            adjacency[a].append(b)
            adjacency[b].append(a)

        visited = set()
        stack = [aid]

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)

            for other in adjacency.get(current, []):
                if other not in visited:
                    stack.append(other)

        return visited

    def connected_components(self):
        remaining = set(self.model.atoms)
        components = []
        adjacency_atoms = set()

        for key in self.model.bonds:
            adjacency_atoms.update(key)

        while remaining:
            aid = min(remaining)
            if aid in adjacency_atoms:
                component = self.connected_component_from_atom(aid)
            else:
                component = {aid}

            if not component:
                component = {aid}

            components.append(component)
            remaining -= component

        return components

    def component_bounds(self, component):
        xs = [self.model.atoms[aid][0] for aid in component if aid in self.model.atoms]
        ys = [self.model.atoms[aid][1] for aid in component if aid in self.model.atoms]

        if not xs or not ys:
            return 0.0, 0.0, 0.0, 0.0

        return min(xs), min(ys), max(xs), max(ys)

    def arrange_components_on_grid(self, push=False):
        components = self.connected_components()

        if len(components) <= 1:
            return False

        components.sort(key=lambda component: min(component))

        bounds = [self.component_bounds(component) for component in components]
        widths = [max(BOND_LEN, xmax - xmin) for xmin, _, xmax, _ in bounds]
        heights = [max(BOND_LEN, ymax - ymin) for _, ymin, _, ymax in bounds]

        columns = max(1, math.ceil(math.sqrt(len(components))))
        rows = math.ceil(len(components) / columns)
        cell_w = max(widths) + COMPONENT_GRID_GAP
        cell_h = max(heights) + COMPONENT_GRID_GAP

        all_xmin = min(value[0] for value in bounds)
        all_ymin = min(value[1] for value in bounds)
        origin_x = all_xmin + 0.5 * max(widths)
        origin_y = all_ymin + 0.5 * max(heights)

        new_positions = {}

        for index, component in enumerate(components):
            row = index // columns
            column = index % columns
            xmin, ymin, xmax, ymax = bounds[index]
            component_cx = 0.5 * (xmin + xmax)
            component_cy = 0.5 * (ymin + ymax)
            target_cx = origin_x + column * cell_w
            target_cy = origin_y + row * cell_h
            dx = target_cx - component_cx
            dy = target_cy - component_cy

            for aid in component:
                x, y, sym = self.model.atoms[aid]
                new_positions[aid] = (x + dx, y + dy, sym)

        if all(self.model.atoms[aid] == new_positions[aid] for aid in new_positions):
            return False

        if push:
            self.push_state()

        for aid, value in new_positions.items():
            self.model.atoms[aid] = value

        return True

    def build_component_mol(self, component):
        mol = Chem.RWMol()
        aid_to_idx = {}

        for aid in sorted(component):
            if aid not in self.model.atoms:
                continue

            _, _, sym = self.model.atoms[aid]
            aid_to_idx[aid] = mol.AddAtom(Chem.Atom(SYM2Z.get(sym, 6)))

        for key, order in self.model.bonds.items():
            if not key.issubset(component):
                continue

            a, b = tuple(key)

            if a not in aid_to_idx or b not in aid_to_idx:
                continue

            order = max(1, min(3, int(order)))
            mol.AddBond(aid_to_idx[a], aid_to_idx[b], BOND_TYPES[order - 1])

        out = mol.GetMol()
        Chem.SanitizeMol(out)
        return out

    def component_signature(self, component):
        atoms = tuple(
            (aid, self.model.atoms[aid][2])
            for aid in sorted(component)
            if aid in self.model.atoms
        )
        bonds = []

        for key, order in self.model.bonds.items():
            if not key.issubset(component):
                continue

            a, b = sorted(key)
            bonds.append((a, b, int(order)))

        return atoms, tuple(sorted(bonds))

    def component_label_text(self, index, component):
        if self.component_label_provider is not None:
            custom = self.component_label_provider(index - 1, component)
            if custom:
                return str(custom)
        signature = self.component_signature(component)

        if signature in self._component_label_cache:
            formula, mw = self._component_label_cache[signature]
            return f"{index} | {formula} | {mw}"

        try:
            mol = self.build_component_mol(component)
            formula = rdMolDescriptors.CalcMolFormula(mol)
            mw = f"{rdMolDescriptors.CalcExactMolWt(mol):.2f}"
            self._component_label_cache[signature] = (formula, mw)
            return f"{index} | {formula} | {mw}"
        except Exception:
            return f"{index} | ? | ?"

    def component_export_rows(self):
        components = self.connected_components()
        components.sort(key=lambda component: min(component))

        records = []

        for index, component in enumerate(components, start=1):
            xmin, ymin, xmax, ymax = self.component_bounds(component)
            records.append(
                {
                    "component": component,
                    "index": index,
                    "label": self.component_label_text(index, component),
                    "center_x": 0.5 * (xmin + xmax),
                    "center_y": 0.5 * (ymin + ymax),
                }
            )

        records.sort(key=lambda record: record["center_y"])

        rows = []
        row_tolerance = BOND_LEN * 0.75

        for record in records:
            if not rows:
                rows.append([record])
                continue

            row_center = sum(item["center_y"] for item in rows[-1]) / len(rows[-1])

            if abs(record["center_y"] - row_center) <= row_tolerance:
                rows[-1].append(record)
            else:
                rows.append([record])

        for row in rows:
            row.sort(key=lambda record: record["center_x"])

        return rows

    def export_grid_image(self, use_svg=False):
        rows = self.component_export_rows()

        if not rows:
            raise ValueError("Empty sketch")

        mols_per_row = max(len(row) for row in rows)
        blank_mol = Chem.Mol()
        mols = []
        legends = []

        for row in rows:
            for record in row:
                mol = self.build_component_mol(record["component"])
                rdDepictor.Compute2DCoords(mol)
                mols.append(mol)
                legends.append(record["label"])

            for _ in range(mols_per_row - len(row)):
                mols.append(blank_mol)
                legends.append("")

        return Draw.MolsToGridImage(
            mols,
            molsPerRow=mols_per_row,
            subImgSize=(260, 220),
            legends=legends,
            useSVG=use_svg,
        )

    def update_component_labels(self):
        labels = []
        components = self.connected_components()
        components.sort(key=lambda component: min(component))

        for index, component in enumerate(components, start=1):
            xmin, ymin, xmax, ymax = self.component_bounds(component)
            labels.append(
                {
                    "text": self.component_label_text(index, component),
                    "x": 0.5 * (xmin + xmax),
                    "y": ymax + 0.45 * COMPONENT_GRID_GAP,
                    "atom_id": min(component),
                }
            )

        self.component_labels = labels

    def clear_component_labels(self):
        self.component_labels = []

    def set_component_label_provider(self, provider):
        self.component_label_provider = provider
        self.update_component_labels()
        self.invalidate_view_cache()
        self.update()

    def snap_components_to_grid(self, push=True):
        if push:
            self.push_state()

        try:
            self.clean_structure(push=False, center=False, emit=False)
        except Exception:
            self._restore_last_state_without_emitting()
            raise

        arranged = self.arrange_components_on_grid(push=False)

        if arranged or self.model.atoms:
            self.center_structure()
            self._emit_change()
        else:
            self._restore_last_state_without_emitting()
            self._emit_change(clear_labels=True)

    def select_atom(self, aid):
        self.selected_atom = aid
        self.selected_bond = None
        self.selected_atoms = set()
        self._emit_component_selected(aid)

    def select_component(self, aid):
        self.selected_atoms = self.connected_component_from_atom(aid)
        self.selected_atom = aid
        self.selected_bond = None
        self.update()
        self._emit_component_selected(aid)

    def clear_selection(self):
        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()
        self.update()
        self.componentSelected.emit(-1)

    def _emit_component_selected(self, aid):
        components = self.connected_components()
        components.sort(key=lambda component: min(component))
        for index, component in enumerate(components):
            if aid in component:
                self.componentSelected.emit(index)
                return
        self.componentSelected.emit(-1)

    def component_at(self, view_x, view_y):
        """Return an atom id identifying the component at a canvas position."""
        aid = self.nearest_atom(view_x, view_y)
        if aid is not None:
            return aid

        bond = self.nearest_bond(view_x, view_y)
        if bond is not None:
            return min(bond)

        return self.component_background_at(view_x, view_y)

    def component_background_at(self, view_x, view_y):
        """Select a component only through its label or unused interior space."""
        if self.nearest_atom(view_x, view_y) is not None:
            return None
        if self.nearest_bond(view_x, view_y) is not None:
            return None

        # Labels are part of the molecule card and should be clickable too.
        metrics = QtGui.QFontMetricsF(self._small_font)
        for label in self.component_labels:
            cx, cy = self.to_view(label["x"], label["y"])
            width = metrics.horizontalAdvance(label["text"]) + 14.0
            height = metrics.height() + 10.0
            if abs(view_x - cx) <= width * 0.5 and abs(view_y - cy) <= height * 0.5:
                return label.get("atom_id")

        # Also accept whitespace inside the molecule's compact visual footprint.
        mx, my = self.to_model(view_x, view_y)
        padding = 14.0 / self.scale
        components = self.connected_components()
        components.sort(key=lambda component: min(component))
        for component in components:
            xmin, ymin, xmax, ymax = self.component_bounds(component)
            if xmin - padding <= mx <= xmax + padding and ymin - padding <= my <= ymax + padding:
                return min(component)

        return None

    def selection_contains_atom(self, aid):
        return aid in self.selected_atoms

    def mouseDoubleClickEvent(self, event):
        self.setFocus()

        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        x, y = self._event_xy(event)

        self.update_hover(x, y)

        aid = (
            self.component_at(x, y)
            if self.read_only
            else self.component_background_at(x, y)
        )
        if aid is not None:
            self.select_component(aid)
        else:
            self.clear_selection()

    def to_model(self, x, y):
        return (x - self.pan_x) / self.scale, (y - self.pan_y) / self.scale

    def to_view(self, x, y):
        return x * self.scale + self.pan_x, y * self.scale + self.pan_y

    def nearest_atom(self, x, y):
        mx, my = self.to_model(x, y)
        self.ensure_spatial_index()

        best = None
        bestd2 = NEAR_ATOM * NEAR_ATOM
        candidates = set()

        for key in self._near_spatial_keys(mx, my, NEAR_ATOM):
            candidates.update(self._atom_bins.get(key, []))

        for aid in candidates:
            ax, ay, _ = self.model.atoms[aid]
            d2 = (ax - mx) ** 2 + (ay - my) ** 2

            if d2 <= bestd2:
                bestd2 = d2
                best = aid

        return best

    def nearest_bond(self, x, y):
        mx, my = self.to_model(x, y)
        self.ensure_spatial_index()

        best = None
        best_distance = NEAR_BOND + 1.0
        candidates = set()

        for bin_key in self._near_spatial_keys(mx, my, NEAR_BOND):
            candidates.update(self._bond_bins.get(bin_key, []))

        for key in candidates:
            a, b = tuple(key)

            if a not in self.model.atoms or b not in self.model.atoms:
                continue

            x1, y1, _ = self.model.atoms[a]
            x2, y2, _ = self.model.atoms[b]

            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)

            if length < 1e-6:
                continue

            trim = min(BOND_PICK_TRIM_FRACTION, 14.0 / length)

            ix1 = x1 + dx * trim
            iy1 = y1 + dy * trim
            ix2 = x2 - dx * trim
            iy2 = y2 - dy * trim

            distance = self._point_segment_distance(mx, my, ix1, iy1, ix2, iy2)

            if distance < best_distance:
                best_distance = distance
                best = key

        return best if best_distance <= NEAR_BOND else None

    def update_hover(self, x, y):
        old_atom = self.hover_atom
        old_bond = self.hover_bond
        atom = self.nearest_atom(x, y)

        if atom is not None:
            self.hover_atom = atom
            self.hover_bond = None
            return old_atom != self.hover_atom or old_bond != self.hover_bond

        self.hover_atom = None
        self.hover_bond = self.nearest_bond(x, y)
        return old_atom != self.hover_atom or old_bond != self.hover_bond

    def _bond_length(self, key):
        a, b = tuple(key)

        if a not in self.model.atoms or b not in self.model.atoms:
            return None

        x1, y1, _ = self.model.atoms[a]
        x2, y2, _ = self.model.atoms[b]
        length = math.hypot(x2 - x1, y2 - y1)
        return length if length > 1e-6 else None

    def nominal_bond_length(self, anchor_atom=None):
        local_lengths = []

        if anchor_atom is not None:
            for key in self.model.bonds:
                if anchor_atom in key:
                    length = self._bond_length(key)

                    if length is not None:
                        local_lengths.append(length)

        length = _median(local_lengths)

        if length is None:
            all_lengths = []

            for key in self.model.bonds:
                bond_length = self._bond_length(key)

                if bond_length is not None:
                    all_lengths.append(bond_length)

            length = _median(all_lengths)

        if length is None:
            return BOND_LEN

        return max(BOND_LEN * 0.5, min(BOND_LEN * 2.5, length))

    def snap_end(self, x0, y0, x1, y1, bond_length=None):
        dx = x1 - x0
        dy = y1 - y0

        if abs(dx) + abs(dy) < 1e-6:
            angle = 0.0
        else:
            angle = math.atan2(dy, dx)

        angle = round(angle / SNAP) * SNAP
        bond_length = BOND_LEN if bond_length is None else bond_length

        return x0 + bond_length * math.cos(angle), y0 + bond_length * math.sin(angle)

    @staticmethod
    def _point_segment_distance(px, py, x1, y1, x2, y2):
        vx = x2 - x1
        vy = y2 - y1
        wx = px - x1
        wy = py - y1

        denom = vx * vx + vy * vy

        if denom == 0:
            return math.hypot(px - x1, py - y1)

        t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
        qx = x1 + t * vx
        qy = y1 + t * vy

        return math.hypot(px - qx, py - qy)

    def set_chain_mode(self, enabled):
        self._set_active_tool("chain" if enabled else "draw")

    def set_cyclohexane_mode(self, enabled):
        self._set_active_tool("cyclohexane" if enabled else "draw")

    def set_benzene_mode(self, enabled):
        self._set_active_tool("benzene" if enabled else "draw")

    def set_united_atom_mode(self, enabled):
        self.united_atom_requested = bool(enabled)
        self.invalidate_view_cache()
        self.update()

    def set_read_only(self, enabled):
        self.read_only = bool(enabled)
        if self.read_only:
            self.selection_only = False
        self.clear_selection()
        self._clear_drag_state(clear_start=True, clear_chain=True)
        self._clear_move_state()
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor if self.read_only else QtCore.Qt.CursorShape.ArrowCursor)

    def set_selection_only(self, enabled):
        self.selection_only = bool(enabled)
        if self.selection_only:
            self.read_only = False
            self._clear_drag_state(clear_start=True, clear_chain=True)
            self._clear_move_state()
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        else:
            self.clear_selection()

    def set_bead_overlays(self, overlays):
        self.bead_overlays = list(overlays or [])
        self.invalidate_view_cache()
        self.update()

    def set_bead_summary_mode(self, enabled):
        self.bead_summary_mode = bool(enabled)
        self.invalidate_view_cache()
        self.update()

    def set_atom_circle_mode(self, enabled):
        self.atom_circle_mode = bool(enabled)
        self.invalidate_view_cache()
        self.update()

    def set_locked_atoms(self, atom_ids):
        self.locked_atoms = set(atom_ids or [])
        if self.selected_atoms:
            self.selected_atoms.difference_update(self.locked_atoms)
        if self.selected_atom in self.locked_atoms:
            self.selected_atom = None
        self.update()

    def should_show_united_atoms(self):
        return self.united_atom_requested and self.scale > UNITED_ATOM_ZOOM_THRESHOLD

    def set_atom_symbol(self, sym):
        self.active_sym = sym
        if self.active_tool == "draw":
            self.activeToolChanged.emit("draw")

        if self.selected_atom is None:
            return

        self.push_state()
        self.model.set_atom_sym(self.selected_atom, sym)

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()
            self._emit_change()
            return

        self._emit_change()

    def get_mol(self):
        mol, _, _ = self.model.build_mol()
        return mol

    def get_smiles(self):
        if not self.model.atoms:
            return ""

        return Chem.MolToSmiles(self.get_mol())

    def load_smiles(self, smiles, explicit_hydrogens=False):
        mol = self.prepare_smiles_mol(smiles, explicit_hydrogens=explicit_hydrogens)
        self.push_state()
        self.model.clear()
        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()
        self.add_mol_to_model(mol)
        self.center_structure()
        self._emit_change()

    def load_smiles_list(self, smiles_values):
        prepared = [
            self.prepare_smiles_mol(str(smiles).strip())
            for smiles in smiles_values
            if str(smiles).strip()
        ]
        self.push_state()
        self.model.clear()
        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()
        for mol in prepared:
            self.add_mol_to_model(mol)
        if self.model.atoms:
            self.arrange_components_on_grid(push=False)
            self.center_structure()
        self._emit_change()

    def component_smiles(self):
        components = self.connected_components()
        components.sort(key=lambda component: min(component))
        return [Chem.MolToSmiles(self.build_component_mol(component)) for component in components]

    def component_details(self):
        details = []
        components = self.connected_components()
        components.sort(key=lambda component: min(component))
        for component in components:
            mol = self.build_component_mol(component)
            details.append(
                {
                    "smiles": Chem.MolToSmiles(mol),
                    "formula": rdMolDescriptors.CalcMolFormula(mol),
                    "mass": rdMolDescriptors.CalcExactMolWt(mol),
                }
            )
        return details

    def remove_component(self, index):
        components = self.connected_components()
        components.sort(key=lambda component: min(component))
        if index < 0 or index >= len(components):
            return
        self.push_state()
        for aid in components[index]:
            self.model.remove_atom(aid)
        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()
        if self.model.atoms:
            self.arrange_components_on_grid(push=False)
            self.center_structure()
        self._emit_change()

    def append_smiles(self, smiles):
        mol = self.prepare_smiles_mol(smiles)
        self.push_state()
        self.add_mol_to_model(mol)
        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()
            self._emit_change()
            return

        self.snap_components_to_grid(push=False)

    def prepare_smiles_mol(self, smiles, explicit_hydrogens=False):
        key = (smiles.strip(), bool(explicit_hydrogens))

        if key in self._prepared_smiles_cache:
            return Chem.Mol(self._prepared_smiles_cache[key])

        mol = Chem.MolFromSmiles(key[0])

        if mol is None:
            raise ValueError("Invalid SMILES")

        mol = Chem.Mol(mol)
        rdDepictor.Compute2DCoords(mol)
        if explicit_hydrogens:
            mol = Chem.AddHs(mol, addCoords=True)

        try:
            Chem.Kekulize(mol, clearAromaticFlags=True)
        except Exception:
            pass

        self._prepared_smiles_cache[key] = Chem.Mol(mol)
        return mol

    def add_mol_to_model(self, mol):
        conf = mol.GetConformer()
        rdkit_to_aid = {}

        for atom in mol.GetAtoms():
            pos = conf.GetAtomPosition(atom.GetIdx())
            sym = atom.GetSymbol()

            if sym not in SYM2Z:
                sym = "C"

            aid = self.model.add_atom(pos.x * BOND_LEN, -pos.y * BOND_LEN, sym)
            rdkit_to_aid[atom.GetIdx()] = aid

        for bond in mol.GetBonds():
            a = rdkit_to_aid[bond.GetBeginAtomIdx()]
            b = rdkit_to_aid[bond.GetEndAtomIdx()]
            order = int(round(bond.GetBondTypeAsDouble()))
            order = max(1, min(3, order))
            self.model.bonds[frozenset((a, b))] = order

    def center_structure(self):
        if not self.model.atoms:
            return

        xs = [v[0] for v in self.model.atoms.values()]
        ys = [v[1] for v in self.model.atoms.values()]

        cx = 0.5 * (min(xs) + max(xs))
        cy = 0.5 * (min(ys) + max(ys))

        view_cx, view_cy = self.to_model(self.width() * 0.5, self.height() * 0.5)

        dx = view_cx - cx
        dy = view_cy - cy

        for aid, (x, y, sym) in list(self.model.atoms.items()):
            self.model.atoms[aid] = (x + dx, y + dy, sym)

    def clear_all(self):
        self.push_state()
        self.model.clear()

        self.selected_atom = None
        self.selected_bond = None
        self.selected_atoms.clear()
        self.hover_atom = None
        self.hover_bond = None
        self._clear_drag_state(clear_start=False, clear_chain=False)
        self._clear_move_state()

        self._emit_change()

    def undo(self):
        state = self.history.pop()

        if state is None:
            return

        atoms, bonds, next_aid, selected_atom, selected_bond, selected_atoms = state

        self.model.atoms = atoms
        self.model.bonds = bonds
        self.model.next_aid = next_aid

        self.selected_atom = selected_atom
        self.selected_bond = selected_bond
        self.selected_atoms = set(selected_atoms)
        self.invalidate_model_caches()

        self.hover_atom = None
        self.hover_bond = None
        self._clear_drag_state(clear_start=False, clear_chain=True)
        self._clear_move_state()

        self._emit_change()

    def clean_structure(self, push=True, center=True, emit=True):
        if not self.model.atoms:
            return

        if push:
            self.push_state()

        mol, _, idx_to_atom = self.model.build_mol()
        rdDepictor.Compute2DCoords(mol)

        conf = mol.GetConformer()

        for ridx in range(mol.GetNumAtoms()):
            aid = idx_to_atom[ridx]
            pos = conf.GetAtomPosition(ridx)
            _, _, sym = self.model.atoms[aid]
            self.model.atoms[aid] = (pos.x * BOND_LEN, -pos.y * BOND_LEN, sym)

        if center:
            self.center_structure()

        if emit:
            self._emit_change()

    def save_png(self, filename):
        image = self.export_grid_image(use_svg=False)
        image.save(filename)

    def save_svg(self, filename):
        svg = self.export_grid_image(use_svg=True)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)

    def _emit_change(self, clear_labels=False, update_labels=True):
        if clear_labels or not self.model.atoms:
            self.clear_component_labels()
        elif update_labels:
            self.update_component_labels()

        self.invalidate_model_caches()
        self.changed.emit()
        self._smiles_emit_timer.start(self.status_update_delay_ms)
        self.update()

    def _emit_smiles_changed(self):
        try:
            if not self.model.atoms:
                self.smilesChanged.emit("")
                self.statusSummaryChanged.emit("", "", 0.0)
                return

            mol = self.get_mol()
            smiles = Chem.MolToSmiles(mol)
            formula = rdMolDescriptors.CalcMolFormula(mol)
            mass = rdMolDescriptors.CalcExactMolWt(mol)
            self.smilesChanged.emit(smiles)
            self.statusSummaryChanged.emit(smiles, formula, mass)
        except Exception:
            self.smilesChanged.emit("")
            self.statusSummaryChanged.emit("", "", 0.0)

    def _compute_chain(self, sx, sy, ex, ey, bond_length=None):
        dx = ex - sx
        dy = ey - sy
        length = math.hypot(dx, dy)

        if length < 1e-6:
            return []

        bond_length = BOND_LEN if bond_length is None else bond_length
        n_atoms = max(1, int(round(length / bond_length)))
        angle = math.atan2(dy, dx)
        angle = round(angle / SNAP) * SNAP

        alpha = math.radians(30.0)

        pts = []
        x = sx
        y = sy

        for i in range(n_atoms):
            theta = angle + (alpha if i % 2 == 0 else -alpha)
            x += bond_length * math.cos(theta)
            y += bond_length * math.sin(theta)
            pts.append((x, y))

        return pts

    def _draw_chain_count_badge(self, painter, x, y, count):
        if count <= 0:
            return

        vx, vy = self.to_view(x, y)
        text = str(count)

        painter.save()
        painter.resetTransform()
        painter.setFont(self._chain_count_font)
        metrics = QtGui.QFontMetrics(self._chain_count_font)
        text_rect = metrics.boundingRect(text)
        pad_x = 7
        pad_y = 4
        rect = QtCore.QRectF(
            vx + 10,
            vy - text_rect.height() - 18,
            text_rect.width() + pad_x * 2,
            text_rect.height() + pad_y * 2,
        )

        if rect.right() > self.width() - 6:
            rect.moveRight(self.width() - 6)

        if rect.top() < 6:
            rect.moveTop(vy + 12)

        painter.setPen(self._chain_count_pen)
        painter.setBrush(self._chain_count_fill)
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QtGui.QColor(40, 40, 40))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def add_ring(self, n=6, aromatic=False):
        self.push_state()

        if self.selected_atom is not None and self.selected_atom in self.model.atoms:
            cx, cy, _ = self.model.atoms[self.selected_atom]
            angle0 = 0.0
        else:
            cx, cy = self.to_model(self.width() * 0.5, self.height() * 0.5)
            angle0 = -math.pi / 2.0

        radius = self.nominal_bond_length(self.selected_atom) / (2.0 * math.sin(math.pi / n))

        aids = []

        for i in range(n):
            theta = angle0 + 2.0 * math.pi * i / n
            x = cx + radius * math.cos(theta)
            y = cy + radius * math.sin(theta)
            aids.append(self.model.add_atom(x, y, "C"))

        for i in range(n):
            order = 2 if aromatic and i % 2 == 0 else 1
            self.model.bonds[frozenset((aids[i], aids[(i + 1) % n]))] = order

        self.selected_atom = aids[0]
        self.selected_bond = None
        self.selected_atoms.clear()

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()

        self._emit_change()

    def _nearest_atom_to_model_point(self, x, y, max_distance=NEAR_ATOM):
        best = None
        bestd2 = max_distance * max_distance

        for aid, (ax, ay, _) in self.model.atoms.items():
            d2 = (ax - x) ** 2 + (ay - y) ** 2

            if d2 <= bestd2:
                bestd2 = d2
                best = aid

        return best

    def _commit_ring_vertices(self, vertices, existing=None, bond_orders=None):
        existing = existing or {}
        bond_orders = bond_orders or (1,) * len(vertices)
        self.push_state()

        aids = []

        for index, (x, y) in enumerate(vertices):
            aid = existing.get(index)

            if aid is None:
                candidate = self._nearest_atom_to_model_point(x, y)

                if candidate is not None and candidate not in aids:
                    aid = candidate

            if aid is None:
                aid = self.model.add_atom(x, y, "C")

            aids.append(aid)

        for index, aid in enumerate(aids):
            other = aids[(index + 1) % len(aids)]

            if aid == other:
                continue

            key = frozenset((aid, other))

            if key not in self.model.bonds or bond_orders[index] > 1:
                self.model.bonds[key] = bond_orders[index]

        self.selected_atom = aids[0] if aids else None
        self.selected_bond = None
        self.selected_atoms.clear()

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()

        self._emit_change()

    def _centered_ring_vertices(self, cx, cy, bond_length=None, angle0=-math.pi / 2.0):
        bond_length = BOND_LEN if bond_length is None else bond_length
        radius = bond_length

        return [
            (
                cx + radius * math.cos(angle0 + i * math.pi / 3.0),
                cy + radius * math.sin(angle0 + i * math.pi / 3.0),
            )
            for i in range(6)
        ]

    def _atom_anchored_ring_vertices(self, aid):
        ax, ay, _ = self.model.atoms[aid]
        bond_length = self.nominal_bond_length(aid)
        angle0 = math.pi
        cx = ax - bond_length * math.cos(angle0)
        cy = ay - bond_length * math.sin(angle0)
        return self._centered_ring_vertices(cx, cy, bond_length, angle0)

    def _bond_fused_ring_vertices(self, bond_key, mx, my):
        a, b = tuple(bond_key)
        ax, ay, _ = self.model.atoms[a]
        bx, by, _ = self.model.atoms[b]
        dx = bx - ax
        dy = by - ay
        length = math.hypot(dx, dy)

        if length < 1e-6:
            return None

        ux = dx / length
        uy = dy / length
        nx = -uy
        ny = ux
        side = 1.0 if (mx - ax) * nx + (my - ay) * ny >= 0.0 else -1.0
        nx *= side
        ny *= side
        apothem = math.sqrt(3.0) * 0.5 * length

        return [
            (ax, ay),
            (bx, by),
            (bx + 0.5 * length * ux + apothem * nx, by + 0.5 * length * uy + apothem * ny),
            (bx + math.sqrt(3.0) * length * nx, by + math.sqrt(3.0) * length * ny),
            (ax + math.sqrt(3.0) * length * nx, ay + math.sqrt(3.0) * length * ny),
            (ax - 0.5 * length * ux + apothem * nx, ay - 0.5 * length * uy + apothem * ny),
        ]

    def _place_ring_template_at(self, template_name, mx, my):
        template = RING_TEMPLATES[template_name]

        if template["aromatize_existing"] and self.aromatize_ring_under_selection(template["orders"]):
            return

        if self.hover_bond is not None:
            vertices = self._bond_fused_ring_vertices(self.hover_bond, mx, my)

            if vertices is not None:
                a, b = tuple(self.hover_bond)
                self._commit_ring_vertices(
                    vertices,
                    existing={0: a, 1: b},
                    bond_orders=template["orders"],
                )
                return

        if self.hover_atom is not None:
            vertices = self._atom_anchored_ring_vertices(self.hover_atom)
            self._commit_ring_vertices(
                vertices,
                existing={0: self.hover_atom},
                bond_orders=template["orders"],
            )
            return

        bond_length = self.nominal_bond_length()
        vertices = self._centered_ring_vertices(mx, my, bond_length)
        self._commit_ring_vertices(vertices, bond_orders=template["orders"])

    def add_cyclohexane_at(self, mx, my):
        self._place_ring_template_at("cyclohexane", mx, my)

    def _six_ring_under_selection(self):
        required_atom = self.hover_atom
        required_bond = self.hover_bond

        if required_atom is None and required_bond is not None:
            required_atom = next(iter(required_bond))

        if required_atom is None or required_atom not in self.model.atoms:
            return None

        adjacency = {aid: set() for aid in self.model.atoms}

        for key in self.model.bonds:
            a, b = tuple(key)

            if a in adjacency and b in adjacency:
                adjacency[a].add(b)
                adjacency[b].add(a)

        path = [required_atom]

        def contains_required_bond(candidate):
            if required_bond is None:
                return True

            edges = [
                frozenset((candidate[i], candidate[(i + 1) % len(candidate)]))
                for i in range(len(candidate))
            ]
            return required_bond in edges

        def dfs(current):
            if len(path) == 6:
                if required_atom in adjacency[current] and contains_required_bond(path):
                    return list(path)

                return None

            for nxt in sorted(adjacency[current]):
                if nxt in path:
                    continue

                path.append(nxt)
                ring = dfs(nxt)

                if ring is not None:
                    return ring

                path.pop()

            return None

        return dfs(required_atom)

    def aromatize_ring_under_selection(self, bond_orders=(2, 1, 2, 1, 2, 1)):
        ring = self._six_ring_under_selection()

        if ring is None:
            return False

        keys = [
            frozenset((ring[i], ring[(i + 1) % len(ring)]))
            for i in range(len(ring))
        ]

        if any(self.model.bonds.get(key) != 1 for key in keys):
            return False

        self.push_state()

        for index, key in enumerate(keys):
            self.model.bonds[key] = bond_orders[index]

        self.selected_atom = ring[0]
        self.selected_bond = None
        self.selected_atoms.clear()

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()

        self._emit_change()
        return True

    def add_benzene_at(self, mx, my):
        self._place_ring_template_at("benzene", mx, my)

    def _restore_last_state_without_emitting(self):
        state = self.history.pop()

        if state is None:
            return

        atoms, bonds, next_aid, selected_atom, selected_bond, selected_atoms = state

        self.model.atoms = atoms
        self.model.bonds = bonds
        self.model.next_aid = next_aid
        self.selected_atom = selected_atom
        self.selected_bond = selected_bond
        self.selected_atoms = set(selected_atoms)

    def _ensure_paint_caches(self):
        if self._font_scale != self.scale:
            self._font_scale = self.scale
            self._font.setPointSizeF(14 / self.scale)
            self._small_font.setPointSizeF(9 / self.scale)
            self._bond_pen.setWidthF(3.0 / self.scale)
            self._preview_pen.setWidthF(2.0 / self.scale)
            self._hover_pen.setWidthF(2.0 / self.scale)
            self._sel_pen.setWidthF(2.0 / self.scale)

        for sym, color in ATOM_COLORS.items():
            if sym not in self._atom_pen_cache:
                self._atom_pen_cache[sym] = QtGui.QPen(color)

    def _draw_grid(self, painter):
        step = BOND_LEN
        left = -self.pan_x / self.scale
        top = -self.pan_y / self.scale
        right = (self.width() - self.pan_x) / self.scale
        bottom = (self.height() - self.pan_y) / self.scale

        x0 = math.floor(left / step) * step
        y0 = math.floor(top / step) * step

        pen = QtGui.QPen(QtGui.QColor(235, 238, 238), 1.0 / self.scale)
        painter.setPen(pen)

        x = x0

        while x <= right:
            painter.drawLine(QtCore.QLineF(x, top, x, bottom))
            x += step

        y = y0

        while y <= bottom:
            painter.drawLine(QtCore.QLineF(left, y, right, y))
            y += step

    def visible_model_rect(self, margin=0.0):
        left = -self.pan_x / self.scale - margin
        top = -self.pan_y / self.scale - margin
        right = (self.width() - self.pan_x) / self.scale + margin
        bottom = (self.height() - self.pan_y) / self.scale + margin
        return left, top, right, bottom

    @staticmethod
    def _point_in_rect(x, y, rect):
        left, top, right, bottom = rect
        return left <= x <= right and top <= y <= bottom

    @staticmethod
    def _segment_may_intersect_rect(x1, y1, x2, y2, rect):
        left, top, right, bottom = rect
        return (
            max(x1, x2) >= left
            and min(x1, x2) <= right
            and max(y1, y2) >= top
            and min(y1, y2) <= bottom
        )

    def _draw_bond(self, painter, x1, y1, x2, y2, order):
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy) or 1e-6

        nx = -dy / length
        ny = dx / length

        if order == 1:
            painter.drawLine(QtCore.QLineF(x1, y1, x2, y2))
            return

        if order == 2:
            off = 4.0
            painter.drawLine(QtCore.QLineF(x1 + nx * off, y1 + ny * off, x2 + nx * off, y2 + ny * off))
            painter.drawLine(QtCore.QLineF(x1 - nx * off, y1 - ny * off, x2 - nx * off, y2 - ny * off))
            return

        off = 6.0
        painter.drawLine(QtCore.QLineF(x1, y1, x2, y2))
        painter.drawLine(QtCore.QLineF(x1 + nx * off, y1 + ny * off, x2 + nx * off, y2 + ny * off))
        painter.drawLine(QtCore.QLineF(x1 - nx * off, y1 - ny * off, x2 - nx * off, y2 - ny * off))

    def rebuild_united_atom_label_cache(self):
        bond_order_sums = {aid: 0 for aid in self.model.atoms}
        explicit_h_counts = {aid: 0 for aid in self.model.atoms}

        for key, order in self.model.bonds.items():
            a, b = tuple(key)

            if a not in self.model.atoms or b not in self.model.atoms:
                continue

            bond_order_sums[a] += int(order)
            bond_order_sums[b] += int(order)

            if self.model.atoms[a][2] == "H":
                explicit_h_counts[b] += 1

            if self.model.atoms[b][2] == "H":
                explicit_h_counts[a] += 1

        labels = {}

        for aid, (_, _, sym) in self.model.atoms.items():
            if sym == "H":
                labels[aid] = ""
                continue

            target_valence = {"C": 4, "N": 3, "O": 2, "S": 2}.get(sym)
            implicit_h = 0

            if target_valence is not None:
                implicit_h = max(0, target_valence - bond_order_sums[aid])

            h_count = explicit_h_counts[aid] + implicit_h

            if h_count <= 0:
                labels[aid] = sym
            elif h_count == 1:
                labels[aid] = f"{sym}H"
            else:
                labels[aid] = f"{sym}H{h_count}"

        self._united_atom_label_cache = labels
        self._united_atom_label_cache_dirty = False

    def ensure_united_atom_label_cache(self):
        if self._united_atom_label_cache_dirty:
            self.rebuild_united_atom_label_cache()

    def united_atom_label(self, aid):
        self.ensure_united_atom_label_cache()
        return self._united_atom_label_cache.get(aid, "")

    def _draw_atom_label(self, painter, x, y, label, sym):
        metrics = QtGui.QFontMetricsF(self._font)
        text_rect = metrics.boundingRect(label)
        width = max(24 / self.scale, text_rect.width() + 10 / self.scale)
        height = max(20 / self.scale, text_rect.height() + 4 / self.scale)
        rect = QtCore.QRectF(x - width * 0.5, y - height * 0.5, width, height)

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(252, 252, 251, 235))
        painter.drawRoundedRect(rect, 4 / self.scale, 4 / self.scale)

        painter.setPen(self._atom_pen_cache.get(sym, QtGui.QPen(QtGui.QColor(20, 20, 20))))
        painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, label)

    def _draw_element_circle(self, painter, x, y, symbol):
        style = ATOM_STYLES.get(symbol, DEFAULT_ATOM_STYLE)
        radius = ATOM_CIRCLE_SCALE * float(style["radius"]) / self.scale
        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor(style["outline"]), 1.6 / self.scale))
        painter.setBrush(QtGui.QColor(style["fill"]))
        painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)
        painter.setPen(QtGui.QPen(QtGui.QColor(style["text"])))
        painter.drawText(
            QtCore.QRectF(
                x - radius,
                y - radius,
                2.0 * radius,
                2.0 * radius,
            ),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            symbol,
        )
        painter.restore()

    def _bead_summary_graph(self):
        """Contract mapped atom groups into bead nodes for the Stage 2 preview."""
        atoms = self.model.atoms
        nodes = {}
        atom_to_node = {}

        for index, overlay in enumerate(self.bead_overlays):
            atom_ids = [
                aid
                for aid in overlay.get("atom_ids", [])
                if aid in atoms and aid not in atom_to_node
            ]
            if not atom_ids:
                continue
            node_id = ("bead", index)
            xs = [atoms[aid][0] for aid in atom_ids]
            ys = [atoms[aid][1] for aid in atom_ids]
            nodes[node_id] = {
                "kind": "bead",
                "x": sum(xs) / len(xs),
                "y": sum(ys) / len(ys),
                "label": str(overlay.get("label", "")),
                "color": str(overlay.get("color", "#4f8cff")),
                "atom_ids": atom_ids,
            }
            for aid in atom_ids:
                atom_to_node[aid] = node_id

        for aid, (x, y, sym) in atoms.items():
            if aid in atom_to_node:
                continue
            node_id = ("atom", aid)
            nodes[node_id] = {
                "kind": "atom",
                "x": x,
                "y": y,
                "label": sym,
                "symbol": sym,
                "atom_ids": [aid],
            }
            atom_to_node[aid] = node_id

        edges = {}
        for key, order in self.model.bonds.items():
            first, second = tuple(key)
            if first not in atom_to_node or second not in atom_to_node:
                continue
            first_node = atom_to_node[first]
            second_node = atom_to_node[second]
            if first_node == second_node:
                continue
            edge_key = frozenset((first_node, second_node))
            both_atoms = (
                nodes[first_node]["kind"] == "atom"
                and nodes[second_node]["kind"] == "atom"
            )
            edges[edge_key] = max(edges.get(edge_key, 1), int(order) if both_atoms else 1)

        return nodes, edges

    def _draw_bead_summary(self, painter, visible_rect):
        nodes, edges = self._bead_summary_graph()
        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#53645f"), 2.2 / self.scale))
        for edge, order in edges.items():
            first_node, second_node = tuple(edge)
            first = nodes[first_node]
            second = nodes[second_node]
            if not self._segment_may_intersect_rect(
                first["x"], first["y"], second["x"], second["y"], visible_rect
            ):
                continue
            self._draw_bond(
                painter,
                first["x"],
                first["y"],
                second["x"],
                second["y"],
                order,
            )
        painter.restore()

        painter.setFont(self._font)
        for node in nodes.values():
            x, y = node["x"], node["y"]
            if not self._point_in_rect(x, y, visible_rect):
                continue
            painter.save()
            if node["kind"] == "bead":
                color = QtGui.QColor(node["color"])
                fill = QtGui.QColor(color)
                fill.setAlpha(225)
                painter.setPen(QtGui.QPen(color.darker(125), 2.2 / self.scale))
                painter.setBrush(QtGui.QBrush(fill))
                radius = 20.0 / self.scale
                painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)
                text_color = QtGui.QColor("#ffffff") if color.lightness() < 145 else QtGui.QColor("#285f66")
                painter.setPen(QtGui.QPen(text_color))
                rect = QtCore.QRectF(
                    x - radius,
                    y - radius,
                    2.0 * radius,
                    2.0 * radius,
                )
                painter.drawText(
                    rect,
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    node["label"],
                )
            else:
                symbol = node["symbol"]
                self._draw_element_circle(painter, x, y, symbol)
            painter.restore()

    def _draw_static_layer(self, painter):
        painter.fillRect(self.rect(), QtGui.QColor(252, 252, 251))
        painter.translate(self.pan_x, self.pan_y)
        painter.scale(self.scale, self.scale)

        self._ensure_paint_caches()
        self._draw_grid(painter)

        atoms = self.model.atoms
        bonds = self.model.bonds
        show_united_atoms = self.should_show_united_atoms()
        visible_rect = self.visible_model_rect(margin=2.0 * BOND_LEN)

        if self.bead_summary_mode:
            self._draw_bead_summary(painter, visible_rect)
            return

        if show_united_atoms:
            self.ensure_united_atom_label_cache()

        painter.setPen(self._bond_pen)

        for key, order in bonds.items():
            a, b = tuple(key)

            if a not in atoms or b not in atoms:
                continue

            if show_united_atoms and (atoms[a][2] == "H" or atoms[b][2] == "H"):
                continue

            x1, y1, _ = atoms[a]
            x2, y2, _ = atoms[b]

            if not self._segment_may_intersect_rect(x1, y1, x2, y2, visible_rect):
                continue

            self._draw_bond(painter, x1, y1, x2, y2, order)

        painter.setFont(self._font)

        for aid, (x, y, sym) in atoms.items():
            if not self._point_in_rect(x, y, visible_rect):
                continue

            if self.atom_circle_mode:
                self._draw_element_circle(painter, x, y, sym)
                continue

            if show_united_atoms:
                label = self.united_atom_label(aid)

                if label:
                    self._draw_atom_label(painter, x, y, label, sym)

                continue

            if sym == "C":
                if self.show_carbon_dots:
                    painter.setPen(QtCore.Qt.PenStyle.NoPen)
                    painter.setBrush(self._black_brush)
                    painter.drawEllipse(QtCore.QPointF(x, y), 2.2 / self.scale, 2.2 / self.scale)
                continue

            if sym == "H" and not self.show_h:
                continue

            self._draw_atom_label(painter, x, y, sym, sym)

        if self.component_labels:
            painter.save()
            painter.setFont(self._small_font)
            painter.setPen(QtGui.QPen(QtGui.QColor(70, 70, 70)))

            for label in self.component_labels:
                if not self._point_in_rect(label["x"], label["y"], visible_rect):
                    continue

                text = label["text"]
                metrics = QtGui.QFontMetricsF(self._small_font)
                text_rect = metrics.boundingRect(text)
                rect = QtCore.QRectF(
                    label["x"] - text_rect.width() * 0.5 - 5.0 / self.scale,
                    label["y"] - text_rect.height() * 0.5 - 3.0 / self.scale,
                    text_rect.width() + 10.0 / self.scale,
                    text_rect.height() + 6.0 / self.scale,
                )
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(QtGui.QColor(252, 252, 251, 230))
                painter.drawRoundedRect(rect, 4 / self.scale, 4 / self.scale)
                painter.setPen(QtGui.QPen(QtGui.QColor(70, 70, 70)))
                painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)

            painter.restore()

    def _view_cache_key(self):
        return (
            self.width(),
            self.height(),
            round(self.pan_x, 2),
            round(self.pan_y, 2),
            round(self.scale, 4),
            self.show_h,
            self.show_carbon_dots,
            self.should_show_united_atoms(),
            self.bead_summary_mode,
            self.atom_circle_mode,
            self._antialiasing_enabled(),
        )

    def _is_dynamic_redraw(self):
        return (
            self.aa_dynamic
            and (
                self.panning
                or self.dragging
                or self.preview is not None
                or bool(self.chain_preview)
            )
        )

    def _antialiasing_enabled(self):
        return not self._is_dynamic_redraw()

    def ensure_view_cache(self):
        key = self._view_cache_key()

        if (
            not self._view_cache_dirty
            and self._view_cache is not None
            and self._view_cache_signature == key
        ):
            return

        cache = QtGui.QPixmap(self.size())
        cache.fill(QtGui.QColor(252, 252, 251))
        painter = QtGui.QPainter(cache)
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing,
            self._antialiasing_enabled(),
        )
        self._draw_static_layer(painter)
        painter.end()

        self._view_cache = cache
        self._view_cache_signature = key
        self._view_cache_dirty = False

    def paintEvent(self, _):
        self.ensure_view_cache()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing,
            self._antialiasing_enabled(),
        )
        painter.drawPixmap(0, 0, self._view_cache)
        if self.bead_summary_mode:
            painter.end()
            return
        painter.translate(self.pan_x, self.pan_y)
        painter.scale(self.scale, self.scale)

        self._ensure_paint_caches()

        atoms = self.model.atoms
        bonds = self.model.bonds

        if self._tool_is("chain") and self.chain_preview and self.down_model:
            painter.setPen(self._preview_pen)
            x0, y0 = self.down_model

            for x1, y1 in self.chain_preview:
                painter.drawLine(QtCore.QLineF(x0, y0, x1, y1))
                x0, y0 = x1, y1

            self._draw_chain_count_badge(painter, x0, y0, len(self.chain_preview))

        if not self._tool_is("chain") and self.preview is not None:
            x1, y1, x2, y2, order = self.preview
            painter.setPen(self._preview_pen)
            self._draw_bond(painter, x1, y1, x2, y2, order)

        if self.bead_overlays:
            for overlay in self.bead_overlays:
                color = QtGui.QColor(str(overlay.get("color", "#4f8cff")))
                active = bool(overlay.get("active", False))
                fill = QtGui.QColor(color)
                fill.setAlpha(70 if active else 42)
                pen_color = QtGui.QColor(color)
                pen_color.setAlpha(230 if active else 175)
                painter.save()
                painter.setPen(QtGui.QPen(pen_color, 2.4 if active else 1.6))
                painter.setBrush(QtGui.QBrush(fill))
                radius = 16.0 if active else 14.0
                atom_ids = [aid for aid in overlay.get("atom_ids", []) if aid in atoms]
                for aid in atom_ids:
                    x, y, _ = atoms[aid]
                    painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)
                if active and atom_ids:
                    xs = [atoms[aid][0] for aid in atom_ids]
                    ys = [atoms[aid][1] for aid in atom_ids]
                    painter.setPen(QtGui.QPen(pen_color, 1.0))
                    painter.drawText(QtCore.QPointF(sum(xs) / len(xs) + 11.0, sum(ys) / len(ys) - 11.0), str(overlay.get("label", "")))
                painter.restore()

        if self.selected_atoms:
            painter.save()
            painter.setPen(self._sel_pen)
            # Component selection is deliberately outline-only so the
            # molecule's atoms, bonds and drawing feedback remain unobscured.
            painter.setBrush(self._empty_brush)

            selected = {aid for aid in self.selected_atoms if aid in atoms}
            is_whole_component = bool(selected) and any(
                selected == component for component in self.connected_components()
            )
            if is_whole_component:
                xmin, ymin, xmax, ymax = self.component_bounds(selected)
                padding = 14.0 / self.scale
                rect = QtCore.QRectF(
                    xmin - padding,
                    ymin - padding,
                    max(2.0 * padding, xmax - xmin + 2.0 * padding),
                    max(2.0 * padding, ymax - ymin + 2.0 * padding),
                )
                painter.drawRoundedRect(rect, 7.0 / self.scale, 7.0 / self.scale)
            else:
                for aid in selected:
                    x, y, _ = atoms[aid]
                    painter.drawEllipse(QtCore.QPointF(x, y), 12.0, 12.0)

            painter.restore()

        if self.selected_bond is not None:
            a, b = tuple(self.selected_bond)

            if a in atoms and b in atoms:
                x1, y1, _ = atoms[a]
                x2, y2, _ = atoms[b]

                painter.save()
                painter.setPen(self._sel_pen)
                painter.setBrush(self._empty_brush)
                self._draw_bond(painter, x1, y1, x2, y2, bonds.get(self.selected_bond, 1))
                painter.restore()

        if self.hover_bond is not None:
            a, b = tuple(self.hover_bond)

            if a in atoms and b in atoms:
                x1, y1, _ = atoms[a]
                x2, y2, _ = atoms[b]

                painter.save()
                painter.setPen(self._hover_pen)
                painter.setBrush(self._empty_brush)
                self._draw_bond(painter, x1, y1, x2, y2, bonds.get(self.hover_bond, 1))
                painter.restore()

        if self.selected_atom is not None and self.selected_atom in atoms and not self.selected_atoms:
            x, y, _ = atoms[self.selected_atom]

            painter.save()
            painter.setPen(self._sel_pen)
            painter.setBrush(self._sel_fill)
            painter.drawEllipse(QtCore.QPointF(x, y), 11.0, 11.0)
            painter.restore()

        if self.hover_atom is not None and self.hover_atom in atoms:
            x, y, _ = atoms[self.hover_atom]

            painter.save()
            painter.setPen(self._hover_pen)
            painter.setBrush(self._hover_fill)
            painter.drawEllipse(QtCore.QPointF(x, y), 9.0, 9.0)
            painter.restore()

    def mousePressEvent(self, event):
        self.setFocus()

        x, y = self._event_xy(event)

        if self.selection_only:
            if event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
                self.panning = True
                self.pan_anchor = (x, y)
                return
            if event.button() != QtCore.Qt.MouseButton.LeftButton:
                return
            self.update_hover(x, y)
            aid = self.nearest_atom(x, y)
            if aid is None:
                self.clear_selection()
            elif aid in self.locked_atoms:
                self.selected_atom = aid
                self.selected_bond = None
            elif aid in self.selected_atoms:
                self.selected_atoms.remove(aid)
                self.selected_atom = None
                self.selected_bond = None
            else:
                self.selected_atoms.add(aid)
                self.selected_atom = aid
                self.selected_bond = None
            self.update()
            self.changed.emit()
            return

        if self.read_only:
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                self.update_hover(x, y)
                aid = self.component_at(x, y)
                if aid is not None:
                    self.select_component(aid)
                else:
                    self.clear_selection()
                self.update()
                self.changed.emit()
                return
            if event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
                self.panning = True
                self.pan_anchor = (x, y)
                self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                return

        if event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
            self.panning = True
            self.pan_anchor = (x, y)
            return

        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        self.update_hover(x, y)

        if self._tool_is("cyclohexane"):
            mx, my = self.to_model(x, y)
            self.add_cyclohexane_at(mx, my)
            return

        if self._tool_is("benzene"):
            mx, my = self.to_model(x, y)
            self.add_benzene_at(mx, my)
            return

        if self._tool_is("chain"):
            mx, my = self.to_model(x, y)
            self.down_model = (mx, my)
            self.down_view = (x, y)
            self.start_atom = self.hover_atom
            self.dragging = False
            self.chain_preview = []

            if self.start_atom is not None:
                self.selected_atom = self.start_atom
                self.selected_bond = None
                self._emit_component_selected(self.start_atom)

                if self.start_atom not in self.selected_atoms:
                    self.selected_atoms.clear()

            self.update()
            return

        if self.hover_bond is not None:
            a, b = tuple(self.hover_bond)
            self.push_state()
            self.selected_atom = None
            self.selected_bond = self.hover_bond
            self.model.cycle_or_set_bond(a, b, 1)

            if not self.model.is_valid():
                self._restore_last_state_without_emitting()

            self._emit_change()
            return

        mx, my = self.to_model(x, y)

        self.down_model = (mx, my)
        self.down_view = (x, y)
        self.start_atom = self.hover_atom
        self.dragging = False
        self.preview = None

        if self.start_atom is not None:
            self.selected_atom = self.start_atom
            self.selected_bond = None
            self._emit_component_selected(self.start_atom)

            if self.start_atom not in self.selected_atoms:
                self.selected_atoms.clear()

            self.update()

    def mouseMoveEvent(self, event):
        x, y = self._event_xy(event)

        if self.panning and self.pan_anchor is not None:
            dx = x - self.pan_anchor[0]
            dy = y - self.pan_anchor[1]

            self.pan_x += dx
            self.pan_y += dy
            self.pan_anchor = (x, y)

            self.update()
            return

        hover_changed = self.update_hover(x, y)

        if self._tool_is("chain") and self.down_model is not None:
            mx, my = self.to_model(x, y)
            sx, sy = self.down_model

            if not self.dragging and (mx - sx) ** 2 + (my - sy) ** 2 < 9.0:
                self.update()
                return

            self.dragging = True
            self.chain_preview = self._compute_chain(
                sx,
                sy,
                mx,
                my,
                self.nominal_bond_length(self.start_atom),
            )
            self.update()
            return

        if self.down_model is None:
            if hover_changed:
                self.update()
            return

        mx, my = self.to_model(x, y)
        x0, y0 = self.down_model

        if (mx - x0) ** 2 + (my - y0) ** 2 < 9.0:
            return

        self.dragging = True

        if self.start_atom is not None and self.start_atom in self.model.atoms:
            sx, sy, _ = self.model.atoms[self.start_atom]
        else:
            sx, sy = self.down_model

        if self.hover_atom is not None and self.hover_atom != self.start_atom:
            x2, y2, _ = self.model.atoms[self.hover_atom]
        else:
            x2, y2 = self.snap_end(
                sx,
                sy,
                mx,
                my,
                self.nominal_bond_length(self.start_atom),
            )

        self.preview = (sx, sy, x2, y2, 1)

        self.update()

    def mouseReleaseEvent(self, event):
        x, y = self._event_xy(event)

        if self.selection_only:
            if event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
                self.panning = False
                self.pan_anchor = None
                self.update()
            return

        if self.read_only and event.button() in (
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.RightButton,
            QtCore.Qt.MouseButton.MiddleButton,
        ):
            self.panning = False
            self.pan_anchor = None
            self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
            self.update()
            return

        if event.button() in (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.MiddleButton):
            self.panning = False
            self.pan_anchor = None
            self.update()
            return

        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return

        if self._tool_is("chain"):
            self._release_chain()
            return

        if self.down_model is None:
            return

        self.update_hover(x, y)

        if not self.dragging:
            aid = (
                self.component_background_at(x, y)
                if self.start_atom is None
                else None
            )

            if aid is not None:
                self.select_component(aid)
            elif self.start_atom is None:
                self.clear_selection()

            self._clear_drag_state(clear_start=False, clear_chain=False)
            self.update()
            return

        self.push_state()

        a_was_existing = self.start_atom is not None
        if self.start_atom is None:
            sx, sy = self.down_model
            a = self.model.add_atom(sx, sy, self.active_sym)
        else:
            a = self.start_atom

        if self.hover_atom is not None and self.hover_atom != a:
            b = self.hover_atom
            b_was_existing = True
        else:
            _, _, x2, y2, _ = self.preview
            b = self.nearest_atom(*self.to_view(x2, y2))

            if b is None:
                b = self.model.add_atom(x2, y2, self.active_sym)
                b_was_existing = False
            else:
                b_was_existing = True

        if a_was_existing and b_was_existing:
            component_a = self.connected_component_from_atom(a)
            component_b = self.connected_component_from_atom(b)
            if component_a and component_b and component_a.isdisjoint(component_b):
                self._restore_last_state_without_emitting()
                self._clear_drag_state(clear_start=True, clear_chain=False)
                self.invalidate_model_caches()
                self.update()
                return

        self.model.cycle_or_set_bond(a, b, 1)

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()
        else:
            self.selected_atoms.clear()
            self.selected_atom = b
            self.selected_bond = None
            self._emit_component_selected(b)

        self._clear_drag_state(clear_start=True, clear_chain=False)

        self._emit_change()

    def _release_chain(self):
        if self.down_model is None:
            return

        if not self.dragging:
            x, y = self.down_view
            aid = (
                self.component_background_at(x, y)
                if self.start_atom is None
                else None
            )

            if aid is not None:
                self.select_component(aid)
            elif self.start_atom is None:
                self.clear_selection()

            self._clear_drag_state(clear_start=True, clear_chain=True)
            self.update()
            return

        sx, sy = self.down_model
        pts = self.chain_preview or []

        start = self.start_atom
        self._clear_drag_state(clear_start=True, clear_chain=True)

        if not pts:
            self.update()
            return

        self.push_state()

        if start is None:
            a = self.model.add_atom(sx, sy, "C")
        else:
            a = start

        prev = a

        for x, y in pts:
            b = self.nearest_atom(*self.to_view(x, y))

            if b is None:
                b = self.model.add_atom(x, y, "C")

            self.model.cycle_or_set_bond(prev, b, 1)
            prev = b

        if not self.model.is_valid():
            self._restore_last_state_without_emitting()
        else:
            self.selected_atoms.clear()
            self.selected_atom = prev
            self.selected_bond = None
            self._emit_component_selected(prev)

        self._emit_change()

    def keyPressEvent(self, event):
        if self.read_only or self.selection_only:
            if event.key() == QtCore.Qt.Key.Key_Escape:
                self.clear_selection()
                self.changed.emit()
            return
        key = event.key()
        modifiers = event.modifiers()

        if key in (
                QtCore.Qt.Key.Key_C,
                QtCore.Qt.Key.Key_O,
                QtCore.Qt.Key.Key_N,
                QtCore.Qt.Key.Key_S,
                QtCore.Qt.Key.Key_H,
        ) and not modifiers:
            self.set_atom_symbol(chr(key))
            return

        if key == QtCore.Qt.Key.Key_V and not modifiers:
            self.show_h = not self.show_h
            self.invalidate_view_cache()
            self.update()
            return

        if key == QtCore.Qt.Key.Key_D and not modifiers:
            self.show_carbon_dots = not self.show_carbon_dots
            self.invalidate_view_cache()
            self.update()
            return

        if key == QtCore.Qt.Key.Key_Delete or key == QtCore.Qt.Key.Key_Backspace:
            if self.selected_atoms:
                self.push_state()

                for aid in list(self.selected_atoms):
                    self.model.remove_atom(aid)

                self.selected_atoms.clear()
                self.selected_atom = None
                self.selected_bond = None

                self._emit_change()
                return

            if self.selected_atom is not None:
                self.push_state()
                self.model.remove_atom(self.selected_atom)
                self.selected_atom = None
                self.selected_bond = None
                self._emit_change()
                return

            if self.selected_bond is not None:
                self.push_state()
                self.model.remove_bond_key(self.selected_bond)
                self.selected_bond = None
                self._emit_change()
                return

        if key == QtCore.Qt.Key.Key_Z and modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
            self.undo()
            return

        if key == QtCore.Qt.Key.Key_X and not modifiers:
            self.clear_all()
            return

        if key == QtCore.Qt.Key.Key_Escape:
            self.clear_selection()
            self.hover_atom = None
            self.hover_bond = None
            self._clear_drag_state(clear_start=False, clear_chain=True)
            self._clear_move_state()
            self.update()
            return

    def wheelEvent(self, event):
        mx, my = self._event_xy(event)

        before = self.to_model(mx, my)

        delta = event.angleDelta().y()

        if delta > 0:
            self.scale *= ZOOM_STEP
        else:
            self.scale /= ZOOM_STEP

        self.scale = max(ZOOM_MIN, min(ZOOM_MAX, self.scale))

        after_x = before[0] * self.scale + self.pan_x
        after_y = before[1] * self.scale + self.pan_y

        self.pan_x += mx - after_x
        self.pan_y += my - after_y

        self.update()


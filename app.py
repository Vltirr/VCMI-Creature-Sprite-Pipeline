import json
import os
import re
import sys
import shutil
import base64
from dataclasses import dataclass, asdict
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl, QByteArray, QTimer
from PySide6.QtGui import QPixmap, QDesktopServices, QPainter, QTextCursor, QKeySequence, QShortcut, QTextDocument, QColor, QBrush


def _make_app_icon() -> 'QIcon':
    """Create a simple built-in icon so we don't depend on external .ico files."""
    try:
        from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush, QColor, QFont
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor('#1b5e20')))
        p.setBrush(QBrush(QColor('#2e7d32')))
        p.drawRoundedRect(1, 1, 30, 30, 6, 6)
        p.setPen(QPen(QColor('white')))
        f = QFont(); f.setBold(True); f.setPointSize(16)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, 'V')
        p.end()
        return QIcon(pm)
    except Exception:
        from PySide6.QtGui import QIcon
        return QIcon()
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QCheckBox, QFileDialog,
    QGroupBox, QSpinBox, QMessageBox, QComboBox, QTabWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPlainTextEdit,
    QSplitter, QToolButton, QFrame, QDialog, QScrollArea, QStyle, QColorDialog,

)

CREATURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SETTINGS_FILE = "settings.json"

VALID_GROUPS = [0, 1, 2, 3, 4, 5, 6, 7, 8,  11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51]

GROUP_NAMES = {
    0: '(Basic)Movement',
    1: '(Basic)Mouse over',
    2: '(Basic)Idle',
    3: '(Basic)Hitted',
    4: '(Basic)Defence',
    5: '(Basic)Death',
    6: '(Basic)Death (ranged)',
    7: '(Rotation)Turn left',
    8: '(Rotation)Turn right',
    11: '(Melee)Attack (up)',
    12: '(Melee)Attack (front)',
    13: '(Melee)Attack (down)',
    14: '(Ranged)Shooting (up)',
    15: '(Ranged)Shooting (front)',
    16: '(Ranged)Shooting (down)',
    17: '(Special)Special (up)',
    18: '(Special)Special (front)',
    19: '(Special)Special (down)',
    20: 'Movement start',
    21: 'Movement end',
    22: 'Dead',
    23: 'Dead (ranged)',
    24: 'Resurrection',
    30: '(Spellcast)Cast (up)',
    31: '(Spellcast)Cast (front)',
    32: '(Spellcast)Cast (down)',
    40: '(Group)Group Attack (up)',
    41: '(Group)Group Attack (front)',
    42: '(Group)Group Attack (down)',
    50: 'Teleportation start',
    51: 'Teleportation end',
}


def group_label(gid: int) -> str:
    return f"{gid} — {GROUP_NAMES.get(gid, 'Unknown')}"


@dataclass
class AppSettings:
    scripts_dir: str = "./scripts"
    input_root: str = "./input_root"
    processed_root: str = "./processed_root"
    anim_json_root: str = "./anim_json"
    mod_assets_root: str = ""
    mod_json_root: str = ""
    hex_overlay: str = ""
    overlay_alpha: int = 180
    # Viewer-only: background behind sprites in the GUI (does not modify files)
    viewer_canvas_bg: str = "#404040"

    baseline_y: int = 263
    left_limit_x: int = 174
    left_padding: int = 2
    sprite_h: int = 100
    sprite_w: int = 0
    prefer: str = "height"
    tol: int = 40
    feather: int = 65
    shrink: int = 1
    despill: bool = True
    key_from: str = "each"
    bg_mode: str = "global"

    split_cols: int = 6
    split_rows: int = 6
    split_autocrop: bool = True

    window_geometry_b64: str = ""
    window_maximized: bool = False

    # UI state persistence
    ui_state_version: int = 0
    ui_paths_expanded: bool = False
    ui_params_expanded: bool = False
    ui_log_expanded: bool = False
    ui_splitter_sizes: list[int] = None

    # Viewer-only: background behind sprites in the GUI (does not modify files)


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        s = AppSettings()
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s
    except Exception:
        return AppSettings()


def save_settings(path: Path, settings: AppSettings):
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def script_path(scripts_dir: str, name: str) -> str:
    return str(Path(scripts_dir) / name)


def quote_cmd(cmd: list[str]) -> str:
    return " ".join([f'"{x}"' if " " in x else x for x in cmd])


def is_nonempty(p: str) -> bool:
    return p.strip() != ""


def exists_dir(p: str) -> bool:
    try:
        return p.strip() != "" and Path(p).exists() and Path(p).is_dir()
    except Exception:
        return False


def exists_file(p: str) -> bool:
    try:
        return p.strip() != "" and Path(p).exists() and Path(p).is_file()
    except Exception:
        return False


def safe_clear_dir_contents(folder: Path) -> tuple[int, int]:
    if not folder.exists() or not folder.is_dir():
        return (0, 0)
    files = 0
    dirs = 0
    for p in folder.iterdir():
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
                files += 1
            elif p.is_dir():
                shutil.rmtree(p)
                dirs += 1
        except Exception:
            pass
    return files, dirs


class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def set_image(self, path: Path | None):
        if not path or not path.exists():
            self._pixmap_item.setPixmap(QPixmap())
            self._scene.setSceneRect(0, 0, 1, 1)
            return
        pm = QPixmap(str(path))
        self._pixmap_item.setPixmap(pm)
        self._scene.setSceneRect(pm.rect())
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        factor = 1.20 if event.angleDelta().y() > 0 else 1 / 1.20
        self.scale(factor, factor)


class LogDialog(QDialog):
    """Pop-out log viewer with Find."""
    def __init__(self, parent, html_provider):
        super().__init__(parent)
        self.setWindowTitle("Log (Pop-out)")
        self.resize(1100, 700)
        self.html_provider = html_provider

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText("Find…")
        self.btn_find_next = QPushButton("Next")
        self.btn_find_prev = QPushButton("Prev")
        self.btn_refresh = QPushButton("Refresh")
        top.addWidget(self.find_box, 1)
        top.addWidget(self.btn_find_prev)
        top.addWidget(self.btn_find_next)
        top.addWidget(self.btn_refresh)
        root.addLayout(top)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        root.addWidget(self.text, 1)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_find_next.clicked.connect(lambda: self.find(direction="next"))
        self.btn_find_prev.clicked.connect(lambda: self.find(direction="prev"))
        self.find_box.returnPressed.connect(lambda: self.find(direction="next"))

        self.refresh()

    def refresh(self):
        self.text.setHtml(self.html_provider())

    def find(self, direction="next"):
        needle = self.find_box.text()
        if not needle:
            return
        flags = QTextDocument.FindFlags()
        if direction == "prev":
            flags |= QTextDocument.FindBackward
        # Use QTextEdit's built-in find
        found = self.text.find(needle, flags)
        if not found:
            # wrap-around
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.Start if direction == "next" else QTextCursor.End)
            self.text.setTextCursor(cursor)
            self.text.find(needle, flags)


# QTextDocument is used in LogDialog.find() flags
from PySide6.QtGui import QTextDocument


class PipelineRunner(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VCMI Creature Sprite Pipeline")
        self.setWindowIcon(_make_app_icon())
        # Fallback size; real geometry restored/centered on first show.
        self.resize(1400, 900)
        self.setMinimumSize(1100, 700)
        self._window_restored = False

        self.settings_path = Path(SETTINGS_FILE)
        self.s = load_settings(self.settings_path)

        self.proc: QProcess | None = None
        self.queue: list[list[str]] = []
        self.current_step = "ui"

        # Viewer animation
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._anim_tick)
        self.anim_playing = False
        self.anim_fps = 12
        self.anim_timer.setInterval(int(1000 / self.anim_fps))
        self.anim_loop = True
        self._build_ui()
        self._apply_tooltips()
        self._load_to_ui()
        # Expand Paths if key fields are missing (first run)
        if not self.le_scripts_dir.text().strip():
            self.btn_toggle_paths.setChecked(True)
        self._wire_dynamic_ui()
        self.refresh_ui_state()

        self.viewer_refresh_all(keep_selection=False)
        self.json_refresh_all(keep_selection=False)

        # Restore persisted UI state (collapses + splitter sizes)
        QTimer.singleShot(0, self._apply_persisted_ui_state)

        self.log_dialog: LogDialog | None = None

    # ---------------- window geometry ----------------
    def _center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(max(geo.x(), x), max(geo.y(), y))

    def _restore_window_geometry(self):
        # Restore saved geometry if present; otherwise center.
        b64 = (self.s.window_geometry_b64 or "").strip()
        if b64:
            try:
                ba = QByteArray.fromBase64(b64.encode("ascii"))
                if not ba.isEmpty():
                    self.restoreGeometry(ba)
            except Exception:
                pass
        else:
            self._center_on_screen()

        if getattr(self.s, "window_maximized", False):
            self.setWindowState(self.windowState() | Qt.WindowMaximized)

    def showEvent(self, event):
        super().showEvent(event)
        if self._window_restored:
            return
        self._window_restored = True
        # Defer so Qt has final DPI/screen info.
        QTimer.singleShot(0, self._restore_window_geometry)

    def _apply_persisted_ui_state(self):
        """Restore collapsible group states + splitter sizes."""
        try:
            first_run = not bool(getattr(self.s, "ui_state_version", 0))

            if hasattr(self, "btn_toggle_paths"):
                self.btn_toggle_paths.setChecked(bool(getattr(self.s, "ui_paths_expanded", False)))
            if hasattr(self, "btn_toggle_params"):
                self.btn_toggle_params.setChecked(bool(getattr(self.s, "ui_params_expanded", False)))

            log_on = bool(getattr(self.s, "ui_log_expanded", False))
            if first_run:
                log_on = False
            if hasattr(self, "btn_toggle_log"):
                self.btn_toggle_log.setChecked(log_on)

            sizes = getattr(self.s, "ui_splitter_sizes", None)
            if isinstance(sizes, list) and len(sizes) == 2 and all(isinstance(x, int) for x in sizes):
                if hasattr(self, "splitter"):
                    self.splitter.setSizes(sizes)
        except Exception:
            pass

    def _capture_ui_state(self):
        """Capture current UI state into settings."""
        try:
            self.s.ui_state_version = 1
            if hasattr(self, "btn_toggle_paths"):
                self.s.ui_paths_expanded = bool(self.btn_toggle_paths.isChecked())
            if hasattr(self, "btn_toggle_params"):
                self.s.ui_params_expanded = bool(self.btn_toggle_params.isChecked())
            if hasattr(self, "btn_toggle_log"):
                self.s.ui_log_expanded = bool(self.btn_toggle_log.isChecked())
            if hasattr(self, "splitter"):
                self.s.ui_splitter_sizes = [int(x) for x in self.splitter.sizes()]
        except Exception:
            pass

    def closeEvent(self, event):
        # Persist window geometry + UI state.
        try:
            self.s.window_geometry_b64 = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.s.window_maximized = bool(self.windowState() & Qt.WindowMaximized)
        except Exception:
            pass

        try:
            self._capture_ui_state()
        except Exception:
            pass

        try:
            save_settings(self.settings_path, self.s)
        except Exception:
            pass

        super().closeEvent(event)

    def _ensure_splitter_log_visible(self):
        # Ensure the log header remains usable when collapsed.
        try:
            collapsed = hasattr(self, "log_body") and (not self.log_body.isVisible())
            header_h = 56
            self.gb_log.setMinimumHeight(header_h if collapsed else 110)
            sizes = self.splitter.sizes() if hasattr(self, "splitter") else []
            if sizes and len(sizes) >= 2:
                total = max(1, sum(sizes))
                if collapsed and sizes[1] < header_h:
                    self.splitter.setSizes([max(200, total - header_h), header_h])
                elif (not collapsed) and sizes[1] < 60:
                    self.splitter.setSizes([max(200, total - 140), 140])
        except Exception:
            pass

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # /* UI polish */
        self.setStyleSheet(
    "QWidget { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e3ecf9, stop:1 #cfdcf0); }"
    "QGroupBox { background: #e9f1fb; font-weight: 600; border: 1px solid #b7c6d8; border-radius: 10px; margin-top: 10px; }"
    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #223; }"
    "QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit { background: #fbfdff; border: 1px solid #b7c6d8; border-radius: 7px; padding: 4px 7px; }"
    "QPushButton { background: #f7faff; border: 1px solid #b7c6d8; border-radius: 7px; padding: 6px 10px; }"
    "QPushButton:hover { background: #e3efff; }"
    "QToolButton { background: transparent; }"
    "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus { border: 1px solid #4A90E2; }"

    "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #8aa0b8; border-radius: 3px; background: #fbfdff; }"

    "QCheckBox::indicator:checked { background: #4A90E2; border: 1px solid #2f6fb9; }"

    "QCheckBox::indicator:checked:pressed { background: #3b7fc9; }"

    "QTabBar::tab { background: #e9f1fb; border: 1px solid #b7c6d8; padding: 6px 10px; border-top-left-radius: 7px; border-top-right-radius: 7px; }"

    "QTabBar::tab:selected { background: #fbfdff; border-bottom-color: #fbfdff; }"

    "QTabWidget::pane { border: 1px solid #b7c6d8; border-radius: 8px; top: -1px; }"

    "QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }"

    "QScrollBar::handle:vertical { background: #b7c6d8; border-radius: 6px; min-height: 24px; }"

    "QScrollBar::handle:vertical:hover { background: #9db0c7; }"
)

        # Tooltip text helpers (keep these in sync with SCRIPTS_DOC.md)
        paths_tt = {
            "Scripts Folder": "Folder containing pipeline scripts (slice_sheet.py, process_frames.py, build_anim_json.py, deploy_assets.py).",
            "Input Root (Raw Frames)": "Working input folder. Expected structure: input_root/<creature_id>/groupN/*.png",
            "Processed Root (450x400)": "Processed 450×400 outputs. Structure: processed_root/<creature_id>/groupN/*.png",
            "Anim Json Root (Generated)": "Where generated <creature_id>.json files are written.",
            "Mod Assets Root (Deploy PNGs)": "Destination root in your mod for battle PNGs (deploy target).",
            "Mod Json Root (Deploy Json)": "Destination root in your mod for <creature_id>.json files (deploy target).",
            "Hex Overlay (Optional PNG)": "Optional 450×400 PNG overlay (hex guide) used by previews in process_frames.py.",
        }

        params_tt = {
            "Baseline Y": "Vertical baseline used to place the sprite on the 450×400 canvas.",
            "Left Limit X": "X reference line when x_mode=left_limit (aligns sprite to left of hex).",
            "Left Padding": "Extra padding relative to Left Limit X.",
            "Sprite Height": "Target sprite height in pixels. Set to 0 to disable height-based scaling and enable Sprite Width.",
            "Sprite Width": "Target sprite width in pixels (used when Sprite Height is 0).",
            "Prefer": "If both width and height are non-zero, choose which dimension wins (avoid distortion).",
            "Dimension Preference": "If both width and height are non-zero, choose which dimension wins (avoid distortion).",
            "Tolerance": "Chroma-key tolerance (0–255). Higher = removes more colors similar to the key (more aggressive background removal), but may start eating into the sprite. Lower = safer for the sprite, but may leave more background/halo.",
            "Feather": "Edge feather/softening (0–255). Higher = smoother, softer alpha edge (reduces jaggies) but can look blurry or expand semi-transparent halo; lower = crisper edge but can look rough. Most noticeable with bg_mode=border.",
            "Shrink": "Alpha erosion (0=off). Helps reduce halos but can eat thin details.",
            "Key From": "Background key sampling: each frame or first frame of group.",
            "Overlay Alpha": "Opacity of the hex overlay in previews (0–255).",
            "Bg Mode": "Background removal mode: global (anywhere) or border (flood-fill from edges).",
            "Despill": "Reduces magenta/green spill from chroma key backgrounds.",
        }

        # -------- Paths --------
        self.gb_paths = QGroupBox("Paths")
        pg = QGridLayout(self.gb_paths)
        pg.setHorizontalSpacing(8)
        pg.setVerticalSpacing(5)

        self.le_scripts_dir = QLineEdit()
        self.le_input_root = QLineEdit()
        self.le_processed_root = QLineEdit()
        self.le_anim_json_root = QLineEdit()
        self.le_mod_assets_root = QLineEdit()
        self.le_mod_json_root = QLineEdit()
        self.le_hex_overlay = QLineEdit()

        def add_path_row(row, label_text, le: QLineEdit, is_dir=True):
            lab = QLabel(label_text)
            tip = paths_tt.get(label_text, "")
            if tip:
                lab.setToolTip(tip)
                le.setToolTip(tip)
            pg.addWidget(lab, row, 0)
            pg.addWidget(le, row, 1)
            btn = QPushButton("Browse…")
            if tip:
                btn.setToolTip(tip)
            pg.addWidget(btn, row, 2)

            def browse():
                start = le.text().strip() or os.getcwd()
                if is_dir:
                    d = QFileDialog.getExistingDirectory(self, f"Select {label_text}", start)
                    if d:
                        le.setText(d)
                else:
                    f, _ = QFileDialog.getOpenFileName(self, f"Select {label_text}", start, "All Files (*)")
                    if f:
                        le.setText(f)

            btn.clicked.connect(browse)
            return lab, le

        self.lb_scripts_dir, _ = add_path_row(0, "Scripts Folder", self.le_scripts_dir, True)
        self.lb_input_root, _ = add_path_row(1, "Input Root (Raw Frames)", self.le_input_root, True)
        self.lb_processed_root, _ = add_path_row(2, "Processed Root (450x400)", self.le_processed_root, True)
        self.lb_anim_json_root, _ = add_path_row(3, "Anim Json Root (Generated)", self.le_anim_json_root, True)
        self.lb_mod_assets_root, _ = add_path_row(4, "Mod Assets Root (Deploy PNGs)", self.le_mod_assets_root, True)
        self.lb_mod_json_root, _ = add_path_row(5, "Mod Json Root (Deploy Json)", self.le_mod_json_root, True)
        self.lb_hex_overlay, _ = add_path_row(6, "Hex Overlay (Optional PNG)", self.le_hex_overlay, False)

        # Toolbar row: Save + Reset/Clears (left), Run/Stop (right)
        self.btn_save = QPushButton("Save")
        self.btn_reset_paths = QPushButton("Reset Defaults")
        self.btn_clear_input = QPushButton("Clear Input")
        self.btn_clear_outputs = QPushButton("Clear Outputs")

        self.btn_run = QPushButton("Run")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)

        for b in [self.btn_save, self.btn_reset_paths, self.btn_clear_input, self.btn_clear_outputs]:
            b.setMinimumWidth(140)
        for b in [self.btn_run, self.btn_stop]:
            b.setMinimumWidth(116)

        bar = QHBoxLayout()
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_reset_paths)
        bar.addWidget(self.btn_clear_input)
        bar.addWidget(self.btn_clear_outputs)
        bar.addStretch(1)
        bar.addWidget(self.btn_run)
        bar.addWidget(self.btn_stop)

        self.btn_save.clicked.connect(self.on_save)
        self.btn_reset_paths.clicked.connect(self.reset_paths_defaults)
        self.btn_clear_input.clicked.connect(self.clear_input_root)
        self.btn_clear_outputs.clicked.connect(self.clear_outputs)
        self.btn_run.clicked.connect(self.on_run)
        self.btn_stop.clicked.connect(self.on_stop)

        # -------- Paths (collapsible body; actions always visible) --------
        self.btn_toggle_paths = QToolButton()
        self.btn_toggle_paths.setCheckable(True)
        self.btn_toggle_paths.setChecked(False)  # collapsed by default
        self.btn_toggle_paths.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.btn_toggle_paths.setToolTip("Show/Hide path fields")

        paths_header = QHBoxLayout()
        paths_header.addWidget(self.btn_toggle_paths)
        paths_header.addWidget(QLabel("Paths"))
        paths_header.addSpacing(8)
        paths_header.addWidget(self.btn_save)
        paths_header.addWidget(self.btn_reset_paths)
        paths_header.addWidget(self.btn_clear_input)
        paths_header.addWidget(self.btn_clear_outputs)
        paths_header.addStretch(1)
        root.addLayout(paths_header)
        sep_paths = QFrame()
        sep_paths.setFrameShape(QFrame.HLine)
        sep_paths.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep_paths)

        root.addWidget(self.gb_paths)
        self.gb_paths.setVisible(False)

        def _toggle_paths():
            on = self.btn_toggle_paths.isChecked()
            self.gb_paths.setVisible(on)
            self.btn_toggle_paths.setIcon(
                self.style().standardIcon(QStyle.SP_ArrowDown if on else QStyle.SP_ArrowRight)
            )

        self.btn_toggle_paths.toggled.connect(lambda _=None: _toggle_paths())


        # -------- Scope + Steps + Split (compact row) --------
        row2 = QHBoxLayout()

        self.gb_scope = QGroupBox("Scope (Optional)")
        sg = QGridLayout(self.gb_scope)
        sg.setHorizontalSpacing(8)
        sg.setVerticalSpacing(4)

        self.lb_scope_creature = QLabel("Creature")
        self.lb_scope_group = QLabel("Group")

        self.le_only_creature = QLineEdit()
        self.le_only_creature.setPlaceholderText("e.g. goblin_darter (empty = all)")

        self.cb_only_group = QComboBox()
        self.cb_only_group.addItem("All", None)
        for g in VALID_GROUPS:
            self.cb_only_group.addItem(group_label(g), g)

        sg.addWidget(self.lb_scope_creature, 0, 0)
        sg.addWidget(self.le_only_creature, 0, 1)
        sg.addWidget(self.lb_scope_group, 1, 0)
        sg.addWidget(self.cb_only_group, 1, 1)

        row2.addWidget(self.gb_scope, 1)

        self.gb_steps = QGroupBox("Pipeline Steps")
        st = QVBoxLayout(self.gb_steps)
        st.setSpacing(4)

        self.chk_split = QCheckBox("Split Spritesheet")
        self.chk_process = QCheckBox("Process Frames")
        self.chk_json = QCheckBox("Build Json")
        self.chk_deploy = QCheckBox("Deploy")

        # Default: no steps selected
        self.chk_split.setChecked(False)
        self.chk_process.setChecked(False)
        self.chk_json.setChecked(False)
        self.chk_deploy.setChecked(False)


        st.addWidget(self.chk_split)
        st.addWidget(self.chk_process)
        st.addWidget(self.chk_json)
        st.addWidget(self.chk_deploy)

        steps_btns = QHBoxLayout()
        self.btn_steps_all = QPushButton("All")
        self.btn_steps_none = QPushButton("None")
        self.btn_steps_all.setMinimumWidth(64)
        self.btn_steps_none.setMinimumWidth(64)
        steps_btns.addWidget(self.btn_steps_all)
        steps_btns.addWidget(self.btn_steps_none)
        steps_btns.addStretch(1)
        st.addLayout(steps_btns)

        row2.addWidget(self.gb_steps, 1)

        self.gb_split = QGroupBox("Split Options")
        so = QGridLayout(self.gb_split)
        so.setHorizontalSpacing(8)
        so.setVerticalSpacing(4)

        self.lb_sheet = QLabel("Spritesheet")
        self.lb_cols = QLabel("Cols")
        self.lb_rows = QLabel("Rows")

        self.le_sheet = QLineEdit()
        self.le_sheet.setPlaceholderText("Spritesheet file path")

        self.btn_sheet = QPushButton("Browse…")
        self.sp_cols = QSpinBox(); self.sp_cols.setRange(1, 200)
        self.sp_rows = QSpinBox(); self.sp_rows.setRange(1, 200)
        self.chk_autocrop = QCheckBox("Auto Crop")

        so.addWidget(self.lb_sheet, 0, 0)
        so.addWidget(self.le_sheet, 0, 1)
        so.addWidget(self.btn_sheet, 0, 2)
        so.addWidget(self.lb_cols, 1, 0)
        so.addWidget(self.sp_cols, 1, 1)
        so.addWidget(self.lb_rows, 2, 0)
        so.addWidget(self.sp_rows, 2, 1)
        so.addWidget(self.chk_autocrop, 3, 1)

        def browse_sheet():
            f, _ = QFileDialog.getOpenFileName(
                self, "Select Spritesheet", os.getcwd(),
                "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
            )
            if f:
                self.le_sheet.setText(f)

        self.btn_sheet.clicked.connect(browse_sheet)

        row2.addWidget(self.gb_split, 2)

        # -------- Run/Stop (primary actions) --------
        self.gb_run = QGroupBox("")
        rr = QVBoxLayout(self.gb_run)
        rr.setContentsMargins(8, 8, 8, 8)
        rr.setSpacing(8)
        self.gb_run.setFixedWidth(132)

        # Make RUN visually primary
        self.btn_run.setText("RUN ▶")
        f = self.btn_run.font()
        f.setBold(True)
        f.setPointSize(max(10, f.pointSize() + 1))
        self.btn_run.setFont(f)
        self.btn_run.setMinimumHeight(46)
        self.btn_run.setStyleSheet(
            "QPushButton { background-color: #2E7D32; color: white; border: 1px solid #1B5E20; border-radius: 6px; }"
            "QPushButton:hover { background-color: #388E3C; }"
            "QPushButton:disabled { background-color: #9E9E9E; color: #eeeeee; border: 1px solid #888; }"
        )

        self.btn_stop.setText("STOP ■")
        self.btn_stop.setMinimumHeight(38)
        self.btn_stop.setStyleSheet(
            "QPushButton { border: 1px solid #B71C1C; border-radius: 6px; }"
            "QPushButton:hover { background-color: #FFEBEE; }"
        )

        rr.addWidget(self.btn_run)
        rr.addWidget(self.btn_stop)
        rr.addStretch(1)

        row2.addWidget(self.gb_run, 0)

        root.addLayout(row2)
        sep_row2 = QFrame()
        sep_row2.setFrameShape(QFrame.HLine)
        sep_row2.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep_row2)

        # -------- Collapsible Process Defaults --------
        self.gb_params_outer = QGroupBox("")
        outer = QVBoxLayout(self.gb_params_outer)

        params_header = QHBoxLayout()
        self.lb_params_title = QLabel("Process Frames Defaults (process_frames.py)")
        self.btn_toggle_params = QToolButton()
        self.btn_toggle_params.setCheckable(True)
        self.btn_toggle_params.setChecked(False)
        self.btn_toggle_params.setAutoRaise(True)
        self.btn_toggle_params.setToolTip("Show/Hide defaults")
        # Arrow icon (right = collapsed, down = expanded)
        self._ico_arrow_right = self.style().standardIcon(QStyle.SP_ArrowRight)
        self._ico_arrow_down = self.style().standardIcon(QStyle.SP_ArrowDown)
        self.btn_toggle_params.setIcon(self._ico_arrow_right)

        params_header.addWidget(self.btn_toggle_params)
        params_header.addWidget(self.lb_params_title)
        params_header.addStretch(1)
        outer.addLayout(params_header)

        self.params_body = QWidget()
        pr = QGridLayout(self.params_body)
        pr.setHorizontalSpacing(10)
        pr.setVerticalSpacing(6)
        pr.setColumnStretch(0, 0)
        pr.setColumnStretch(1, 1)
        pr.setColumnStretch(2, 0)
        pr.setColumnStretch(3, 1)
        pr.setColumnStretch(4, 0)
        pr.setColumnStretch(5, 1)

        def add_param(row, col_pair, label_text, widget):
            if col_pair == 0:
                col = 0
            elif col_pair == 1:
                col = 2
            else:
                col = 4
            lab = QLabel(label_text)
            lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lab.setMinimumWidth(110)
            tip = params_tt.get(label_text, "")
            if tip:
                lab.setToolTip(tip)
                widget.setToolTip(tip)
            pr.addWidget(lab, row, col, alignment=Qt.AlignLeft)
            pr.addWidget(widget, row, col + 1, alignment=Qt.AlignLeft)
            widget.setMinimumWidth(120)
            return lab, widget

        self.sp_baseline_y = QSpinBox(); self.sp_baseline_y.setRange(0, 10000)
        self.sp_left_limit_x = QSpinBox(); self.sp_left_limit_x.setRange(0, 10000)
        self.sp_left_padding = QSpinBox(); self.sp_left_padding.setRange(-999, 999)
        self.sp_sprite_h = QSpinBox(); self.sp_sprite_h.setRange(0, 10000)
        self.sp_sprite_w = QSpinBox(); self.sp_sprite_w.setRange(0, 10000)
        self.cb_prefer = QComboBox(); self.cb_prefer.addItems(["height", "width"])

        self.sp_tol = QSpinBox(); self.sp_tol.setRange(0, 255)
        self.sp_feather = QSpinBox(); self.sp_feather.setRange(0, 255)
        self.sp_shrink = QSpinBox(); self.sp_shrink.setRange(0, 10)

        self.chk_despill = QCheckBox("Despill")
        self.cb_key_from = QComboBox(); self.cb_key_from.addItems(["each", "first"])
        self.cb_bg_mode = QComboBox(); self.cb_bg_mode.addItems(["global", "border"])
        self.sp_overlay_alpha = QSpinBox(); self.sp_overlay_alpha.setRange(0, 255)

        # ---- Group headers ----
        lbl_pos = QLabel("Position & Size")
        lbl_pos.setStyleSheet("font-weight: 600;")
        lbl_bg = QLabel("Background Removal")
        lbl_bg.setStyleSheet("font-weight: 600;")
        lbl_prev = QLabel("Preview")
        lbl_prev.setStyleSheet("font-weight: 600;")
        pr.addWidget(lbl_pos, 0, 0, 1, 2)
        pr.addWidget(lbl_bg, 0, 2, 1, 2)
        pr.addWidget(lbl_prev, 0, 4, 1, 2)

        # ---- Position & Size (left column) ----
        add_param(1, 0, "Baseline Y", self.sp_baseline_y)
        add_param(2, 0, "Left Limit X", self.sp_left_limit_x)
        add_param(3, 0, "Left Padding", self.sp_left_padding)
        add_param(4, 0, "Sprite Height", self.sp_sprite_h)
        add_param(5, 0, "Sprite Width", self.sp_sprite_w)
        add_param(6, 0, "Dimension Preference", self.cb_prefer)

        # ---- Background Removal (middle column) ----
        add_param(1, 1, "Tolerance", self.sp_tol)
        add_param(2, 1, "Feather", self.sp_feather)
        add_param(3, 1, "Bg Mode", self.cb_bg_mode)
        add_param(4, 1, "Shrink", self.sp_shrink)
        add_param(5, 1, "Key From", self.cb_key_from)
        pr.addWidget(self.chk_despill, 6, 2, 1, 2)

        # ---- Preview (right column) ----
        add_param(1, 2, "Overlay Alpha", self.sp_overlay_alpha)

        outer.addWidget(self.params_body)
        self.params_body.setVisible(False)
        def _toggle_params(checked: bool):
            self.params_body.setVisible(checked)
            self.btn_toggle_params.setIcon(self._ico_arrow_down if checked else self._ico_arrow_right)

            self._ensure_splitter_log_visible()

        self.btn_toggle_params.toggled.connect(_toggle_params)
        root.addWidget(self.gb_params_outer)

        # -------- Viewer + Log (vertical splitter) --------
        self.splitter = QSplitter(Qt.Vertical)

        # Viewer group (top)
        self.gb_view = QGroupBox("Viewer")
        vbox = QVBoxLayout(self.gb_view)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # Images tab: left controls panel + big image on right
        self.tab_images = QWidget()
        images_row = QHBoxLayout(self.tab_images)

        self.images_controls = QFrame()
        self.images_controls.setFrameShape(QFrame.StyledPanel)
        controls = QVBoxLayout(self.images_controls)
        controls.setSpacing(6)
        controls.setContentsMargins(6, 6, 6, 6)

        self.cb_view_source = QComboBox()
        self.cb_view_source.addItems([
            "Input (Raw Frames)",
            "Processed (450x400)",
            "Previews",
            "Cleaned (Alpha)",
            "Forced (Solid BG)",
            "Deployed (Mod Assets)",
        ])

        self.cb_view_creature = QComboBox()
        self.cb_view_group = QComboBox()
        self.cb_view_frame = QComboBox()

        self.btn_view_refresh = QPushButton("Refresh")
        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_prev = QPushButton("Prev (A)")
        self.btn_next = QPushButton("Next (D)")

        controls.addWidget(QLabel("Source"))
        controls.addWidget(self.cb_view_source)
        controls.addWidget(self.btn_view_refresh)

        controls.addSpacing(6)
        controls.addWidget(QLabel("Creature"))
        controls.addWidget(self.cb_view_creature)

        controls.addWidget(QLabel("Group"))
        controls.addWidget(self.cb_view_group)

        controls.addWidget(QLabel("Frame"))
        controls.addWidget(self.cb_view_frame)

        controls.addSpacing(6)
        controls.addWidget(self.btn_open_folder)

        # Viewer-only background (does NOT affect generated PNG previews)
        controls.addSpacing(6)
        controls.addWidget(QLabel("Canvas BG"))
        self.le_canvas_bg = QLineEdit()
        self.le_canvas_bg.setPlaceholderText("#RRGGBB or empty")
        self.btn_pick_canvas_bg = QToolButton()
        self.btn_pick_canvas_bg.setText("…")
        self.btn_pick_canvas_bg.setAutoRaise(True)
        wbg = QWidget()
        hb_bg = QHBoxLayout(wbg)
        hb_bg.setContentsMargins(0, 0, 0, 0)
        hb_bg.setSpacing(6)
        hb_bg.addWidget(self.le_canvas_bg, 1)
        hb_bg.addWidget(self.btn_pick_canvas_bg)
        controls.addWidget(wbg)

        nav = QHBoxLayout()
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.btn_next)
        controls.addLayout(nav)

        # Animation controls (viewer only)
        controls.addSpacing(6)
        self.btn_anim_play = QPushButton("Play")
        self.btn_anim_play.setToolTip("Play/Pause animation (Space)")
        self.cb_anim_fps = QComboBox()
        for v in [6, 10, 12, 15, 20, 24]:
            self.cb_anim_fps.addItem(f"{v} fps", v)
        self.cb_anim_fps.setCurrentIndex(self.cb_anim_fps.findData(12))
        self.chk_anim_loop = QCheckBox("Loop")
        self.chk_anim_loop.setChecked(True)
        controls.addWidget(self.btn_anim_play)
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS"))
        fps_row.addWidget(self.cb_anim_fps, 1)
        controls.addLayout(fps_row)
        controls.addWidget(self.chk_anim_loop)

        controls.addStretch(1)
        self.images_controls.setMaximumWidth(300)

        # Keep controls usable even when vertical space is tight
        self.images_controls_scroll = QScrollArea()
        self.images_controls_scroll.setWidgetResizable(True)
        self.images_controls_scroll.setFrameShape(QFrame.NoFrame)
        self.images_controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.images_controls_scroll.setWidget(self.images_controls)
        self.images_controls_scroll.setMaximumWidth(320)

        self.viewer = ImageView()

        images_row.addWidget(self.images_controls_scroll, 0)
        images_row.addWidget(self.viewer, 1)

        self.tabs.addTab(self.tab_images, "Images")

        # JSON tab
        self.tab_json = QWidget()
        jv = QGridLayout(self.tab_json)
        jv.setHorizontalSpacing(8)
        jv.setVerticalSpacing(5)

        self.cb_json_source = QComboBox()
        self.cb_json_source.addItems([
            "Generated JSON (anim_json_root)",
            "Deployed JSON (mod_json_root)",
        ])
        self.cb_json_creature = QComboBox()
        self.btn_json_refresh = QPushButton("Refresh")
        self.btn_json_open = QPushButton("Open File")

        self.json_text = QPlainTextEdit()
        self.json_text.setReadOnly(True)

        jv.addWidget(QLabel("Source"), 0, 0)
        jv.addWidget(self.cb_json_source, 0, 1)
        jv.addWidget(self.btn_json_refresh, 0, 2)

        jv.addWidget(QLabel("Creature"), 1, 0)
        jv.addWidget(self.cb_json_creature, 1, 1)
        jv.addWidget(self.btn_json_open, 1, 2)

        jv.addWidget(self.json_text, 2, 0, 1, 3)

        self.tabs.addTab(self.tab_json, "JSON")

        # Log group (bottom) - small, pop-out available
        self.gb_log = QGroupBox("")
        lg = QVBoxLayout(self.gb_log)

        log_top = QHBoxLayout()
        log_top.setContentsMargins(8, 6, 8, 6)
        log_top.setSpacing(8)
        self.lb_log_title = QLabel("Log")
        self.btn_toggle_log = QToolButton()
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(True)
        self.btn_toggle_log.setAutoRaise(True)
        self._ico_log_show = self.style().standardIcon(QStyle.SP_ArrowDown)
        self._ico_log_hide = self.style().standardIcon(QStyle.SP_ArrowRight)
        self.btn_toggle_log.setIcon(self._ico_log_show)
        self.btn_toggle_log.setToolTip("Show/Hide log")
        log_top.addWidget(self.btn_toggle_log)
        log_top.addWidget(self.lb_log_title)
        log_top.addStretch(1)

        self.btn_log_find = QToolButton()
        self.btn_log_find.setAutoRaise(True)
        self.btn_log_find.setToolTip("Find in log (Ctrl+F)")
        self.btn_log_find.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))

        self.btn_log_pop = QToolButton()
        self.btn_log_pop.setAutoRaise(True)
        self.btn_log_pop.setToolTip("Pop-out log")
        self.btn_log_pop.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))

        self.btn_log_clear = QToolButton()
        self.btn_log_clear.setAutoRaise(True)
        self.btn_log_clear.setToolTip("Clear log")
        self.btn_log_clear.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))

        log_top.addWidget(self.btn_log_find)
        log_top.addWidget(self.btn_log_pop)
        log_top.addWidget(self.btn_log_clear)
        lg.addLayout(log_top)

        # Log body (collapsible; header stays visible)
        self.log_body = QWidget()
        log_body_layout = QVBoxLayout(self.log_body)
        log_body_layout.setContentsMargins(0, 0, 0, 0)
        log_body_layout.setSpacing(6)

        # Embedded find bar (hidden by default)
        self.log_find_bar = QFrame()
        fb = QHBoxLayout(self.log_find_bar)
        fb.setContentsMargins(0, 0, 0, 0)
        fb.setSpacing(6)

        self.log_find_box = QLineEdit()
        self.log_find_box.setPlaceholderText("Find…")
        self.btn_log_find_prev = QToolButton()
        self.btn_log_find_prev.setText("Prev")
        self.btn_log_find_prev.setAutoRaise(True)
        self.btn_log_find_next = QToolButton()
        self.btn_log_find_next.setText("Next")
        self.btn_log_find_next.setAutoRaise(True)
        self.btn_log_find_close = QToolButton()
        self.btn_log_find_close.setText("×")
        self.btn_log_find_close.setAutoRaise(True)

        fb.addWidget(self.log_find_box, 1)
        fb.addWidget(self.btn_log_find_prev)
        fb.addWidget(self.btn_log_find_next)
        fb.addWidget(self.btn_log_find_close)

        self.log_find_bar.setVisible(False)
        log_body_layout.addWidget(self.log_find_bar)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        log_body_layout.addWidget(self.log, 1)

        lg.addWidget(self.log_body, 1)

        # Splitter add
        self.splitter.addWidget(self.gb_view)
        self.splitter.addWidget(self.gb_log)
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 1)
        # Prevent bottom pane (log) from collapsing to 0px
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setCollapsible(1, False)
        self.gb_log.setMinimumHeight(56)
        # Give viewer most height by default
        self.splitter.setSizes([900, 140])

        def _toggle_log():
            on = self.btn_toggle_log.isChecked()
            if hasattr(self, "log_body"):
                self.log_body.setVisible(on)
            self.btn_toggle_log.setIcon(self._ico_log_show if on else self._ico_log_hide)

            # Collapse/expand: keep header always usable; no max-height clamping.
            try:
                header_h = 56
                if on:
                    self.gb_log.setMinimumHeight(110)
                    target_h = 140
                else:
                    self.gb_log.setMinimumHeight(header_h)
                    target_h = header_h

                sizes = self.splitter.sizes()
                total = max(1, sum(sizes))
                self.splitter.setSizes([max(200, total - target_h), target_h])
            except Exception:
                pass
        self.btn_toggle_log.toggled.connect(lambda _=None: _toggle_log())

        root.addWidget(self.splitter, 1)

        # -------- Signals / bindings --------
        for le in [
            self.le_scripts_dir, self.le_input_root, self.le_processed_root, self.le_anim_json_root,
            self.le_mod_assets_root, self.le_mod_json_root, self.le_hex_overlay, self.le_sheet, self.le_only_creature
        ]:
            le.textChanged.connect(self.refresh_ui_state)

        self.cb_only_group.currentIndexChanged.connect(self.refresh_ui_state)
        self.chk_split.toggled.connect(self.refresh_ui_state)
        self.chk_process.toggled.connect(self.refresh_ui_state)
        self.chk_json.toggled.connect(self.refresh_ui_state)
        self.chk_deploy.toggled.connect(self.refresh_ui_state)

        self.btn_steps_all.clicked.connect(self.steps_select_all)
        self.btn_steps_none.clicked.connect(self.steps_select_none)

        self.sp_sprite_h.valueChanged.connect(lambda _=None: self._sync_sprite_dims_ui())
        self.sp_sprite_w.valueChanged.connect(lambda _=None: self._sync_sprite_dims_ui())

        self.btn_view_refresh.clicked.connect(lambda: self.viewer_refresh_all(keep_selection=True))
        self.cb_view_source.currentIndexChanged.connect(lambda: self.viewer_refresh_all(keep_selection=True))
        self.cb_view_creature.currentIndexChanged.connect(lambda: self.viewer_refresh_groups(keep_selection=True))
        self.cb_view_group.currentIndexChanged.connect(lambda: self.viewer_refresh_frames(keep_selection=True))
        self.cb_view_frame.currentIndexChanged.connect(self.viewer_load_selected)
        self.btn_open_folder.clicked.connect(self.viewer_open_folder)
        self.btn_pick_canvas_bg.clicked.connect(self._pick_canvas_bg)
        self.le_canvas_bg.textChanged.connect(lambda _=None: self._apply_canvas_bg())
        self.btn_prev.clicked.connect(self.viewer_prev_frame)
        self.btn_next.clicked.connect(self.viewer_next_frame)
        self.btn_anim_play.clicked.connect(self.viewer_toggle_anim)
        self.cb_anim_fps.currentIndexChanged.connect(self.viewer_anim_fps_changed)
        self.chk_anim_loop.toggled.connect(self.viewer_anim_loop_changed)

        self.btn_json_refresh.clicked.connect(lambda: self.json_refresh_all(keep_selection=True))
        self.cb_json_source.currentIndexChanged.connect(lambda: self.json_refresh_all(keep_selection=True))
        self.cb_json_creature.currentIndexChanged.connect(self.json_load_selected)
        self.btn_json_open.clicked.connect(self.json_open_selected)

        self.btn_log_clear.clicked.connect(lambda: self.log.clear())
        self.btn_log_pop.clicked.connect(self.open_log_popup)
        self.btn_log_find.clicked.connect(lambda _=False: self.toggle_log_find())  # embedded find
        self.btn_log_find_next.clicked.connect(lambda: self.find_in_log(direction="next"))
        self.btn_log_find_prev.clicked.connect(lambda: self.find_in_log(direction="prev"))
        self.btn_log_find_close.clicked.connect(lambda: self.toggle_log_find(force=False))
        self.log_find_box.returnPressed.connect(lambda: self.find_in_log(direction="next"))

        # Ctrl+F focuses embedded find
        self._sc_find = QShortcut(QKeySequence.Find, self)
        self._sc_find.activated.connect(self.toggle_log_find)


    # ---------------- viewer canvas background (UI only) ----------------
    def _apply_canvas_bg(self):
        if not hasattr(self, "viewer") or self.viewer is None:
            return
        txt = (self.le_canvas_bg.text() if hasattr(self, "le_canvas_bg") else "").strip()
        if not txt:
            self.viewer.setBackgroundBrush(QBrush())
            return
        c = QColor(txt)
        if not c.isValid():
            return
        self.viewer.setBackgroundBrush(QBrush(c))

    def _pick_canvas_bg(self):
        c = QColorDialog.getColor(parent=self)
        if not c.isValid():
            return
        self.le_canvas_bg.setText(c.name().upper())
        self._apply_canvas_bg()

    # ---------------- sprite dims UI ----------------
    def _sync_sprite_dims_ui(self):
        # Make precedence explicit: when Sprite Height > 0, disable Sprite Width.
        # Set Sprite Height to 0 to enable width-based scaling.
        h = self.sp_sprite_h.value() if hasattr(self, "sp_sprite_h") else 0
        use_h = h > 0
        if hasattr(self, "sp_sprite_w"):
            self.sp_sprite_w.setEnabled(not use_h)

    # ---------------- Tooltips ----------------
    def _apply_tooltips(self):
        def tt(label: QLabel | None, widget, text: str):
            if label is not None:
                label.setToolTip(text)
            if widget is not None:
                widget.setToolTip(text)

        # ---- Top actions / global ----
        tt(None, self.btn_save, "Save settings.json (paths, defaults, UI state).")
        tt(None, self.btn_reset_paths, "Reset paths to defaults relative to scripts folder.")
        tt(None, self.btn_clear_input, "Clear ALL contents of input_root (keeps folder).")
        tt(None, self.btn_clear_outputs, "Clear processed_root + siblings (cleaned/forced/previews) + anim_json_root.")
        tt(None, self.btn_run, "Run the selected pipeline steps (queued).")
        tt(None, self.btn_stop, "Stop current running step and clear remaining queue.")

        # ---- Paths collapse ----
        if hasattr(self, "btn_toggle_paths"):
            tt(None, self.btn_toggle_paths, "Show/Hide path fields (buttons stay visible).")

        # ---- Scope ----
        tt(self.lb_scope_creature, self.le_only_creature, "Optional creature scope (creature_id folder name), e.g. goblin_darter. Empty = all creatures found.")
        tt(self.lb_scope_group, self.cb_only_group, "Optional group scope. All = all groups present in the selected creature folder.")

        # ---- Steps ----
        tt(None, self.chk_split, "Step 1: Split a spritesheet into frames (slice_sheet.py).")
        tt(None, self.chk_process, "Step 2: Process frames (chroma key removal + scale + align to 450×400).")
        tt(None, self.chk_json, "Step 3: Build <creature_id>.json animation files from processed frames.")
        tt(None, self.chk_deploy, "Step 4: Deploy PNGs + merge JSON incrementally into mod folder.")
        if hasattr(self, "btn_steps_all"):
            tt(None, self.btn_steps_all, "Select all pipeline steps.")
        if hasattr(self, "btn_steps_none"):
            tt(None, self.btn_steps_none, "Deselect all pipeline steps.")

        # ---- Split options ----
        tt(self.lb_sheet, self.le_sheet, "Input spritesheet image to split.")
        tt(None, self.btn_sheet, "Browse for spritesheet.")
        tt(self.lb_cols, self.sp_cols, "Grid columns in spritesheet.")
        tt(self.lb_rows, self.sp_rows, "Grid rows in spritesheet.")
        tt(None, self.chk_autocrop, "Auto-crop spritesheet to be divisible by rows/cols.")

        # ---- Process defaults ----
        tt(None, self.btn_toggle_params, "Show/Hide process_frames.py default parameters.")
        tt(None, self.chk_despill, "Enable despill to reduce chroma spill (magenta/green).")

        # ---- Viewer controls ----
        tt(None, self.cb_view_source, "Select viewer source root (Input/Processed/Previews/Cleaned/Forced/Deployed).")
        tt(None, self.btn_view_refresh, "Refresh viewer lists (creature/group/frame).")
        tt(None, self.cb_view_creature, "Select creature folder under current source root.")
        tt(None, self.cb_view_group, "Select animation group (groupN).")
        tt(None, self.cb_view_frame, "Select PNG frame to preview.")
        tt(None, self.btn_open_folder, "Open selected folder in file explorer.")
        tt(None, self.btn_prev, "Previous frame (A).")
        tt(None, self.btn_next, "Next frame (D).")
        tt(None, self.le_canvas_bg, "Viewer-only background color (#RRGGBB). Does NOT modify generated files.")
        tt(None, self.btn_pick_canvas_bg, "Pick viewer background color.")
        tt(None, self.btn_anim_play, "Play/Pause animation of frames in selected folder (Space).")
        tt(None, self.cb_anim_fps, "Animation speed.")
        tt(None, self.chk_anim_loop, "Loop animation when reaching the last frame.")

        # ---- JSON viewer ----
        tt(None, self.cb_json_source, "Select JSON source root (generated vs deployed).")
        tt(None, self.cb_json_creature, "Select <creature_id>.json to view.")
        tt(None, self.btn_json_refresh, "Refresh JSON file list.")
        tt(None, self.btn_json_open, "Open selected JSON in default editor.")

        # ---- Log ----
        tt(None, self.btn_toggle_log, "Collapse/expand log (header stays visible).")
        tt(None, self.btn_log_clear, "Clear embedded log.")
        tt(None, self.btn_log_pop, "Open pop-out log window.")
        tt(None, self.btn_log_find, "Toggle embedded Find bar (Ctrl+F).")
        tt(None, self.log_find_box, "Find text in embedded log.")
        tt(None, self.btn_log_find_prev, "Find previous match.")
        tt(None, self.btn_log_find_next, "Find next match.")
        tt(None, self.btn_log_find_close, "Close embedded Find bar.")

        # Helpful label tooltips
        if hasattr(self, "lb_params_title"):
            self.lb_params_title.setToolTip("Advanced parameters for process_frames.py.")
        if hasattr(self, "lb_log_title"):
            self.lb_log_title.setToolTip("Embedded log; use Pop-out for larger view.")

# ---------------- dynamic UI state ----------------
    def _wire_dynamic_ui(self):
        self.gb_split.setEnabled(self.chk_split.isChecked())
        self.chk_split.toggled.connect(self.gb_split.setEnabled)

        # hide params section if process is not selected + auto-expand when enabled
        def sync_params_enabled():
            enabled = self.chk_process.isChecked()

            # Don't hide the group anymore; just collapse/expand.
            self.gb_params_outer.setVisible(True)

            # If the step is enabled, ensure params are expanded.
            # If disabled, collapse (user can reopen manually).
            if enabled and not self.btn_toggle_params.isChecked():
                self.btn_toggle_params.setChecked(True)
            elif (not enabled) and self.btn_toggle_params.isChecked():
                self.btn_toggle_params.setChecked(False)

            self._ensure_splitter_log_visible()

        self.chk_process.toggled.connect(sync_params_enabled)
        sync_params_enabled()

    def _load_to_ui(self):
        s = self.s
        self.le_scripts_dir.setText(s.scripts_dir)
        self.le_input_root.setText(s.input_root)
        self.le_processed_root.setText(s.processed_root)
        self.le_anim_json_root.setText(s.anim_json_root)
        self.le_mod_assets_root.setText(s.mod_assets_root)
        self.le_mod_json_root.setText(s.mod_json_root)
        self.le_hex_overlay.setText(s.hex_overlay)

        self.sp_baseline_y.setValue(s.baseline_y)
        self.sp_left_limit_x.setValue(s.left_limit_x)
        self.sp_left_padding.setValue(s.left_padding)
        self.sp_sprite_h.setValue(s.sprite_h)
        self.sp_sprite_w.setValue(getattr(s, "sprite_w", 0))
        self.cb_prefer.setCurrentText(getattr(s, "prefer", "height") if getattr(s, "prefer", "height") in ["height", "width"] else "height")
        self.sp_tol.setValue(s.tol)
        self.sp_feather.setValue(s.feather)
        self.sp_shrink.setValue(s.shrink)
        self.chk_despill.setChecked(bool(s.despill))
        self.cb_key_from.setCurrentText(s.key_from if s.key_from in ["each", "first"] else "each")
        self.cb_bg_mode.setCurrentText(s.bg_mode if s.bg_mode in ["global", "border"] else "global")
        self.sp_overlay_alpha.setValue(s.overlay_alpha)
        if hasattr(self, "le_canvas_bg"):
            self.le_canvas_bg.setText(getattr(s, "viewer_canvas_bg", "#404040"))
            self._apply_canvas_bg()

        self.sp_cols.setValue(s.split_cols)
        self.sp_rows.setValue(s.split_rows)
        self.chk_autocrop.setChecked(bool(s.split_autocrop))

        self._sync_sprite_dims_ui()

    def _ui_to_settings(self):
        s = self.s
        s.scripts_dir = self.le_scripts_dir.text().strip()
        s.input_root = self.le_input_root.text().strip()
        s.processed_root = self.le_processed_root.text().strip()
        s.anim_json_root = self.le_anim_json_root.text().strip()
        s.mod_assets_root = self.le_mod_assets_root.text().strip()
        s.mod_json_root = self.le_mod_json_root.text().strip()
        s.hex_overlay = self.le_hex_overlay.text().strip()

        s.baseline_y = self.sp_baseline_y.value()
        s.left_limit_x = self.sp_left_limit_x.value()
        s.left_padding = self.sp_left_padding.value()
        s.sprite_h = self.sp_sprite_h.value()
        s.sprite_w = self.sp_sprite_w.value()
        s.prefer = self.cb_prefer.currentText()
        s.tol = self.sp_tol.value()
        s.feather = self.sp_feather.value()
        s.shrink = self.sp_shrink.value()
        s.despill = self.chk_despill.isChecked()
        s.key_from = self.cb_key_from.currentText()
        s.bg_mode = self.cb_bg_mode.currentText()
        s.overlay_alpha = self.sp_overlay_alpha.value()
        if hasattr(self, "le_canvas_bg"):
            s.viewer_canvas_bg = self.le_canvas_bg.text().strip()

        s.split_cols = self.sp_cols.value()
        s.split_rows = self.sp_rows.value()
        s.split_autocrop = self.chk_autocrop.isChecked()

    def steps_select_all(self):
        # Select all pipeline steps
        self.chk_split.setChecked(True)
        self.chk_process.setChecked(True)
        self.chk_json.setChecked(True)
        self.chk_deploy.setChecked(True)

    def steps_select_none(self):
        # Deselect all pipeline steps
        self.chk_split.setChecked(False)
        self.chk_process.setChecked(False)
        self.chk_json.setChecked(False)
        self.chk_deploy.setChecked(False)

    def refresh_ui_state(self):
        sd_ok = exists_dir(self.le_scripts_dir.text())
        in_ok = is_nonempty(self.le_input_root.text())
        proc_ok = is_nonempty(self.le_processed_root.text())
        json_ok = is_nonempty(self.le_anim_json_root.text())
        mod_assets_ok = is_nonempty(self.le_mod_assets_root.text())
        mod_json_ok = is_nonempty(self.le_mod_json_root.text())

        self.chk_split.setEnabled(sd_ok)
        self.chk_process.setEnabled(sd_ok and in_ok and proc_ok)
        self.chk_json.setEnabled(sd_ok and proc_ok and json_ok)
        self.chk_deploy.setEnabled(sd_ok and proc_ok and json_ok and mod_assets_ok and mod_json_ok)

        self.btn_run.setEnabled(any([self.chk_split.isChecked(), self.chk_process.isChecked(),
                                     self.chk_json.isChecked(), self.chk_deploy.isChecked()]))

    # ---------------- log popup + colored log ----------------
    def log_html(self) -> str:
        return self.log.toHtml()

    def open_log_popup(self):
        if self.log_dialog is None or not self.log_dialog.isVisible():
            self.log_dialog = LogDialog(self, self.log_html)
            self.log_dialog.show()
        else:
            self.log_dialog.raise_()
            self.log_dialog.activateWindow()

    # ---------------- embedded log find ----------------
    def toggle_log_find(self, force: bool | None = None):
        # force=True opens, force=False closes, None toggles
        # Note: button clicked() may pass a bool even when not checkable; treat that as 'toggle'.
        if isinstance(force, bool) and not self.btn_log_find.isCheckable():
            force = None
        if not hasattr(self, "log_find_bar"):
            # Embedded bar not present (patch mismatch) — fallback to popup so the button is never a no-op.
            self.open_log_popup()
            return
        if force is None:
            want = not self.log_find_bar.isVisible()
        else:
            want = bool(force)
        self.log_find_bar.setVisible(want)
        if want:
            self.log_find_box.setFocus()
            self.log_find_box.selectAll()

    def find_in_log(self, direction: str = "next"):
        if not hasattr(self, "log_find_box"):
            return
        needle = self.log_find_box.text().strip()
        if not needle:
            return
        flags = QTextDocument.FindFlags()
        if direction == "prev":
            flags |= QTextDocument.FindBackward
        found = self.log.find(needle, flags)
        if not found:
            # wrap-around
            cur = self.log.textCursor()
            cur.movePosition(QTextCursor.Start if direction == "next" else QTextCursor.End)
            self.log.setTextCursor(cur)
            self.log.find(needle, flags)
    def _log_ts(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def _step_from_cmd(self, cmd: list[str]) -> str:
        try:
            p = (cmd[1] if len(cmd) > 1 else cmd[0])
            base = os.path.basename(p).lower()
        except Exception:
            return ""
        if "slice_sheet" in base:
            return "split"
        if "process_frames" in base:
            return "process"
        if "build_anim_json" in base:
            return "json"
        if "deploy_assets" in base:
            return "deploy"
        return base.replace(".py", "")

    def append_log(self, text: str, level: str = "info"):
        colors = {
            "info": "#000000",
            "warn": "#ff7a00",
            "error": "#cc0000",
            "ok": "#1a8f1a",
            "cmd": "#3b5bb5",
        }
        c = colors.get(level, "#000000")
        step = getattr(self, "current_step", "ui") or "ui"
        prefix = f"[{self._log_ts()}][{step}] "
        safe = (prefix + text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log.append(f'<span style="color:{c}">{safe}</span>')
        if self.log_dialog and self.log_dialog.isVisible():
            # keep popup in sync (cheap but effective)
            self.log_dialog.refresh()

    # ---------------- actions: reset/cleanup ----------------
    def reset_paths_defaults(self):
        sd = Path(self.le_scripts_dir.text().strip() or "./scripts")
        base = sd.parent if sd.name.lower() == "scripts" else sd

        self.le_input_root.setText(str((base / "input_root").resolve()))
        self.le_processed_root.setText(str((base / "processed_root").resolve()))
        self.le_anim_json_root.setText(str((base / "anim_json").resolve()))

        self.append_log("[INFO] Paths reset to defaults relative to scripts folder.", "info")
        self.viewer_refresh_all(keep_selection=True)
        self.json_refresh_all(keep_selection=True)

    def clear_input_root(self):
        folder = Path(self.le_input_root.text().strip())
        if not folder.exists():
            self.append_log("[WARN] Input Root does not exist.", "warn")
            return
        resp = QMessageBox.question(
            self, "Confirm",
            f"Delete ALL contents inside:\n{folder}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return
        f, d = safe_clear_dir_contents(folder)
        self.append_log(f"[OK] Cleared Input Root: {f} files, {d} folders removed.", "ok")
        self.viewer_refresh_all(keep_selection=False)

    def clear_outputs(self):
        processed = Path(self.le_processed_root.text().strip())
        animjson = Path(self.le_anim_json_root.text().strip())

        targets = []
        if processed.parent.exists():
            targets += [
                processed,
                processed.parent / "cleaned_root",
                processed.parent / "forced_root",
                processed.parent / "previews",
            ]
        targets += [animjson]

        resp = QMessageBox.question(
            self, "Confirm",
            "Delete ALL contents of these folders (folders kept):\n\n" +
            "\n".join(str(t) for t in targets) +
            "\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        for t in targets:
            f, d = safe_clear_dir_contents(t)
            self.append_log(f"[OK] Cleared: {t} ({f} files, {d} folders)", "ok")

        self.viewer_refresh_all(keep_selection=False)
        self.json_refresh_all(keep_selection=False)

    # ---------------- scope ----------------
    def _scope_values(self):
        creature = self.le_only_creature.text().strip()
        group = self.cb_only_group.currentData()
        return creature, group

    # ---------------- image viewer ----------------
    def viewer_source_root(self) -> Path | None:
        src = self.cb_view_source.currentText()
        input_root = Path(self.le_input_root.text().strip()) if is_nonempty(self.le_input_root.text()) else None
        processed_root = Path(self.le_processed_root.text().strip()) if is_nonempty(self.le_processed_root.text()) else None
        mod_assets_root = Path(self.le_mod_assets_root.text().strip()) if is_nonempty(self.le_mod_assets_root.text()) else None

        if src.startswith("Input") and input_root:
            return input_root
        if src.startswith("Processed") and processed_root:
            return processed_root
        if src.startswith("Deployed") and mod_assets_root:
            return mod_assets_root

        if processed_root:
            parent = processed_root.parent
            if src.startswith("Previews"):
                return parent / "previews"
            if src.startswith("Cleaned"):
                return parent / "cleaned_root"
            if src.startswith("Forced"):
                return parent / "forced_root"
        return None

    def viewer_refresh_all(self, keep_selection: bool = True):
        prev_src = self.cb_view_source.currentIndex()
        prev_cre = self.cb_view_creature.currentData()
        prev_gid = self.cb_view_group.currentData()
        prev_frame = self.cb_view_frame.currentData()

        root = self.viewer_source_root()

        self.cb_view_creature.blockSignals(True)
        self.cb_view_group.blockSignals(True)
        self.cb_view_frame.blockSignals(True)

        self.cb_view_creature.clear()
        self.cb_view_group.clear()
        self.cb_view_frame.clear()
        self.cb_view_creature.addItem("(Select)", None)
        self.cb_view_group.addItem("(Select)", None)
        self.cb_view_frame.addItem("(Select)", None)
        self.viewer_stop_anim()
        self.viewer.set_image(None)

        if root and root.exists() and root.is_dir():
            creatures = sorted([p.name for p in root.iterdir() if p.is_dir() and CREATURE_ID_RE.match(p.name)])
            for c in creatures:
                self.cb_view_creature.addItem(c, c)

        self.cb_view_creature.blockSignals(False)
        self.cb_view_group.blockSignals(False)
        self.cb_view_frame.blockSignals(False)

        if keep_selection:
            self.cb_view_source.setCurrentIndex(prev_src)
            if prev_cre is not None:
                i = self.cb_view_creature.findData(prev_cre)
                if i != -1:
                    self.cb_view_creature.setCurrentIndex(i)
                    self.viewer_refresh_groups(keep_selection=True, prev_gid=prev_gid, prev_frame=prev_frame)
                    return

        if self.cb_view_creature.count() > 1:
            self.cb_view_creature.setCurrentIndex(1)
            self.viewer_refresh_groups(keep_selection=False)

    def viewer_refresh_groups(self, keep_selection: bool = True, prev_gid=None, prev_frame=None):
        root = self.viewer_source_root()
        creature = self.cb_view_creature.currentData()

        if keep_selection:
            if prev_gid is None:
                prev_gid = self.cb_view_group.currentData()
            if prev_frame is None:
                prev_frame = self.cb_view_frame.currentData()

        self.cb_view_group.blockSignals(True)
        self.cb_view_frame.blockSignals(True)

        self.cb_view_group.clear()
        self.cb_view_frame.clear()
        self.cb_view_group.addItem("(Select)", None)
        self.cb_view_frame.addItem("(Select)", None)
        self.viewer_stop_anim()
        self.viewer.set_image(None)

        if root and creature:
            cdir = root / creature
            if cdir.exists():
                gids = []
                for p in cdir.iterdir():
                    if p.is_dir():
                        m = re.match(r"^group(\d+)$", p.name, re.IGNORECASE)
                        if m:
                            gids.append(int(m.group(1)))
                for gid in sorted(gids):
                    self.cb_view_group.addItem(group_label(gid), gid)

        self.cb_view_group.blockSignals(False)
        self.cb_view_frame.blockSignals(False)

        if keep_selection and prev_gid is not None:
            ig = self.cb_view_group.findData(prev_gid)
            if ig != -1:
                self.cb_view_group.setCurrentIndex(ig)
                self.viewer_refresh_frames(keep_selection=True, prev_frame=prev_frame)
                return

        if self.cb_view_group.count() > 1:
            self.cb_view_group.setCurrentIndex(1)
            self.viewer_refresh_frames(keep_selection=False)

    def viewer_refresh_frames(self, keep_selection: bool = True, prev_frame=None):
        root = self.viewer_source_root()
        creature = self.cb_view_creature.currentData()
        gid = self.cb_view_group.currentData()

        if keep_selection and prev_frame is None:
            prev_frame = self.cb_view_frame.currentData()

        self.cb_view_frame.blockSignals(True)
        self.cb_view_frame.clear()
        self.cb_view_frame.addItem("(Select)", None)
        self.viewer_stop_anim()
        self.viewer.set_image(None)

        if root and creature and gid is not None:
            gdir = root / creature / f"group{gid}"
            if gdir.exists():
                frames = sorted([p.name for p in gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"])
                for f in frames:
                    self.cb_view_frame.addItem(f, f)

        self.cb_view_frame.blockSignals(False)

        if keep_selection and prev_frame is not None:
            jf = self.cb_view_frame.findData(prev_frame)
            if jf != -1:
                self.cb_view_frame.setCurrentIndex(jf)
                self.viewer_load_selected()
                return

        if self.cb_view_frame.count() > 1:
            self.cb_view_frame.setCurrentIndex(1)
            self.viewer_load_selected()

    def viewer_selected_path(self) -> Path | None:
        root = self.viewer_source_root()
        creature = self.cb_view_creature.currentData()
        gid = self.cb_view_group.currentData()
        frame = self.cb_view_frame.currentData()
        if not (root and creature and gid is not None and frame):
            return None
        return root / creature / f"group{gid}" / frame

    def viewer_load_selected(self):
        p = self.viewer_selected_path()
        if not p:
            self.viewer_stop_anim()
        self.viewer.set_image(p)

    def viewer_open_folder(self):
        root = self.viewer_source_root()
        if not root:
            return

        creature = self.cb_view_creature.currentData()
        gid = self.cb_view_group.currentData()

        # If no structured selection is available (e.g. quick split outputs),
        # open the source root itself (or creature folder if set).
        if creature and gid is not None:
            folder = root / creature / f"group{gid}"
        elif creature:
            folder = root / creature
        else:
            folder = root

        # Fallback: open the nearest existing parent
        cand = folder
        while cand and not cand.exists():
            parent = cand.parent
            if parent == cand:
                break
            cand = parent

        if cand and cand.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(cand.resolve())))
        else:
            self.append_log(f"[Viewer] Folder not found: {folder}", "warn")

    def viewer_prev_frame(self):
        idx = self.cb_view_frame.currentIndex()
        if idx > 1:
            self.cb_view_frame.setCurrentIndex(idx - 1)

    def viewer_next_frame(self):
        idx = self.cb_view_frame.currentIndex()
        if idx < self.cb_view_frame.count() - 1:
            if idx == 0 and self.cb_view_frame.count() > 1:
                self.cb_view_frame.setCurrentIndex(1)
            else:
                self.cb_view_frame.setCurrentIndex(idx + 1)

    # ---------------- viewer animation ----------------
    def _anim_frame_count(self) -> int:
        return max(0, self.cb_view_frame.count() - 1)

    def viewer_anim_fps_changed(self):
        try:
            fps = int(self.cb_anim_fps.currentData())
        except Exception:
            fps = 12
        fps = max(1, fps)
        self.anim_fps = fps
        self.anim_timer.setInterval(int(1000 / self.anim_fps))

    def viewer_anim_loop_changed(self, on: bool):
        self.anim_loop = bool(on)

    def viewer_stop_anim(self):
        if self.anim_playing:
            self.anim_timer.stop()
            self.anim_playing = False
            if hasattr(self, "btn_anim_play"):
                self.btn_anim_play.setText("Play")

    def viewer_start_anim(self):
        if self._anim_frame_count() <= 1:
            self.viewer_stop_anim()
            return
        self.anim_playing = True
        self.anim_timer.start()
        if hasattr(self, "btn_anim_play"):
            self.btn_anim_play.setText("Pause")

    def viewer_toggle_anim(self):
        if self.anim_playing:
            self.viewer_stop_anim()
        else:
            self.viewer_start_anim()

    def _anim_tick(self):
        # Advance frame selection without blocking UI.
        if self._anim_frame_count() <= 1:
            self.viewer_stop_anim()
            return
        idx = self.cb_view_frame.currentIndex()
        if idx <= 0:
            idx = 1
        nxt = idx + 1
        if nxt >= self.cb_view_frame.count():
            if self.anim_loop:
                nxt = 1
            else:
                self.viewer_stop_anim()
                return
        self.cb_view_frame.setCurrentIndex(nxt)

    def keyPressEvent(self, event):
        if self.tabs.currentWidget() == self.tab_images:
            if event.key() == Qt.Key_A:
                self.viewer_prev_frame()
                return
            if event.key() == Qt.Key_D:
                self.viewer_next_frame()
                return
            if event.key() == Qt.Key_Space:
                self.viewer_toggle_anim()
                return
        super().keyPressEvent(event)

    # ---------------- JSON viewer ----------------
    def json_source_root(self) -> Path | None:
        if self.cb_json_source.currentText().startswith("Generated"):
            p = Path(self.le_anim_json_root.text().strip())
        else:
            p = Path(self.le_mod_json_root.text().strip())
        return p if is_nonempty(str(p)) else None

    def json_refresh_all(self, keep_selection: bool = True):
        prev_src = self.cb_json_source.currentIndex()
        prev_cre = self.cb_json_creature.currentData()

        root = self.json_source_root()

        self.cb_json_creature.blockSignals(True)
        self.cb_json_creature.clear()
        self.cb_json_creature.addItem("(Select)", None)

        if root and root.exists() and root.is_dir():
            files = sorted([p for p in root.iterdir()
                            if p.is_file() and p.suffix.lower() == ".json" and CREATURE_ID_RE.match(p.stem)])
            for p in files:
                self.cb_json_creature.addItem(p.stem, p.stem)

        self.cb_json_creature.blockSignals(False)

        if keep_selection:
            self.cb_json_source.setCurrentIndex(prev_src)
            if prev_cre is not None:
                i = self.cb_json_creature.findData(prev_cre)
                if i != -1:
                    self.cb_json_creature.setCurrentIndex(i)
                    self.json_load_selected()
                    return

        if self.cb_json_creature.count() > 1:
            self.cb_json_creature.setCurrentIndex(1)
            self.json_load_selected()
        else:
            self.json_text.setPlainText("")

    def json_selected_path(self) -> Path | None:
        root = self.json_source_root()
        cre = self.cb_json_creature.currentData()
        if not (root and cre):
            return None
        p = root / f"{cre}.json"
        return p if p.exists() else None

    def json_load_selected(self):
        p = self.json_selected_path()
        if not p:
            self.json_text.setPlainText("")
            return
        try:
            self.json_text.setPlainText(p.read_text(encoding="utf-8"))
        except Exception as e:
            self.json_text.setPlainText(f"Failed to read JSON:\n{p}\n\n{e}")

    def json_open_selected(self):
        p = self.json_selected_path()
        if p and p.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.resolve())))

    # ---------------- pipeline run ----------------
    def on_save(self):
        self._ui_to_settings()
        # window geometry
        try:
            self.s.window_geometry_b64 = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.s.window_maximized = bool(self.windowState() & Qt.WindowMaximized)
        except Exception:
            pass
        self._capture_ui_state()
        save_settings(self.settings_path, self.s)
        self.append_log(f"[INFO] Saved settings -> {self.settings_path.resolve()}", "info")

    def validate(self) -> bool:
        self._ui_to_settings()

        sd = Path(self.s.scripts_dir)
        if not sd.exists():
            QMessageBox.critical(self, "Error", f"Scripts folder does not exist:\n{sd}")
            return False

        creature, group = self._scope_values()
        if creature and not CREATURE_ID_RE.match(creature):
            QMessageBox.critical(self, "Error", "Scope creature_id is invalid. Example: goblin_darter")
            return False

        if self.chk_split.isChecked():
            if not self.le_sheet.text().strip() or not exists_file(self.le_sheet.text().strip()):
                QMessageBox.critical(self, "Error", "Split is enabled but the spritesheet file is missing.")
                return False
            if (creature and group is None) or ((not creature) and (group is not None)):
                QMessageBox.critical(
                    self, "Error",
                    "Split uses Scope.\n\n"
                    "Provide BOTH Scope creature + group for structured output, OR leave BOTH empty for flat output."
                )
                return False

        if self.chk_process.isChecked():
            Path(self.s.input_root).mkdir(parents=True, exist_ok=True)
            Path(self.s.processed_root).mkdir(parents=True, exist_ok=True)
        if self.chk_json.isChecked():
            Path(self.s.anim_json_root).mkdir(parents=True, exist_ok=True)

        if self.chk_deploy.isChecked():
            if not self.s.mod_assets_root.strip() or not self.s.mod_json_root.strip():
                QMessageBox.critical(self, "Error", "Deploy requires both Mod Assets Root and Mod Json Root.")
                return False

        return True

    def build_commands(self):
        s = self.s
        cmds: list[list[str]] = []
        creature, group = self._scope_values()

        if self.chk_split.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "slice_sheet.py"),
                self.le_sheet.text().strip(),
                s.input_root,
                "--cols", str(s.split_cols),
                "--rows", str(s.split_rows),
            ]
            if s.split_autocrop:
                cmd += ["--auto_crop", "--crop_mode", "center"]
            if creature and group is not None:
                cmd += ["--creature", creature, "--group", str(group)]
            cmds.append(cmd)

        if self.chk_process.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "process_frames.py"),
                "--in_root", s.input_root,
                "--out_root", s.processed_root,
                "--clean_root", str(Path(s.processed_root).parent / "cleaned_root"),
                "--forced_root", str(Path(s.processed_root).parent / "forced_root"),
                "--preview_root", str(Path(s.processed_root).parent / "previews"),
                "--key", "auto",
                "--key_from", s.key_from,
                "--bg_mode", s.bg_mode,
                "--tol", str(s.tol),
                "--feather", str(s.feather),
                "--shrink", str(s.shrink),
                "--baseline_y", str(s.baseline_y),
                "--sprite_h", str(s.sprite_h),
                "--sprite_w", str(getattr(s, "sprite_w", 0)),
                "--prefer", str(getattr(s, "prefer", "height")),
                "--x_mode", "left_limit",
                "--left_limit_x", str(s.left_limit_x),
                "--left_padding", str(s.left_padding),
                "--overlay_alpha", str(s.overlay_alpha),
            ]
            if s.despill:
                cmd += ["--despill"]
            if s.hex_overlay.strip():
                cmd += ["--hex_overlay", s.hex_overlay.strip()]
            if creature:
                cmd += ["--only_creature", creature]
            if group is not None:
                cmd += ["--only_group", str(group)]
            cmds.append(cmd)

        if self.chk_json.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "build_anim_json.py"),
                "--input_root", s.processed_root,
                "--output_root", s.anim_json_root,
                "--basepath_prefix", "battle/",
            ]
            cmds.append(cmd)

        if self.chk_deploy.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "deploy_assets.py"),
                "--in_root", s.processed_root,
                "--out_root", s.mod_assets_root,
                "--json_in", s.anim_json_root,
                "--json_out", s.mod_json_root,
            ]
            if creature:
                cmd += ["--only_creature", creature]
            if group is not None:
                cmd += ["--only_group", str(group)]
            cmds.append(cmd)

        return cmds

    def on_run(self):
        if not self.validate():
            return

        # Confirm risky operation: splitting without scope produces unstructured output
        if self.chk_split.isChecked() and not self.le_only_creature.text().strip():
            r = QMessageBox.question(
                self,
                "Split without scope?",
                "You are about to run 'Split Spritesheet' without a creature scope.\n\nThis typically generates frames without the standard <creature_id>/groupN structure, which can be harder to browse and deploy.\n\nDo you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return

        # If log is collapsed, expand it so output is visible during RUN.
        try:
            if hasattr(self, "btn_toggle_log") and hasattr(self, "log_body") and (not self.log_body.isVisible()):
                self.btn_toggle_log.setChecked(True)
                # Give log a reasonable height
                if hasattr(self, "splitter"):
                    sizes = self.splitter.sizes()
                    total = max(1, sum(sizes))
                    log_h = min(180, max(120, total // 4))
                    self.splitter.setSizes([max(200, total - log_h), log_h])
        except Exception:
            pass

        self.on_save()
        cmds = self.build_commands()
        if not cmds:
            QMessageBox.information(self, "Nothing To Run", "No pipeline steps selected.")
            return

        self.queue = cmds
        self.append_log("=== RUN START ===", "info")
        for c in cmds:
            self.append_log("> " + quote_cmd(c), "cmd")

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._run_next()

    def _run_next(self):
        if not self.queue:
            self.append_log("=== RUN OK ===", "ok")
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.proc = None
            self.current_step = "ui"
            self.viewer_refresh_all(keep_selection=True)
            self.json_refresh_all(keep_selection=True)
            return

        cmd = self.queue.pop(0)
        self.current_step = self._step_from_cmd(cmd) or "run"
        self.append_log("[RUN] " + quote_cmd(cmd), "cmd")

        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._on_proc_output)
        self.proc.finished.connect(self._on_proc_finished)
        self.proc.start(cmd[0], cmd[1:])

        if not self.proc.waitForStarted(3000):
            self.append_log("[ERROR] Failed to start process.", "error")
            self.queue = []
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.proc = None

    def _on_proc_output(self):
        if not self.proc:
            return
        data = self.proc.readAllStandardOutput().data().decode(errors="replace")
        if not data.strip():
            return
        for line in data.splitlines():
            u = line.upper()
            if "[ERROR]" in u or "TRACEBACK" in u:
                self.append_log(line, "error")
            elif "[WARN]" in u or "WARNING" in u:
                self.append_log(line, "warn")
            elif "[OK]" in u:
                self.append_log(line, "ok")
            else:
                self.append_log(line, "info")

    def _on_proc_finished(self, exit_code, _exit_status):
        if exit_code != 0:
            self.append_log(f"[ERROR] exit_code={exit_code}. Aborting pipeline.", "error")
            self.queue = []
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.proc = None
            self.current_step = "ui"
            return

        self.append_log(f"[OK] step exit_code={exit_code}", "ok")
        self._run_next()

    def on_stop(self):
        if self.proc:
            self.append_log("[WARN] Stop requested.", "warn")
            self.proc.kill()
        self.queue = []
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.proc = None
        self.current_step = "ui"


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(_make_app_icon())
    w = PipelineRunner()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

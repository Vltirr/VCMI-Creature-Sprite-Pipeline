import json
import os
import re
import sys
import shutil
import base64
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl, QByteArray, QTimer, QSize, Signal
from PySide6.QtGui import QPixmap, QDesktopServices, QPainter, QTextCursor, QKeySequence, QShortcut, QTextDocument, QColor, QBrush, QTransform, QIcon, QPen
from PIL import Image
from PIL.ImageQt import ImageQt

from image_adjustments import apply_adjustments


def _make_preview_icon() -> QIcon:
    pm = QPixmap(18, 18)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor('#47627f'))
    pen.setWidth(2)
    p.setPen(pen)
    p.drawEllipse(3, 3, 8, 8)
    p.drawLine(10, 10, 15, 15)
    p.end()
    return QIcon(pm)


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
    QSizePolicy, QSlider,

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
    return f"{gid} - {GROUP_NAMES.get(gid, 'Unknown')}"


@dataclass
class AppSettings:
    scripts_dir: str = "./scripts"
    input_root: str = "./inputs"
    processed_root: str = "./outputs"
    anim_json_root: str = "./anim_json"
    mod_assets_root: str = ""
    mod_json_root: str = ""
    hex_overlay: str = ""
    overlay_alpha: int = 180
    # Viewer-only: background behind sprites in the GUI (does not modify files)
    viewer_canvas_bg: str = "#404040"
    viewer_zoom_scale: float = 0.0
    viewer_hscroll: int = 0
    viewer_vscroll: int = 0

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
    gen_1x: bool = True
    gen_2x: bool = False
    gen_3x: bool = False
    gen_4x: bool = False
    process_remove_bg: bool = True
    process_reframe: bool = True
    process_force_bg_output: bool = True
    process_force_bg_color: str = "#FF00FF"

    input_brightness: int = 100
    input_contrast: int = 100
    input_saturation: int = 100
    input_sharpness: int = 100
    input_gamma: int = 100
    input_highlights: int = 0
    input_shadows: int = 0

    output_brightness: int = 100
    output_contrast: int = 100
    output_saturation: int = 100
    output_sharpness: int = 100
    output_gamma: int = 100
    output_highlights: int = 0
    output_shadows: int = 0

    window_geometry_b64: str = ""
    window_maximized: bool = False

    # UI state persistence
    ui_state_version: int = 0
    ui_paths_expanded: bool = False
    ui_params_expanded: bool = False
    ui_adjustments_expanded: bool = False
    ui_log_expanded: bool = False
    ui_splitter_sizes: list[int] = None
    global_profiles: dict = field(default_factory=dict)

    # Viewer-only: background behind sprites in the GUI (does not modify files)


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        s = AppSettings()
        if all(k in data for k in ["paths", "ui_state", "global_profiles", "current_values"]):
            for k, v in data.get("paths", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            for k, v in data.get("ui_state", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            current_values = data.get("current_values", {})
            for k, v in current_values.get("process_frames", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            for k, v in current_values.get("image_adjustments", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            s.global_profiles = data.get("global_profiles", {})
        else:
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            s.global_profiles = {
                "process_frames": _settings_process_profile_dict(s),
                "image_adjustments": _settings_adjust_profile_dict(s),
            }
        return s
    except Exception:
        return AppSettings()


def save_settings(path: Path, settings: AppSettings):
    data = {
        "paths": {
            "scripts_dir": settings.scripts_dir,
            "input_root": settings.input_root,
            "processed_root": settings.processed_root,
            "anim_json_root": settings.anim_json_root,
            "mod_assets_root": settings.mod_assets_root,
            "mod_json_root": settings.mod_json_root,
            "hex_overlay": settings.hex_overlay,
        },
        "ui_state": {
            "viewer_canvas_bg": settings.viewer_canvas_bg,
            "viewer_zoom_scale": settings.viewer_zoom_scale,
            "viewer_hscroll": settings.viewer_hscroll,
            "viewer_vscroll": settings.viewer_vscroll,
            "overlay_alpha": settings.overlay_alpha,
            "split_cols": settings.split_cols,
            "split_rows": settings.split_rows,
            "split_autocrop": settings.split_autocrop,
            "window_geometry_b64": settings.window_geometry_b64,
            "window_maximized": settings.window_maximized,
            "ui_state_version": settings.ui_state_version,
            "ui_paths_expanded": settings.ui_paths_expanded,
            "ui_params_expanded": settings.ui_params_expanded,
            "ui_adjustments_expanded": settings.ui_adjustments_expanded,
            "ui_log_expanded": settings.ui_log_expanded,
            "ui_splitter_sizes": settings.ui_splitter_sizes,
        },
        "global_profiles": settings.global_profiles or {
            "process_frames": _settings_process_profile_dict(settings),
            "image_adjustments": _settings_adjust_profile_dict(settings),
        },
        "current_values": {
            "process_frames": _settings_process_profile_dict(settings),
            "image_adjustments": _settings_adjust_profile_dict(settings),
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


def _settings_process_profile_dict(settings: AppSettings) -> dict:
    return {
        "process_remove_bg": settings.process_remove_bg,
        "process_reframe": settings.process_reframe,
        "process_force_bg_output": settings.process_force_bg_output,
        "process_force_bg_color": settings.process_force_bg_color,
        "gen_1x": settings.gen_1x,
        "gen_2x": settings.gen_2x,
        "gen_3x": settings.gen_3x,
        "gen_4x": settings.gen_4x,
        "baseline_y": settings.baseline_y,
        "left_limit_x": settings.left_limit_x,
        "left_padding": settings.left_padding,
        "sprite_h": settings.sprite_h,
        "sprite_w": settings.sprite_w,
        "prefer": settings.prefer,
        "tol": settings.tol,
        "feather": settings.feather,
        "shrink": settings.shrink,
        "despill": settings.despill,
        "key_from": settings.key_from,
        "bg_mode": settings.bg_mode,
    }


def _settings_adjust_profile_dict(settings: AppSettings) -> dict:
    return {
        "input_brightness": settings.input_brightness,
        "input_contrast": settings.input_contrast,
        "input_saturation": settings.input_saturation,
        "input_sharpness": settings.input_sharpness,
        "input_gamma": settings.input_gamma,
        "input_highlights": settings.input_highlights,
        "input_shadows": settings.input_shadows,
        "output_brightness": settings.output_brightness,
        "output_contrast": settings.output_contrast,
        "output_saturation": settings.output_saturation,
        "output_sharpness": settings.output_sharpness,
        "output_gamma": settings.output_gamma,
        "output_highlights": settings.output_highlights,
        "output_shadows": settings.output_shadows,
    }


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

    def set_pixmap(self, pm: QPixmap, preserve_view: bool = False):
        had_previous = not self._pixmap_item.pixmap().isNull()
        old_transform = self.transform()
        old_h = self.horizontalScrollBar().value()
        old_v = self.verticalScrollBar().value()
        self._pixmap_item.setPixmap(pm)
        self._scene.setSceneRect(pm.rect())
        if preserve_view and had_previous:
            self.setTransform(old_transform)
            self.horizontalScrollBar().setValue(old_h)
            self.verticalScrollBar().setValue(old_v)
        else:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def clear_image(self):
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0, 0, 1, 1)

    def set_image(self, path: Path | None):
        if not path or not path.exists():
            self.clear_image()
            return
        pm = QPixmap(str(path))
        self.set_pixmap(pm, preserve_view=False)

    def wheelEvent(self, event):
        factor = 1.20 if event.angleDelta().y() > 0 else 1 / 1.20
        self.scale(factor, factor)

    def fit_to_view(self):
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_zoom_100(self):
        if self._pixmap_item.pixmap().isNull():
            return
        self.setTransform(QTransform())
        self.centerOn(self._scene.sceneRect().center())


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        track_color = QColor('#4f93e6') if self._checked else QColor('#d8e1eb')
        border_color = QColor('#3e7fcd') if self._checked else QColor('#a8b8cb')
        p.setPen(QPen(border_color, 1))
        p.setBrush(track_color)
        p.drawRoundedRect(rect, 12, 12)

        knob_d = 18
        knob_y = (self.height() - knob_d) // 2
        knob_x = self.width() - knob_d - 3 if self._checked else 3
        p.setPen(QPen(QColor('#cfd9e4'), 1))
        p.setBrush(QColor('white'))
        p.drawEllipse(knob_x, knob_y, knob_d, knob_d)
        p.end()



class PreviewWindow(QDialog):
    ADJUST_FIELDS = [
        ("brightness", "Brightness", -100, 100, 0),
        ("contrast", "Contrast", -100, 100, 0),
        ("saturation", "Saturation", -100, 100, 0),
        ("sharpness", "Sharpness", -100, 100, 0),
        ("gamma", "Gamma", -100, 100, 0),
        ("highlights", "Highlights", -100, 100, 0),
        ("shadows", "Shadows", -100, 100, 0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                self.resize(max(1200, int(geo.width() * 0.9)), max(800, int(geo.height() * 0.9)))
            else:
                self.resize(1600, 980)
        except Exception:
            self.resize(1600, 980)
        self.setModal(False)

        self.original_pm: QPixmap | None = None
        self.preview_pm: QPixmap | None = None
        self.show_original = False
        self.edit_stage: str | None = "input"
        self.preview_compare_mode = False
        self._fit_on_next_refresh = True

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.lb_editing = QLabel("Editing: Input stage")
        self.lb_editing.setStyleSheet("font-weight: 600; color: #223;")
        self.btn_edit_input = QPushButton("Edit Input")
        self.btn_edit_output = QPushButton("Edit Output")
        self.btn_hold_original = QPushButton("Hold Original")
        self.btn_hold_original.setToolTip("Hold the mouse button down to temporarily show the original frame.")
        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setToolTip("Fit the image to the preview window.")
        self.btn_zoom_100 = QPushButton("100%")
        self.btn_zoom_100.setToolTip("Show the image at 100% zoom.")
        top.addWidget(self.lb_editing)
        top.addSpacing(12)
        top.addWidget(self.btn_edit_input)
        top.addWidget(self.btn_edit_output)
        top.addStretch(1)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.btn_reset.setToolTip("Reset the preview editor sliders to neutral values.")
        self.btn_apply_input = QPushButton("Apply to Input")
        self.btn_apply_input.setToolTip("Copy the current preview slider values into the Input stage settings.")
        self.btn_apply_output = QPushButton("Apply to Output")
        self.btn_apply_output.setToolTip("Copy the current preview slider values into the Output stage settings.")
        top.addWidget(self.btn_hold_original)
        top.addWidget(self.btn_fit)
        top.addWidget(self.btn_zoom_100)
        top.addSpacing(10)
        top.addWidget(self.btn_reset)
        top.addWidget(self.btn_apply_input)
        top.addWidget(self.btn_apply_output)
        root.addLayout(top)

        body = QSplitter(Qt.Horizontal)
        body.setChildrenCollapsible(False)
        root.addWidget(body, 1)

        controls_wrap = QWidget()
        controls_wrap.setMinimumWidth(350)
        controls_wrap.setMaximumWidth(470)
        controls_wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        controls_layout = QVBoxLayout(controls_wrap)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)

        self.controls_scroll = QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QFrame.NoFrame)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.controls_scroll.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.controls_scroll.setMinimumWidth(350)
        self.controls_scroll.setMaximumWidth(470)

        controls_body = QWidget()
        controls_body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        controls_grid = QGridLayout(controls_body)
        controls_grid.setContentsMargins(0, 0, 0, 0)
        controls_grid.setHorizontalSpacing(8)
        controls_grid.setVerticalSpacing(4)

        for row, (name, label_text, minimum, maximum, value) in enumerate(self.ADJUST_FIELDS):
            label = QLabel(label_text)
            label.setToolTip(f"{label_text} adjustment for the live preview editor.")
            control = self._make_adjust_slider(minimum, maximum, value)
            setattr(self, f"sp_{name}", control)
            controls_grid.addWidget(label, row, 0, alignment=Qt.AlignTop)
            controls_grid.addWidget(control, row, 1)

        self.controls_scroll.setWidget(controls_body)
        controls_layout.addWidget(self.controls_scroll, 1)

        body.addWidget(controls_wrap)

        preview_wrap = QWidget()
        preview_layout = QVBoxLayout(preview_wrap)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)

        self.preview_splitter = QSplitter(Qt.Horizontal)
        self.preview_splitter.setChildrenCollapsible(False)

        self.original_panel = QWidget()
        original_layout = QVBoxLayout(self.original_panel)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(4)
        self.lb_original = QLabel("Original")
        self.lb_original.setAlignment(Qt.AlignCenter)
        self.lb_original.setStyleSheet("font-weight: 700; font-size: 13px; color: #173f6b; background: #e6f0fa; border: 1px solid #a8c1de; border-radius: 4px; padding: 4px 8px;")
        self.original_view = ImageView()
        original_layout.addWidget(self.lb_original)
        original_layout.addWidget(self.original_view, 1)

        self.adjusted_panel = QWidget()
        adjusted_layout = QVBoxLayout(self.adjusted_panel)
        adjusted_layout.setContentsMargins(0, 0, 0, 0)
        adjusted_layout.setSpacing(4)
        self.lb_adjusted = QLabel("Adjusted")
        self.lb_adjusted.setAlignment(Qt.AlignCenter)
        self.lb_adjusted.setStyleSheet("font-weight: 700; font-size: 13px; color: #173f6b; background: #e6f0fa; border: 1px solid #a8c1de; border-radius: 4px; padding: 4px 8px;")
        self.preview_view = ImageView()
        adjusted_layout.addWidget(self.lb_adjusted)
        adjusted_layout.addWidget(self.preview_view, 1)

        self.preview_splitter.addWidget(self.original_panel)
        self.preview_splitter.addWidget(self.adjusted_panel)
        self.preview_splitter.setSizes([1, 1])

        preview_layout.addWidget(self.preview_splitter, 1)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        self.lb_status = QLabel("No frame selected")
        self.lb_status.setStyleSheet("color: #355; font-style: italic;")
        status_row.addWidget(self.lb_status, 1)
        self.mode_toggle_wrap = QWidget()
        mode_layout = QHBoxLayout(self.mode_toggle_wrap)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(8)
        self.lb_mode_single = QLabel("Single")
        self.lb_mode_single.setStyleSheet("color: #4d627a;")
        self.chk_compare_mode = ToggleSwitch(False)
        self.chk_compare_mode.setChecked(False)
        self.chk_compare_mode.setToolTip("Toggle between single-image preview and side-by-side comparison.")
        self.lb_mode_compare = QLabel("Compare")
        self.lb_mode_compare.setStyleSheet("color: #4d627a;")
        mode_layout.addWidget(self.lb_mode_single)
        mode_layout.addWidget(self.chk_compare_mode)
        mode_layout.addWidget(self.lb_mode_compare)
        status_row.addWidget(self.mode_toggle_wrap, 0, Qt.AlignRight)
        preview_layout.addLayout(status_row)
        body.addWidget(preview_wrap)
        body.setSizes([400, 1200])

        self.btn_hold_original.pressed.connect(self._show_original_pressed)
        self.btn_hold_original.released.connect(self._show_original_released)
        self.chk_compare_mode.toggled.connect(self._set_preview_compare_mode)
        self.btn_fit.clicked.connect(self._fit_preview_views)
        self.btn_zoom_100.clicked.connect(self._set_preview_zoom_100)
        self.btn_reset.clicked.connect(self.reset_values)

        for name, *_ in self.ADJUST_FIELDS:
            getattr(self, f"sp_{name}").slider.valueChanged.connect(self._notify_values_changed)

        self._set_preview_compare_mode(False)
        self._update_stage_action_styles()

    def _make_adjust_slider(self, minimum, maximum, value, suffix=""):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setSingleStep(1)
        slider.setPageStep(10)
        slider.setFixedWidth(280)
        slider.setStyleSheet(
            "QSlider { min-height: 18px; max-height: 18px; }"
            "QSlider::groove:horizontal { height: 5px; background: #d8e4f2; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: #4f93e6; border-radius: 3px; }"
            "QSlider::add-page:horizontal { background: #e7eef8; border-radius: 3px; }"
            "QSlider::handle:horizontal { background: white; border: 1px solid #7ea5cf; width: 14px; margin: -5px 0; border-radius: 7px; }"
            "QSlider::handle:horizontal:hover { background: #f7fbff; border: 1px solid #4A90E2; }"
        )

        value_label = QLabel(f"{value}{suffix}")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setMinimumWidth(38)

        scale_values = [
            minimum,
            minimum + ((maximum - minimum) // 4),
            0,
            minimum + (((maximum - minimum) * 3) // 4),
            maximum,
        ]
        scale_labels = [QLabel(str(v)) for v in scale_values]
        for lbl in scale_labels:
            lbl.setStyleSheet("color: #6a7f98; font-size: 9px;")
        scale_labels[0].setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        scale_labels[-1].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for lbl in scale_labels[1:-1]:
            lbl.setAlignment(Qt.AlignCenter)

        def sync_label(v: int):
            value_label.setText(f"{v}{suffix}")

        slider.valueChanged.connect(sync_label)

        wrapper = QWidget()
        wrapper.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        outer_layout = QVBoxLayout(wrapper)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(1)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addWidget(slider, 0)
        top_row.addWidget(value_label, 0)
        top_row.addStretch(1)
        outer_layout.addLayout(top_row)

        tick_row = QHBoxLayout()
        tick_row.setContentsMargins(8, 0, 42, 0)
        tick_row.setSpacing(0)
        tick_row.addStretch(1)
        for idx in range(5):
            tick = QFrame()
            tick.setFixedSize(1, 6 if idx == 2 else 4)
            tick.setStyleSheet("background: #88a8cc;")
            tick_row.addWidget(tick, 0, Qt.AlignHCenter | Qt.AlignTop)
            if idx < 4:
                tick_row.addStretch(1)
        outer_layout.addLayout(tick_row)

        scale_row = QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 38, 0)
        scale_row.setSpacing(0)
        for idx, lbl in enumerate(scale_labels):
            scale_row.addWidget(lbl)
            if idx < len(scale_labels) - 1:
                scale_row.addStretch(1)
        outer_layout.addLayout(scale_row)

        wrapper.slider = slider
        wrapper.value_label = value_label
        return wrapper

    def _notify_values_changed(self, *_):
        parent = self.parent()
        if parent is not None and hasattr(parent, "_schedule_viewer_preview"):
            parent._schedule_viewer_preview(self.edit_stage)

    def _show_original_pressed(self):
        self.show_original = True
        self.refresh_display()

    def _show_original_released(self):
        self.show_original = False
        self.refresh_display()

    def _fit_preview_views(self):
        self.original_view.fit_to_view()
        self.preview_view.fit_to_view()

    def _set_preview_zoom_100(self):
        self.original_view.set_zoom_100()
        self.preview_view.set_zoom_100()

    def _set_preview_compare_mode(self, compare: bool):
        self.preview_compare_mode = bool(compare)
        if hasattr(self, "chk_compare_mode") and self.chk_compare_mode.isChecked() != self.preview_compare_mode:
            self.chk_compare_mode.setChecked(self.preview_compare_mode)
        self.lb_mode_single.setStyleSheet("color: #173f6b; font-weight: 600;" if not self.preview_compare_mode else "color: #4d627a;")
        self.lb_mode_compare.setStyleSheet("color: #173f6b; font-weight: 600;" if self.preview_compare_mode else "color: #4d627a;")
        self.original_panel.setVisible(self.preview_compare_mode)
        if self.preview_compare_mode:
            self.preview_splitter.setSizes([1, 1])
        self.refresh_display()

    def reset_values(self):
        for name, *_ in self.ADJUST_FIELDS:
            getattr(self, f"sp_{name}").slider.setValue(0)

    def set_status(self, text: str):
        self.lb_status.setText(text)

    def set_edit_stage(self, stage: str | None):
        self.edit_stage = stage
        if stage is None:
            self.lb_editing.setText("Editing: Preview")
        else:
            self.lb_editing.setText(f"Editing: {stage.title()} stage")
        self._update_stage_action_styles()

    def _update_stage_action_styles(self):
        active = (
            "QPushButton { background-color: #1f6fd1; color: white; border: 1px solid #1758a8; border-radius: 6px; }"
            "QPushButton:hover { background-color: #2d7de0; }"
        )
        neutral = ""
        self.btn_edit_input.setStyleSheet(active if self.edit_stage == "input" else neutral)
        self.btn_edit_output.setStyleSheet(active if self.edit_stage == "output" else neutral)
        self.btn_apply_input.setStyleSheet(active if self.edit_stage == "input" else neutral)
        self.btn_apply_output.setStyleSheet(active if self.edit_stage == "output" else neutral)

    def set_stage_values(self, stage: str | None, values: dict[str, int]):
        self.set_edit_stage(stage)
        for name, *_ in self.ADJUST_FIELDS:
            stored = values.get(name, 100 if name in {"brightness", "contrast", "saturation", "sharpness", "gamma"} else 0)
            slider_value = stored - 100 if name in {"brightness", "contrast", "saturation", "sharpness", "gamma"} else stored
            getattr(self, f"sp_{name}").slider.setValue(slider_value)

    def current_values(self) -> dict[str, int]:
        values = {}
        for name, *_ in self.ADJUST_FIELDS:
            raw = getattr(self, f"sp_{name}").slider.value()
            values[name] = raw + 100 if name in {"brightness", "contrast", "saturation", "sharpness", "gamma"} else raw
        return values

    def set_pixmaps(self, original: QPixmap | None, preview: QPixmap | None):
        self.original_pm = original
        self.preview_pm = preview
        self.refresh_display()

    def refresh_display(self):
        original_pm = self.original_pm
        adjusted_pm = self.original_pm if self.show_original else (self.preview_pm or self.original_pm)
        preserve = not self._fit_on_next_refresh

        if original_pm is None or original_pm.isNull():
            self.original_view.clear_image()
            self.preview_view.clear_image()
            return

        if self.preview_compare_mode:
            self.original_view.set_pixmap(original_pm, preserve_view=preserve)
            self.preview_view.set_pixmap(adjusted_pm, preserve_view=preserve)
        else:
            self.preview_view.set_pixmap(adjusted_pm, preserve_view=preserve)
        self._fit_on_next_refresh = False

    def closeEvent(self, event):
        parent = self.parent()
        if parent is not None and hasattr(parent, "_schedule_viewer_preview"):
            parent._schedule_viewer_preview()
        super().closeEvent(event)


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
        self.find_box.setPlaceholderText("Find...")
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
        if not self.s.global_profiles:
            self.s.global_profiles = {
                "process_frames": _settings_process_profile_dict(self.s),
                "image_adjustments": _settings_adjust_profile_dict(self.s),
            }

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

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(90)
        self.preview_timer.timeout.connect(self._apply_viewer_preview)
        self.preview_stage_preference = "input"
        self.preview_source_path: Path | None = None
        self.preview_source_image: Image.Image | None = None
        self.preview_window: PreviewWindow | None = None
        self._pending_viewer_state_restore = bool(getattr(self.s, "viewer_zoom_scale", 0.0) and getattr(self.s, "viewer_zoom_scale", 0.0) > 0)
        self._pending_viewer_refresh_state: tuple[QTransform, int, int] | None = None
        self._build_ui()
        self._apply_tooltips()
        self._load_to_ui()
        # Expand Paths if key fields are missing (first run)
        if not self.le_scripts_dir.text().strip():
            self.btn_toggle_paths.setChecked(True)
        self._wire_dynamic_ui()
        self._bind_adjustment_preview()
        self._update_preview_status()
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
                shared_open = bool(getattr(self.s, "ui_params_expanded", False))
                self.btn_toggle_params.setChecked(shared_open)
                if hasattr(self, "btn_toggle_adjustments"):
                    self.btn_toggle_adjustments.setChecked(shared_open)

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
            if hasattr(self, "btn_toggle_adjustments"):
                self.s.ui_adjustments_expanded = bool(self.btn_toggle_params.isChecked())
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
            self._ui_to_settings()
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
        root.setAlignment(Qt.AlignTop)

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
            "Inputs": "Working input folder. Expected structure: inputs/<creature_id>/groupN/*.png",
            "Outputs": "Base processed outputs folder. Multi-resolution outputs are stored as outputs/<scale>x/<creature_id>/groupN/*.png. The viewer, JSON build, deploy, and output adjustments currently use 1x.",
            "Anim Json Root (Generated)": "Where generated <creature_id>.json files are written.",
            "Mod Assets Root (Deploy PNGs)": "Destination root in your mod for battle PNGs (deploy target).",
            "Mod Json Root (Deploy Json)": "Destination root in your mod for <creature_id>.json files (deploy target).",
            "Hex Overlay (Optional PNG)": "Optional 450x400 PNG overlay (hex guide) used by previews in process_frames.py.",
            "Force Background Color": "Solid color used for the forced background helper output.",
        }

        params_tt = {
            "Baseline Y": "Vertical baseline used to place the sprite on the 450x400 canvas.",
            "Left Limit X": "X reference line when x_mode=left_limit (aligns sprite to left of hex).",
            "Left Padding": "Extra padding relative to Left Limit X.",
            "Sprite Height": "Target sprite height in pixels. Used when Dimension Preference=height. You can also set both height and width and use Preference=none to allow slight distortion.",
            "Sprite Width": "Target sprite width in pixels. Used when Dimension Preference=width. With Preference=none and both dimensions set, the sprite is resized to (width,height) even if it distorts.",
            "Dimension Preference": "Controls scaling. height = use Sprite Height and ignore width (keep aspect). width = use Sprite Width and ignore height (keep aspect). none = if both are set, resize to (width,height) even if it distorts.",
            "Tolerance": "Chroma-key tolerance (0-255). Higher = removes more colors similar to the key (more aggressive background removal), but may start eating into the sprite. Lower = safer for the sprite, but may leave more background/halo.",
            "Feather": "Edge feather/softening (0-255). Higher = smoother, softer alpha edge (reduces jaggies) but can look blurry or expand semi-transparent halo; lower = crisper edge but can look rough. Most noticeable with bg_mode=border.",
            "Shrink": "Alpha erosion (0=off). Helps reduce halos but can eat thin details.",
            "Key From": "Background key sampling: each frame or first frame of group.",
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

        self.path_open_buttons = {}

        def add_path_row(row, label_text, le: QLineEdit, is_dir=True):
            lab = QLabel(label_text)
            tip = paths_tt.get(label_text, "")
            if tip:
                lab.setToolTip(tip)
                le.setToolTip(tip)
            pg.addWidget(lab, row, 0)
            pg.addWidget(le, row, 1)
            btn = QPushButton("Browse...")
            btn_open = QToolButton()
            btn_open.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
            btn_open.setAutoRaise(True)
            if tip:
                btn.setToolTip(tip)
                btn_open.setToolTip(f"Open the current {label_text} folder.")
            pg.addWidget(btn, row, 2)
            pg.addWidget(btn_open, row, 3)

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

            def open_current():
                value = le.text().strip()
                if not value:
                    return
                target = Path(value)
                if not is_dir:
                    target = target.parent
                self._open_folder_path(target)

            btn.clicked.connect(browse)
            btn_open.clicked.connect(open_current)
            self.path_open_buttons[label_text] = btn_open
            return lab, le

        self.lb_scripts_dir, _ = add_path_row(0, "Scripts Folder", self.le_scripts_dir, True)
        self.lb_input_root, _ = add_path_row(1, "Inputs", self.le_input_root, True)
        self.lb_processed_root, _ = add_path_row(2, "Outputs", self.le_processed_root, True)
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
        self.lb_scope_hint = QLabel("Scope filters existing content. For Split, it also defines the destination creature/group.")
        self.lb_scope_hint.setWordWrap(True)
        self.lb_scope_hint.setStyleSheet("color: #4b5e77; font-size: 11px;")

        self.le_only_creature = QComboBox()
        self.le_only_creature.setEditable(True)
        self.le_only_creature.setInsertPolicy(QComboBox.NoInsert)
        self.le_only_creature.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)
        self.le_only_creature.lineEdit().setPlaceholderText("e.g. goblin_darter (empty = all)")
        self.btn_scope_refresh = QToolButton()
        self.btn_scope_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.btn_scope_refresh.setAutoRaise(True)
        self.btn_use_viewer_scope = QPushButton("Use Viewer Selection")
        self.btn_use_viewer_scope.setMinimumWidth(0)
        self.btn_scope_save_profile = QPushButton("Save Profile")
        self.btn_scope_save_profile.setMinimumWidth(0)

        self.cb_only_group = QComboBox()
        self.cb_only_group.addItem("All", None)
        for g in VALID_GROUPS:
            self.cb_only_group.addItem(group_label(g), g)

        scope_creature_row = QWidget()
        scope_creature_layout = QHBoxLayout(scope_creature_row)
        scope_creature_layout.setContentsMargins(0, 0, 0, 0)
        scope_creature_layout.setSpacing(6)
        scope_creature_layout.addWidget(self.le_only_creature, 1)
        scope_creature_layout.addWidget(self.btn_scope_refresh)
        scope_creature_layout.addWidget(self.btn_use_viewer_scope)
        scope_group_row = QWidget()
        scope_group_layout = QHBoxLayout(scope_group_row)
        scope_group_layout.setContentsMargins(0, 0, 0, 0)
        scope_group_layout.setSpacing(6)
        scope_group_layout.addWidget(self.cb_only_group, 1)
        scope_group_layout.addWidget(self.btn_scope_save_profile, 0)

        sg.addWidget(self.lb_scope_creature, 0, 0)
        sg.addWidget(scope_creature_row, 0, 1)
        sg.addWidget(self.lb_scope_group, 1, 0)
        sg.addWidget(scope_group_row, 1, 1)
        sg.addWidget(self.lb_scope_hint, 2, 0, 1, 2)

        row2.addWidget(self.gb_scope, 1)

        self.gb_steps = QGroupBox("Pipeline Steps")
        st = QVBoxLayout(self.gb_steps)
        st.setSpacing(4)

        self.chk_split = QCheckBox("Split Spritesheet")
        self.chk_adjust_input = QCheckBox("Adjust Input")
        self.chk_process = QCheckBox("Process Frames")
        self.chk_adjust_output = QCheckBox("Adjust Output")
        self.chk_json = QCheckBox("Build Json")
        self.chk_deploy = QCheckBox("Deploy")

        # Default: no steps selected
        self.chk_split.setChecked(False)
        self.chk_adjust_input.setChecked(False)
        self.chk_process.setChecked(False)
        self.chk_adjust_output.setChecked(False)
        self.chk_json.setChecked(False)
        self.chk_deploy.setChecked(False)


        st.addWidget(self.chk_split)
        st.addWidget(self.chk_adjust_input)
        st.addWidget(self.chk_process)
        st.addWidget(self.chk_adjust_output)
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

        self.btn_sheet = QPushButton("Browse...")
        self.btn_sheet_open = QToolButton()
        self.btn_sheet_open.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_sheet_open.setAutoRaise(True)
        self.sp_cols = QSpinBox(); self.sp_cols.setRange(1, 200)
        self.sp_rows = QSpinBox(); self.sp_rows.setRange(1, 200)
        self.chk_autocrop = QCheckBox("Auto Crop")

        so.addWidget(self.lb_sheet, 0, 0)
        so.addWidget(self.le_sheet, 0, 1)
        so.addWidget(self.btn_sheet, 0, 2)
        so.addWidget(self.btn_sheet_open, 0, 3)
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
        self.btn_sheet_open.clicked.connect(
            lambda: self._open_folder_path(
                Path(self.le_sheet.text().strip()).parent if self.le_sheet.text().strip() else Path.cwd()
            )
        )

        row2.addWidget(self.gb_split, 2)

        # -------- Run/Stop (primary actions) --------
        self.gb_run = QGroupBox("")
        rr = QVBoxLayout(self.gb_run)
        rr.setContentsMargins(8, 8, 8, 8)
        rr.setSpacing(8)
        self.gb_run.setFixedWidth(132)

        # Make RUN visually primary
        self.btn_run.setText("Run")
        self.btn_run.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
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

        self.btn_stop.setText("Stop")
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
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
        self.gb_params_outer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        outer = QVBoxLayout(self.gb_params_outer)
        outer.setContentsMargins(9, 6, 9, 9)
        outer.setSpacing(6)
        outer.setAlignment(Qt.AlignTop)

        params_header = QHBoxLayout()
        params_header.setContentsMargins(0, 0, 0, 0)
        params_header.setSpacing(6)
        self.lb_params_title = QLabel("Process Frames Options")
        self.lb_params_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        self.params_profile_bar = QWidget()
        params_profile_layout = QHBoxLayout(self.params_profile_bar)
        params_profile_layout.setContentsMargins(0, 0, 0, 0)
        params_profile_layout.setSpacing(4)
        self.btn_params_load_global = QToolButton(); self.btn_params_load_global.setText("Load Global")
        self.btn_params_load_creature = QToolButton(); self.btn_params_load_creature.setText("Load Creature")
        self.btn_params_load_group = QToolButton(); self.btn_params_load_group.setText("Load Group")
        self.btn_params_save_global = QToolButton(); self.btn_params_save_global.setText("Save Global")
        self.btn_params_save_creature = QToolButton(); self.btn_params_save_creature.setText("Save Creature")
        self.btn_params_save_group = QToolButton(); self.btn_params_save_group.setText("Save Group")
        for btn in [
            self.btn_params_load_global, self.btn_params_load_creature, self.btn_params_load_group,
            self.btn_params_save_global, self.btn_params_save_creature, self.btn_params_save_group,
        ]:
            btn.setAutoRaise(True)
            params_profile_layout.addWidget(btn)
        params_header.addSpacing(22)
        params_header.addWidget(self.params_profile_bar)
        params_header.addStretch(1)
        outer.addLayout(params_header)

        self.params_fill = QWidget()
        self.params_fill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        fill_layout = QVBoxLayout(self.params_fill)
        fill_layout.setContentsMargins(0, 0, 0, 0)
        fill_layout.setSpacing(0)

        self.params_body = QWidget()
        self.params_body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        pr = QGridLayout(self.params_body)
        pr.setHorizontalSpacing(12)
        pr.setVerticalSpacing(6)
        for col in range(8):
            pr.setColumnStretch(col, 0 if col % 2 == 0 else 1)

        def add_param_at(row, col, label_text, widget, *, min_width=110):
            lab = QLabel(label_text)
            lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lab.setMinimumWidth(min_width)
            tip = params_tt.get(label_text, "")
            if tip:
                lab.setToolTip(tip)
                widget.setToolTip(tip)
            pr.addWidget(lab, row, col, alignment=Qt.AlignLeft)
            pr.addWidget(widget, row, col + 1, alignment=Qt.AlignLeft)
            widget.setMinimumWidth(110)
            return lab, widget

        self.sp_baseline_y = QSpinBox(); self.sp_baseline_y.setRange(0, 10000)
        self.sp_left_limit_x = QSpinBox(); self.sp_left_limit_x.setRange(0, 10000)
        self.sp_left_padding = QSpinBox(); self.sp_left_padding.setRange(-999, 999)
        self.sp_sprite_h = QSpinBox(); self.sp_sprite_h.setRange(0, 10000)
        self.sp_sprite_w = QSpinBox(); self.sp_sprite_w.setRange(0, 10000)
        self.cb_prefer = QComboBox(); self.cb_prefer.addItems(["height", "width", "none"])

        self.sp_tol = QSpinBox(); self.sp_tol.setRange(0, 255)
        self.sp_feather = QSpinBox(); self.sp_feather.setRange(0, 255)
        self.sp_shrink = QSpinBox(); self.sp_shrink.setRange(0, 10)

        self.chk_remove_bg = QCheckBox("Remove Background")
        self.chk_remove_bg.setChecked(True)
        self.chk_reframe = QCheckBox("Reframe")
        self.chk_reframe.setChecked(True)
        self.chk_force_bg_output = QCheckBox("Force Background")
        self.chk_force_bg_output.setChecked(True)

        self.chk_despill = QCheckBox("Despill")
        self.cb_key_from = QComboBox(); self.cb_key_from.addItems(["each", "first"])
        self.cb_bg_mode = QComboBox(); self.cb_bg_mode.addItems(["global", "border"])

        self.chk_res_1x = QCheckBox("1x")
        self.chk_res_2x = QCheckBox("2x")
        self.chk_res_3x = QCheckBox("3x")
        self.chk_res_4x = QCheckBox("4x")
        self.chk_res_1x.setChecked(True)

        self.le_force_bg_color = QLineEdit()
        self.le_force_bg_color.setPlaceholderText("#FF00FF")
        self.le_force_bg_color.setFixedWidth(92)
        self.btn_force_bg_color = QToolButton()
        self.btn_force_bg_color.setText("...")
        self.btn_force_bg_color.setAutoRaise(True)
        force_color_wrap = QWidget()
        force_color_layout = QHBoxLayout(force_color_wrap)
        force_color_layout.setContentsMargins(0, 0, 0, 0)
        force_color_layout.setSpacing(6)
        force_color_layout.addWidget(self.le_force_bg_color)
        force_color_layout.addWidget(self.btn_force_bg_color)
        force_color_layout.addStretch(1)
        tip = paths_tt.get("Force Background Color", "")
        if tip:
            self.le_force_bg_color.setToolTip(tip)
            self.btn_force_bg_color.setToolTip(tip)

        pr.addWidget(self.chk_remove_bg, 0, 0, 1, 2, alignment=Qt.AlignLeft)
        pr.addWidget(self.chk_reframe, 0, 2, 1, 2, alignment=Qt.AlignLeft)
        pr.addWidget(self.chk_force_bg_output, 0, 6, 1, 2, alignment=Qt.AlignLeft)

        add_param_at(1, 0, "Tolerance", self.sp_tol)
        add_param_at(2, 0, "Feather", self.sp_feather)
        add_param_at(3, 0, "Bg Mode", self.cb_bg_mode)
        add_param_at(4, 0, "Shrink", self.sp_shrink)
        add_param_at(5, 0, "Key From", self.cb_key_from)
        pr.addWidget(self.chk_despill, 6, 0, 1, 2, alignment=Qt.AlignLeft)

        add_param_at(1, 2, "Baseline Y", self.sp_baseline_y)
        add_param_at(2, 2, "Left Limit X", self.sp_left_limit_x)
        add_param_at(3, 2, "Left Padding", self.sp_left_padding)
        add_param_at(4, 2, "Sprite Height", self.sp_sprite_h)
        add_param_at(5, 2, "Sprite Width", self.sp_sprite_w)
        add_param_at(6, 2, "Dimension Preference", self.cb_prefer)

        pr.addWidget(self.chk_res_1x, 1, 4, 1, 2, alignment=Qt.AlignLeft)
        pr.addWidget(self.chk_res_2x, 2, 4, 1, 2, alignment=Qt.AlignLeft)
        pr.addWidget(self.chk_res_3x, 3, 4, 1, 2, alignment=Qt.AlignLeft)
        pr.addWidget(self.chk_res_4x, 4, 4, 1, 2, alignment=Qt.AlignLeft)

        pr.addWidget(QLabel("Color"), 1, 6, alignment=Qt.AlignLeft)
        pr.addWidget(force_color_wrap, 1, 7, alignment=Qt.AlignLeft)

        fill_layout.addWidget(self.params_body)
        outer.addWidget(self.params_fill)
        self.params_fill.setVisible(False)
        def _toggle_params(checked: bool):
            self.params_fill.setVisible(checked)
            self.btn_toggle_params.setIcon(self._ico_arrow_down if checked else self._ico_arrow_right)
            if checked and hasattr(self, "btn_toggle_log") and self.btn_toggle_log.isChecked():
                self.btn_toggle_log.setChecked(False)
            self._ensure_splitter_log_visible()

        self.btn_toggle_params.toggled.connect(_toggle_params)

        adjust_tt = {
            "Brightness": "Overall lightness adjustment. Slider 0 is neutral.",
            "Contrast": "Difference between dark and bright areas. Slider 0 is neutral.",
            "Saturation": "Color intensity. Slider 0 is neutral.",
            "Sharpness": "Edge enhancement. Slider 0 is neutral.",
            "Gamma": "Midtone response. Slider 0 is neutral.",
            "Highlights": "Bright-area adjustment. Slider 0 is neutral.",
            "Shadows": "Dark-area adjustment. Slider 0 is neutral.",
        }

        self.gb_adjustments = QGroupBox("")
        self.gb_adjustments.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        adj_outer = QVBoxLayout(self.gb_adjustments)
        adj_outer.setContentsMargins(9, 6, 9, 9)
        adj_outer.setSpacing(6)

        adjust_header = QHBoxLayout()
        adjust_header.setContentsMargins(0, 0, 0, 0)
        adjust_header.setSpacing(6)
        self.btn_toggle_adjustments = QToolButton()
        self.btn_toggle_adjustments.setCheckable(True)
        self.btn_toggle_adjustments.setChecked(True)
        self.btn_toggle_adjustments.setAutoRaise(True)
        self.btn_toggle_adjustments.setToolTip("Show/Hide image adjustment controls")
        self.btn_toggle_adjustments.setIcon(self._ico_arrow_down)
        self.lb_adjustments_title = QLabel("Image Adjustments")
        self.lb_adjustments_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        adjust_header.addWidget(self.btn_toggle_adjustments)
        adjust_header.addWidget(self.lb_adjustments_title)
        self.adjust_profile_bar = QWidget()
        adjust_profile_layout = QHBoxLayout(self.adjust_profile_bar)
        adjust_profile_layout.setContentsMargins(0, 0, 0, 0)
        adjust_profile_layout.setSpacing(4)
        self.btn_adjust_load_global = QToolButton(); self.btn_adjust_load_global.setText("Load Global")
        self.btn_adjust_load_creature = QToolButton(); self.btn_adjust_load_creature.setText("Load Creature")
        self.btn_adjust_load_group = QToolButton(); self.btn_adjust_load_group.setText("Load Group")
        self.btn_adjust_save_global = QToolButton(); self.btn_adjust_save_global.setText("Save Global")
        self.btn_adjust_save_creature = QToolButton(); self.btn_adjust_save_creature.setText("Save Creature")
        self.btn_adjust_save_group = QToolButton(); self.btn_adjust_save_group.setText("Save Group")
        for btn in [
            self.btn_adjust_load_global, self.btn_adjust_load_creature, self.btn_adjust_load_group,
            self.btn_adjust_save_global, self.btn_adjust_save_creature, self.btn_adjust_save_group,
        ]:
            btn.setAutoRaise(True)
            adjust_profile_layout.addWidget(btn)
        adjust_header.addSpacing(22)
        adjust_header.addWidget(self.adjust_profile_bar)
        adjust_header.addStretch(1)
        adj_outer.addLayout(adjust_header)

        self.adjustments_scroll = QScrollArea()
        self.adjustments_scroll.setWidgetResizable(True)
        self.adjustments_scroll.setFrameShape(QFrame.NoFrame)
        self.adjustments_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.adjustments_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.adjustments_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.adjustments_scroll.setMinimumHeight(180)
        self.adjustments_scroll.setMaximumHeight(360)

        self.adjustments_body = QWidget()
        self.adjustments_body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        adjustments_body_layout = QVBoxLayout(self.adjustments_body)
        adjustments_body_layout.setContentsMargins(0, 0, 0, 0)
        adjustments_body_layout.setSpacing(8)

        def make_adjust_slider(minimum, maximum, value, suffix=""):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setValue(value)
            slider.setSingleStep(1)
            slider.setPageStep(10)
            slider.setStyleSheet(
                "QSlider { min-height: 26px; }"
                "QSlider::groove:horizontal { height: 6px; background: #d8e4f2; border-radius: 3px; }"
                "QSlider::sub-page:horizontal { background: #4f93e6; border-radius: 3px; }"
                "QSlider::add-page:horizontal { background: #e7eef8; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: white; border: 1px solid #7ea5cf; width: 16px; margin: -6px 0; border-radius: 8px; }"
                "QSlider::handle:horizontal:hover { background: #f7fbff; border: 1px solid #4A90E2; }"
            )

            value_label = QLabel(f"{value}{suffix}")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setMinimumWidth(44)

            scale_values = [
                minimum,
                minimum + ((maximum - minimum) // 4),
                0,
                minimum + (((maximum - minimum) * 3) // 4),
                maximum,
            ]
            scale_labels = [QLabel(str(v)) for v in scale_values]
            for lbl in scale_labels:
                lbl.setStyleSheet("color: #6a7f98; font-size: 10px;")
            scale_labels[0].setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            scale_labels[-1].setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for lbl in scale_labels[1:-1]:
                lbl.setAlignment(Qt.AlignCenter)

            def sync_label(v: int):
                value_label.setText(f"{v}{suffix}")

            slider.valueChanged.connect(sync_label)

            wrapper = QWidget()
            outer_layout = QVBoxLayout(wrapper)
            outer_layout.setContentsMargins(0, 0, 0, 0)
            outer_layout.setSpacing(2)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(8)
            top_row.addWidget(slider, 1)
            top_row.addWidget(value_label, 0)
            outer_layout.addLayout(top_row)

            tick_row = QHBoxLayout()
            tick_row.setContentsMargins(8, 0, 52, 0)
            tick_row.setSpacing(0)
            tick_row.addStretch(1)
            for idx in range(5):
                tick = QFrame()
                tick.setFixedSize(1, 7 if idx == 2 else 5)
                tick.setStyleSheet("background: #88a8cc;")
                tick_row.addWidget(tick, 0, Qt.AlignHCenter | Qt.AlignTop)
                if idx < 4:
                    tick_row.addStretch(1)
            outer_layout.addLayout(tick_row)

            scale_row = QHBoxLayout()
            scale_row.setContentsMargins(0, 0, 44, 0)
            scale_row.setSpacing(0)
            for idx, lbl in enumerate(scale_labels):
                scale_row.addWidget(lbl)
                if idx < len(scale_labels) - 1:
                    scale_row.addStretch(1)
            outer_layout.addLayout(scale_row)

            wrapper.slider = slider
            wrapper.value_label = value_label
            return wrapper
        def make_adjust_stage(title: str, prefix: str):
            box = QGroupBox(title)
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout = QVBoxLayout(box)
            layout.setContentsMargins(9, 9, 9, 9)
            layout.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(6)
            preview_btn = QPushButton("Preview/Edit")
            preview_btn.setMinimumWidth(100)
            preview_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
            reset_btn = QPushButton("Reset")
            reset_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
            reset_btn.setMinimumWidth(72)
            top_row.addWidget(preview_btn)
            top_row.addStretch(1)
            top_row.addWidget(reset_btn)
            layout.addLayout(top_row)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(6)

            fields = [
                ("brightness", "Brightness", 0),
                ("contrast", "Contrast", 0),
                ("saturation", "Saturation", 0),
                ("sharpness", "Sharpness", 0),
                ("gamma", "Gamma", 0),
                ("highlights", "Highlights", 0),
                ("shadows", "Shadows", 0),
            ]

            for idx, (name, label_text, value) in enumerate(fields):
                row = idx % 4
                col = (idx // 4) * 2
                label = QLabel(label_text)
                label.setMinimumWidth(72)
                control = QLineEdit()
                control.setReadOnly(True)
                control.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                control.setFixedWidth(54)
                control.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                control.current_value = value
                tip = adjust_tt[label_text]
                label.setToolTip(tip)
                control.setToolTip(tip)
                setattr(self, f"sp_{prefix}_{name}", control)
                self._set_adjust_slider_value(control, value)
                grid.addWidget(label, row, col)
                grid.addWidget(control, row, col + 1)

            layout.addLayout(grid)

            def reset_stage():
                defaults = {
                    "brightness": 0,
                    "contrast": 0,
                    "saturation": 0,
                    "sharpness": 0,
                    "gamma": 0,
                    "highlights": 0,
                    "shadows": 0,
                }
                for key, value in defaults.items():
                    self._set_adjust_slider_value(getattr(self, f"sp_{prefix}_{key}"), value)
                self._ui_to_settings()
                self._update_preview_status()

            preview_btn.clicked.connect(lambda _=False, stage=prefix: self._open_preview_window_for_stage(stage))
            reset_btn.clicked.connect(reset_stage)
            setattr(self, f"btn_{prefix}_preview_edit", preview_btn)
            setattr(self, f"btn_{prefix}_reset", reset_btn)
            return box

        self.gb_adjust_input_stage = make_adjust_stage("Input stage", "input")
        self.gb_adjust_output_stage = make_adjust_stage("Output stage", "output")
        self.adjust_transfer_widget = QWidget()
        transfer_layout = QVBoxLayout(self.adjust_transfer_widget)
        transfer_layout.setContentsMargins(0, 0, 0, 0)
        transfer_layout.setSpacing(8)
        transfer_layout.addStretch(1)
        self.btn_adjust_copy_input_to_output = QToolButton()
        self.btn_adjust_copy_input_to_output.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.btn_adjust_copy_input_to_output.setAutoRaise(True)
        self.btn_adjust_copy_output_to_input = QToolButton()
        self.btn_adjust_copy_output_to_input.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.btn_adjust_copy_output_to_input.setAutoRaise(True)
        self.btn_adjust_swap_stages = QToolButton()
        self.btn_adjust_swap_stages.setText("<>")
        self.btn_adjust_swap_stages.setAutoRaise(True)
        transfer_layout.addWidget(self.btn_adjust_copy_input_to_output, 0, Qt.AlignHCenter)
        transfer_layout.addWidget(self.btn_adjust_copy_output_to_input, 0, Qt.AlignHCenter)
        transfer_layout.addWidget(self.btn_adjust_swap_stages, 0, Qt.AlignHCenter)
        transfer_layout.addStretch(1)
        adjustments_stages_row = QHBoxLayout()
        adjustments_stages_row.setContentsMargins(0, 0, 0, 0)
        adjustments_stages_row.setSpacing(10)
        adjustments_stages_row.addWidget(self.gb_adjust_input_stage, 1)
        adjustments_stages_row.addWidget(self.adjust_transfer_widget, 0, Qt.AlignCenter)
        adjustments_stages_row.addWidget(self.gb_adjust_output_stage, 1)
        adjustments_body_layout.addLayout(adjustments_stages_row)
        self.adjustments_scroll.setWidget(self.adjustments_body)
        adj_outer.addWidget(self.adjustments_scroll, 1)

        def _toggle_adjustments(checked: bool):
            self.adjustments_scroll.setVisible(checked)
            self.btn_toggle_adjustments.setIcon(self._ico_arrow_down if checked else self._ico_arrow_right)
            if checked and hasattr(self, "btn_toggle_log") and self.btn_toggle_log.isChecked():
                self.btn_toggle_log.setChecked(False)

        self.btn_toggle_adjustments.toggled.connect(_toggle_adjustments)

        self._syncing_panel_toggles = False

        def _sync_open_panels(source: str, checked: bool):
            if self._syncing_panel_toggles:
                return
            self._syncing_panel_toggles = True
            try:
                if source == "params" and self.btn_toggle_adjustments.isChecked() != checked:
                    self.btn_toggle_adjustments.setChecked(checked)
                elif source == "adjustments" and self.btn_toggle_params.isChecked() != checked:
                    self.btn_toggle_params.setChecked(checked)
            finally:
                self._syncing_panel_toggles = False

        self.btn_toggle_params.toggled.connect(lambda checked: _sync_open_panels("params", checked))
        self.btn_toggle_adjustments.toggled.connect(lambda checked: _sync_open_panels("adjustments", checked))

        def _sync_params_row_height():
            try:
                self.gb_params_outer.setMinimumHeight(0)
                self.gb_params_outer.setMaximumHeight(16777215)
                self.gb_adjustments.setMinimumHeight(0)
                self.gb_adjustments.setMaximumHeight(16777215)
                self.params_row_widget.setMinimumHeight(0)
                self.params_row_widget.setMaximumHeight(16777215)

                height = max(self.gb_params_outer.sizeHint().height(), self.gb_adjustments.sizeHint().height())
                self.params_row_widget.setFixedHeight(height)

                if self.btn_toggle_params.isChecked():
                    self.gb_params_outer.setFixedHeight(height)
                else:
                    self.gb_params_outer.setFixedHeight(self.gb_params_outer.sizeHint().height())

                if self.btn_toggle_adjustments.isChecked():
                    self.gb_adjustments.setFixedHeight(height)
                else:
                    self.gb_adjustments.setFixedHeight(self.gb_adjustments.sizeHint().height())
            except Exception:
                pass

        self.btn_toggle_params.toggled.connect(lambda _=False: QTimer.singleShot(0, _sync_params_row_height))
        self.btn_toggle_adjustments.toggled.connect(lambda _=False: QTimer.singleShot(0, _sync_params_row_height))

        self.params_row_widget = QWidget()
        self.params_row_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        params_row = QHBoxLayout(self.params_row_widget)
        params_row.setContentsMargins(0, 0, 0, 0)
        params_row.setSpacing(12)
        params_row.setAlignment(Qt.AlignTop)
        params_row.addWidget(self.gb_params_outer, 1, Qt.AlignTop)
        params_row.addWidget(self.gb_adjustments, 1, Qt.AlignTop)
        root.addWidget(self.params_row_widget, 0, Qt.AlignTop)
        QTimer.singleShot(0, _sync_params_row_height)

        # -------- Viewer + Log (vertical splitter) --------
        self.splitter = QSplitter(Qt.Vertical)

        # Viewer group (top)
        self.gb_view = QGroupBox("Viewer")
        vbox = QVBoxLayout(self.gb_view)

        self.tabs = QTabWidget()
        self.btn_viewer_preview = QToolButton(self.tabs)
        self.btn_viewer_preview.setAutoRaise(True)
        self.btn_viewer_preview.setIcon(_make_preview_icon())
        self.btn_viewer_preview.setToolTip("Open the preview editor for the current viewer frame.")
        self.btn_viewer_preview.setCursor(Qt.PointingHandCursor)
        self.btn_viewer_preview.setFixedSize(28, 28)
        self.btn_viewer_preview.setIconSize(QSize(18, 18))
        self.btn_viewer_preview.setStyleSheet(
            "QToolButton { background: rgba(245, 247, 250, 0.92); border: 1px solid #b7c6d9; border-radius: 6px; padding: 0; margin-right: 6px; }"
            "QToolButton:hover { background: rgba(255, 255, 255, 0.98); border-color: #8ea8c7; }"
        )
        self.tabs.setCornerWidget(self.btn_viewer_preview, Qt.TopRightCorner)
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
            "Inputs",
            "Outputs",
            "Cleaned Alpha",
            "Previews",
            "Forced Background",
            "Deployed",
        ])
        self.cb_view_scale = QComboBox()
        self.cb_view_scale.addItem("1x", 1)
        self.cb_view_scale.addItem("2x", 2)
        self.cb_view_scale.addItem("3x", 3)
        self.cb_view_scale.addItem("4x", 4)
        self.cb_view_scale.setCurrentIndex(3)

        self.cb_view_creature = QComboBox()
        self.cb_view_group = QComboBox()
        self.cb_view_frame = QComboBox()

        self.btn_view_refresh = QPushButton("Refresh")
        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_prev = QPushButton("Prev (A)")
        self.btn_next = QPushButton("Next (D)")

        controls.addWidget(QLabel("Source"))
        controls.addWidget(self.cb_view_source)
        controls.addWidget(QLabel("Resolution"))
        controls.addWidget(self.cb_view_scale)
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
        self.btn_pick_canvas_bg.setText("...")
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

        viewer_canvas_wrap = QWidget()
        viewer_canvas_layout = QVBoxLayout(viewer_canvas_wrap)
        viewer_canvas_layout.setContentsMargins(0, 0, 0, 0)
        viewer_canvas_layout.setSpacing(0)

        viewer_stack = QWidget()
        viewer_stack_layout = QGridLayout(viewer_stack)
        viewer_stack_layout.setContentsMargins(0, 0, 0, 0)
        viewer_stack_layout.setSpacing(0)
        viewer_stack_layout.addWidget(self.viewer, 0, 0)

        viewer_canvas_layout.addWidget(viewer_stack, 1)

        images_row.addWidget(self.images_controls_scroll, 0)
        images_row.addWidget(viewer_canvas_wrap, 1)

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
        self.btn_json_open_folder = QPushButton("Open Folder")

        self.json_text = QPlainTextEdit()
        self.json_text.setReadOnly(True)

        jv.addWidget(QLabel("Source"), 0, 0)
        jv.addWidget(self.cb_json_source, 0, 1)
        jv.addWidget(self.btn_json_refresh, 0, 2)

        jv.addWidget(QLabel("Creature"), 1, 0)
        jv.addWidget(self.cb_json_creature, 1, 1)
        jv.addWidget(self.btn_json_open, 1, 2)
        jv.addWidget(self.btn_json_open_folder, 1, 3)

        jv.addWidget(self.json_text, 2, 0, 1, 4)

        self.tabs.addTab(self.tab_json, "JSON")

        # Log group (bottom) - small, pop-out available
        self.gb_log = QGroupBox("")
        self.gb_log.setFlat(True)
        self.gb_log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        lg = QVBoxLayout(self.gb_log)
        lg.setContentsMargins(6, 4, 6, 6)
        lg.setSpacing(4)

        log_top = QHBoxLayout()
        log_top.setContentsMargins(4, 2, 4, 2)
        log_top.setSpacing(6)
        self.lb_log_title = QLabel("Log")
        self.lb_log_title.setContentsMargins(0, 0, 0, 0)
        self.btn_toggle_log = QToolButton()
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(True)
        self.btn_toggle_log.setAutoRaise(True)
        self._ico_log_show = self.style().standardIcon(QStyle.SP_ArrowDown)
        self._ico_log_hide = self.style().standardIcon(QStyle.SP_ArrowRight)
        self.btn_toggle_log.setIcon(self._ico_log_show)
        self.btn_toggle_log.setToolTip("Show/Hide log")
        self.btn_toggle_log.setFixedSize(18, 18)
        log_top.addWidget(self.btn_toggle_log)
        log_top.addWidget(self.lb_log_title)
        log_top.addStretch(1)

        self.btn_log_find = QToolButton()
        self.btn_log_find.setAutoRaise(True)
        self.btn_log_find.setFixedSize(18, 18)
        self.btn_log_find.setToolTip("Find in log (Ctrl+F)")
        self.btn_log_find.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))

        self.btn_log_pop = QToolButton()
        self.btn_log_pop.setAutoRaise(True)
        self.btn_log_pop.setFixedSize(18, 18)
        self.btn_log_pop.setToolTip("Pop-out log")
        self.btn_log_pop.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))

        self.btn_log_clear = QToolButton()
        self.btn_log_clear.setAutoRaise(True)
        self.btn_log_clear.setFixedSize(18, 18)
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
        self.log_find_box.setPlaceholderText("Find...")
        self.btn_log_find_prev = QToolButton()
        self.btn_log_find_prev.setText("Prev")
        self.btn_log_find_prev.setAutoRaise(True)
        self.btn_log_find_next = QToolButton()
        self.btn_log_find_next.setText("Next")
        self.btn_log_find_next.setAutoRaise(True)
        self.btn_log_find_close = QToolButton()
        self.btn_log_find_close.setText("x")
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
            self.le_mod_assets_root, self.le_mod_json_root, self.le_hex_overlay, self.le_sheet
        ]:
            le.textChanged.connect(self.refresh_ui_state)
        self.le_only_creature.lineEdit().textChanged.connect(self.refresh_ui_state)
        self.le_input_root.textChanged.connect(lambda _=None: self._refresh_scope_creature_choices())
        self.btn_scope_refresh.clicked.connect(self._refresh_scope_creature_choices)

        self.cb_only_group.currentIndexChanged.connect(self.refresh_ui_state)
        self.chk_split.toggled.connect(self.refresh_ui_state)
        self.chk_split.toggled.connect(self._update_scope_hint)
        self.chk_adjust_input.toggled.connect(self.refresh_ui_state)
        self.chk_process.toggled.connect(self.refresh_ui_state)
        self.chk_adjust_output.toggled.connect(self.refresh_ui_state)
        self.chk_json.toggled.connect(self.refresh_ui_state)
        self.chk_deploy.toggled.connect(self.refresh_ui_state)
        self.chk_remove_bg.toggled.connect(self.refresh_ui_state)
        self.chk_reframe.toggled.connect(self.refresh_ui_state)
        self.chk_force_bg_output.toggled.connect(self.refresh_ui_state)
        self.chk_res_1x.toggled.connect(self.refresh_ui_state)
        self.chk_res_2x.toggled.connect(self.refresh_ui_state)
        self.chk_res_3x.toggled.connect(self.refresh_ui_state)
        self.chk_res_4x.toggled.connect(self.refresh_ui_state)
        self.btn_use_viewer_scope.clicked.connect(self._use_viewer_selection_for_scope)
        self.btn_scope_save_profile.clicked.connect(self._save_scope_profile_bundle)
        self.btn_adjust_copy_input_to_output.clicked.connect(lambda: self._copy_adjustment_stage("input", "output"))
        self.btn_adjust_copy_output_to_input.clicked.connect(lambda: self._copy_adjustment_stage("output", "input"))
        self.btn_adjust_swap_stages.clicked.connect(self._swap_adjustment_stages)
        self.btn_params_load_global.clicked.connect(lambda: self._load_profile_into_ui("process_frames", "global"))
        self.btn_params_load_creature.clicked.connect(lambda: self._load_profile_into_ui("process_frames", "creature"))
        self.btn_params_load_group.clicked.connect(lambda: self._load_profile_into_ui("process_frames", "group"))
        self.btn_params_save_global.clicked.connect(lambda: self._save_profile_from_ui("process_frames", "global"))
        self.btn_params_save_creature.clicked.connect(lambda: self._save_profile_from_ui("process_frames", "creature"))
        self.btn_params_save_group.clicked.connect(lambda: self._save_profile_from_ui("process_frames", "group"))
        self.btn_adjust_load_global.clicked.connect(lambda: self._load_profile_into_ui("image_adjustments", "global"))
        self.btn_adjust_load_creature.clicked.connect(lambda: self._load_profile_into_ui("image_adjustments", "creature"))
        self.btn_adjust_load_group.clicked.connect(lambda: self._load_profile_into_ui("image_adjustments", "group"))
        self.btn_adjust_save_global.clicked.connect(lambda: self._save_profile_from_ui("image_adjustments", "global"))
        self.btn_adjust_save_creature.clicked.connect(lambda: self._save_profile_from_ui("image_adjustments", "creature"))
        self.btn_adjust_save_group.clicked.connect(lambda: self._save_profile_from_ui("image_adjustments", "group"))

        self.btn_steps_all.clicked.connect(self.steps_select_all)
        self.btn_steps_none.clicked.connect(self.steps_select_none)

        self.btn_view_refresh.clicked.connect(lambda: self.viewer_refresh_all(keep_selection=True))
        self.cb_view_source.currentIndexChanged.connect(lambda: self.viewer_refresh_all(keep_selection=True))
        self.cb_view_scale.currentIndexChanged.connect(lambda: self.viewer_refresh_all(keep_selection=True))
        self.cb_view_creature.currentIndexChanged.connect(lambda: self.viewer_refresh_groups(keep_selection=True))
        self.cb_view_group.currentIndexChanged.connect(lambda: self.viewer_refresh_frames(keep_selection=True))
        self.cb_view_frame.currentIndexChanged.connect(self.viewer_load_selected)
        self.btn_open_folder.clicked.connect(self.viewer_open_folder)
        self.btn_viewer_preview.clicked.connect(self._open_preview_window)
        self.btn_pick_canvas_bg.clicked.connect(self._pick_canvas_bg)
        self.btn_force_bg_color.clicked.connect(self._pick_force_bg_color)
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
        self.btn_json_open_folder.clicked.connect(self.json_open_folder)

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

    def _pick_force_bg_color(self):
        current = QColor(self.le_force_bg_color.text().strip() or "#FF00FF")
        c = QColorDialog.getColor(current, parent=self)
        if not c.isValid():
            return
        self.le_force_bg_color.setText(c.name().upper())

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
        tt(self.lb_scope_creature, self.le_only_creature, "Optional creature scope. You can type a creature_id manually or pick one discovered under Inputs. Empty = all creatures.")
        tt(self.lb_scope_group, self.cb_only_group, "Optional group scope. All = all groups present in the selected creature folder.")
        tt(None, self.btn_scope_refresh, "Rescan creature folders under Inputs and refresh the Scope creature list.")
        tt(None, self.btn_use_viewer_scope, "Copy the current Viewer creature and group into Scope.")
        tt(None, self.btn_scope_save_profile, "Save both Process Frames and Image Adjustments profiles at the active scope level.")
        tt(None, self.lb_scope_hint, "Scope filters existing content for most steps. When Split is enabled, it also defines the destination creature/group.")
        tt(None, self.btn_params_load_global, "Load global Process Frames values from settings.json.")
        tt(None, self.btn_params_load_creature, "Load Process Frames values from the creature profile under inputs/<creature_id>.")
        tt(None, self.btn_params_load_group, "Load Process Frames values from the group profile under inputs/<creature_id>/groupN.")
        tt(None, self.btn_params_save_global, "Save current Process Frames values as global defaults in settings.json.")
        tt(None, self.btn_params_save_creature, "Save current Process Frames values to the creature profile under inputs/<creature_id>.")
        tt(None, self.btn_params_save_group, "Save current Process Frames values to the group profile under inputs/<creature_id>/groupN.")
        tt(None, self.btn_adjust_load_global, "Load global Image Adjustments values from settings.json.")
        tt(None, self.btn_adjust_load_creature, "Load Image Adjustments values from the creature profile under inputs/<creature_id>.")
        tt(None, self.btn_adjust_load_group, "Load Image Adjustments values from the group profile under inputs/<creature_id>/groupN.")
        tt(None, self.btn_adjust_save_global, "Save current Image Adjustments values as global defaults in settings.json.")
        tt(None, self.btn_adjust_save_creature, "Save current Image Adjustments values to the creature profile under inputs/<creature_id>.")
        tt(None, self.btn_adjust_save_group, "Save current Image Adjustments values to the group profile under inputs/<creature_id>/groupN.")

        # ---- Steps ----
        tt(None, self.chk_split, "Step 1: Split a spritesheet into frames (slice_sheet.py).")
        tt(None, self.chk_adjust_input, "Step 2: Apply image adjustments to frames in input_root using adjust_frames.py.")
        tt(None, self.chk_process, "Step 3: Process frames (chroma key removal + scale + align to 450x400).")
        tt(None, self.chk_adjust_output, "Step 4: Apply image adjustments to frames in processed_root using adjust_frames.py.")
        tt(None, self.chk_json, "Step 5: Build <creature_id>.json animation files from processed frames.")
        tt(None, self.chk_deploy, "Step 6: Deploy PNGs + merge JSON incrementally into mod folder.")
        if hasattr(self, "btn_steps_all"):
            tt(None, self.btn_steps_all, "Select all pipeline steps.")
        if hasattr(self, "btn_steps_none"):
            tt(None, self.btn_steps_none, "Deselect all pipeline steps.")

        # ---- Split options ----
        tt(self.lb_sheet, self.le_sheet, "Input spritesheet image to split.")
        tt(None, self.btn_sheet, "Browse for spritesheet.")
        tt(None, self.btn_sheet_open, "Open the current spritesheet folder.")
        tt(self.lb_cols, self.sp_cols, "Grid columns in spritesheet.")
        tt(self.lb_rows, self.sp_rows, "Grid rows in spritesheet.")
        tt(None, self.chk_autocrop, "Auto-crop spritesheet to be divisible by rows/cols.")

        # ---- Process defaults ----
        tt(None, self.btn_toggle_params, "Show/Hide the frame-processing options used by the Process Frames step.")
        tt(None, self.btn_toggle_adjustments, "Show/Hide image adjustment controls.")
        tt(None, self.chk_despill, "Enable despill to reduce chroma spill (magenta/green).")
        tt(None, self.chk_remove_bg, "Run chroma/key cleanup for Process Frames.")
        tt(None, self.chk_reframe, "Resize, align, and compose the sprite onto the target canvas.")
        tt(None, self.chk_force_bg_output, "Generate the forced background helper output in forced_bg using the selected color.")
        tt(None, self.chk_res_1x, "Generate 1x processed output. This is the currently used resolution for JSON, deploy, and output adjustments.")
        tt(None, self.chk_res_2x, "Generate 2x processed output alongside any other selected resolutions.")
        tt(None, self.chk_res_3x, "Generate 3x processed output alongside any other selected resolutions.")
        tt(None, self.chk_res_4x, "Generate 4x processed output alongside any other selected resolutions.")

        # ---- Viewer controls ----
        tt(None, self.cb_view_source, "Select viewer source root (Inputs/Outputs/Cleaned Alpha/Previews/Forced Background/Deployed).")
        tt(None, self.cb_view_scale, "Select the resolution variant to browse for processed, preview, cleaned, or forced outputs.")
        tt(None, self.btn_view_refresh, "Refresh viewer lists (creature/group/frame).")
        tt(None, self.cb_view_creature, "Select creature folder under current source root.")
        tt(None, self.cb_view_group, "Select animation group (groupN).")
        tt(None, self.cb_view_frame, "Select PNG frame to preview.")
        tt(None, self.btn_open_folder, "Open selected folder in file explorer.")
        tt(None, self.btn_viewer_preview, "Open the preview editor for the current viewer frame.")
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
        tt(None, self.btn_json_open_folder, "Open the current JSON source folder.")

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
            self.lb_params_title.setToolTip("Options for background cleanup, reframing, output resolutions, and forced background helper generation.")
        if hasattr(self, "gb_adjustments"):
            self.gb_adjustments.setToolTip("Independent image adjustment controls for input and output stages.")
            self.lb_adjustments_title.setToolTip("Independent image adjustment controls for input and output stages.")
            self.gb_adjust_input_stage.setToolTip("Saved settings used by the Adjust Input pipeline step.")
            self.gb_adjust_output_stage.setToolTip("Saved settings used by the Adjust Output pipeline step.")
        if hasattr(self, "btn_input_preview_edit"):
            self.btn_input_preview_edit.setToolTip("Open the live preview editor loaded with the Input stage values.")
        if hasattr(self, "btn_output_preview_edit"):
            self.btn_output_preview_edit.setToolTip("Open the live preview editor loaded with the Output stage values.")
        if hasattr(self, "btn_input_reset"):
            self.btn_input_reset.setToolTip("Reset saved Input stage values to neutral.")
        if hasattr(self, "btn_output_reset"):
            self.btn_output_reset.setToolTip("Reset saved Output stage values to neutral.")
        if hasattr(self, "btn_adjust_copy_input_to_output"):
            self.btn_adjust_copy_input_to_output.setToolTip("Copy Input stage adjustment values into Output stage.")
        if hasattr(self, "btn_adjust_copy_output_to_input"):
            self.btn_adjust_copy_output_to_input.setToolTip("Copy Output stage adjustment values into Input stage.")
        if hasattr(self, "btn_adjust_swap_stages"):
            self.btn_adjust_swap_stages.setToolTip("Swap Input stage and Output stage adjustment values.")
        if hasattr(self, "lb_log_title"):
            self.lb_log_title.setToolTip("Embedded log; use Pop-out for larger view.")

# ---------------- dynamic UI state ----------------
    def _wire_dynamic_ui(self):
        self.gb_split.setEnabled(self.chk_split.isChecked())
        self.chk_split.toggled.connect(self.gb_split.setEnabled)

        def sync_params_enabled():
            enabled = self.chk_process.isChecked()
            self.gb_params_outer.setVisible(True)
            if enabled and not self.btn_toggle_params.isChecked():
                self.btn_toggle_params.setChecked(True)
            elif (not enabled) and self.btn_toggle_params.isChecked():
                self.btn_toggle_params.setChecked(False)
            self._ensure_splitter_log_visible()

        def sync_process_action_enabled():
            bg_enabled = self.chk_remove_bg.isChecked()
            self.sp_tol.setEnabled(bg_enabled)
            self.sp_feather.setEnabled(bg_enabled)
            self.cb_bg_mode.setEnabled(bg_enabled)
            self.sp_shrink.setEnabled(bg_enabled)
            self.cb_key_from.setEnabled(bg_enabled)
            self.chk_despill.setEnabled(bg_enabled)

            reframe_enabled = self.chk_reframe.isChecked()
            self.sp_baseline_y.setEnabled(reframe_enabled)
            self.sp_left_limit_x.setEnabled(reframe_enabled)
            self.sp_left_padding.setEnabled(reframe_enabled)
            self.sp_sprite_h.setEnabled(reframe_enabled)
            self.sp_sprite_w.setEnabled(reframe_enabled)
            self.cb_prefer.setEnabled(reframe_enabled)
            self.chk_res_1x.setEnabled(reframe_enabled)
            self.chk_res_2x.setEnabled(reframe_enabled)
            self.chk_res_3x.setEnabled(reframe_enabled)
            self.chk_res_4x.setEnabled(reframe_enabled)

            force_enabled = self.chk_force_bg_output.isChecked()
            self.le_force_bg_color.setEnabled(force_enabled)
            self.btn_force_bg_color.setEnabled(force_enabled)

        def sync_adjustments_enabled():
            self.gb_adjust_input_stage.setEnabled(True)
            self.gb_adjust_output_stage.setEnabled(True)

        self.chk_process.toggled.connect(sync_params_enabled)
        self.chk_remove_bg.toggled.connect(sync_process_action_enabled)
        self.chk_reframe.toggled.connect(sync_process_action_enabled)
        self.chk_force_bg_output.toggled.connect(sync_process_action_enabled)
        sync_params_enabled()
        sync_process_action_enabled()
        sync_adjustments_enabled()

    def _format_adjust_display(self, value: int) -> str:
        return "0" if value == 0 else f"{value:+d}"

    def _adjust_slider_value(self, widget) -> int:
        if hasattr(widget, "slider"):
            return widget.slider.value()
        return int(getattr(widget, "current_value", 0))

    def _set_adjust_slider_value(self, widget, value: int):
        if hasattr(widget, "slider"):
            widget.slider.setValue(value)
            return
        widget.current_value = int(value)
        widget.setText(self._format_adjust_display(int(value)))

    def _stored_adjust_to_slider(self, name: str, value: int) -> int:
        if name in {"brightness", "contrast", "saturation", "sharpness", "gamma"}:
            return value - 100
        return value

    def _slider_adjust_to_stored(self, name: str, value: int) -> int:
        if name in {"brightness", "contrast", "saturation", "sharpness", "gamma"}:
            return value + 100
        return value

    def _selected_group_value(self) -> int | None:
        idx = self.cb_only_group.currentIndex()
        if idx <= 0:
            return None
        try:
            return int(self.cb_only_group.currentData())
        except Exception:
            return None

    def _scope_has_png_content(self, root_path: str) -> bool:
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            return False

        creature = self.le_only_creature.currentText().strip()
        group = self._selected_group_value()
        creature_dirs = [root / creature] if creature else [p for p in root.iterdir() if p.is_dir()]

        for creature_dir in creature_dirs:
            if not creature_dir.exists() or not creature_dir.is_dir():
                continue
            if group is None:
                group_dirs = [p for p in creature_dir.iterdir() if p.is_dir() and p.name.lower().startswith("group")]
            else:
                group_dirs = [creature_dir / f"group{group}"]
            for group_dir in group_dirs:
                if not group_dir.exists() or not group_dir.is_dir():
                    continue
                for png in group_dir.iterdir():
                    if png.is_file() and png.suffix.lower() == ".png":
                        return True
        return False

    def _require_scope_content(self, root_path: str, step_name: str) -> bool:
        if self._scope_has_png_content(root_path):
            return True
        QMessageBox.warning(
            self,
            step_name,
            f"No PNG content was found for the selected scope in:\n{root_path}\n\nThe '{step_name}' step will be aborted.",
        )
        return False

    def _append_adjust_command(self, cmds: list[list[str]], in_root: str, stage_prefix: str):
        creature, group = self._scope_values()
        cmd = [
            sys.executable, script_path(self.s.scripts_dir, "adjust_frames.py"),
            "--in_root", in_root,
            "--out_root", in_root,
            "--brightness", str(getattr(self.s, f"{stage_prefix}_brightness")),
            "--contrast", str(getattr(self.s, f"{stage_prefix}_contrast")),
            "--saturation", str(getattr(self.s, f"{stage_prefix}_saturation")),
            "--sharpness", str(getattr(self.s, f"{stage_prefix}_sharpness")),
            "--gamma", str(getattr(self.s, f"{stage_prefix}_gamma")),
            "--highlights", str(getattr(self.s, f"{stage_prefix}_highlights")),
            "--shadows", str(getattr(self.s, f"{stage_prefix}_shadows")),
        ]
        if creature:
            cmd += ["--creature", creature]
        if group is not None:
            cmd += ["--group", str(group)]
        cmds.append(cmd)

    def _selected_process_scales(self) -> list[int]:
        scales = []
        if getattr(self, "chk_res_1x", None) and self.chk_res_1x.isChecked():
            scales.append(1)
        if getattr(self, "chk_res_2x", None) and self.chk_res_2x.isChecked():
            scales.append(2)
        if getattr(self, "chk_res_3x", None) and self.chk_res_3x.isChecked():
            scales.append(3)
        if getattr(self, "chk_res_4x", None) and self.chk_res_4x.isChecked():
            scales.append(4)
        return scales

    def _processed_scale_root(self, scale: int) -> str:
        root = Path(self.s.processed_root)
        return str(root / f"{scale}x")

    def _aux_scale_root(self, folder_name: str, scale: int) -> str:
        root = Path(self.s.processed_root)
        return str(root.parent / folder_name / f"{scale}x")

    def _deploy_scale_root(self, scale: int) -> Path | None:
        root_text = self.le_mod_assets_root.text().strip()
        if not is_nonempty(root_text):
            return None
        root = Path(root_text)
        if scale == 1:
            return root
        parts = list(root.parts)
        lowered = [p.lower() for p in parts]
        if "sprites" not in lowered:
            return root
        idx = lowered.index("sprites")
        parts[idx] = f"sprites{scale}x"
        return Path(*parts)

    def _build_process_command(
        self,
        in_root: str,
        out_root: str,
        *,
        scale: int,
        remove_bg: bool,
        reframe: bool,
        force_bg: bool,
        clean_root: str = "",
        forced_root: str = "",
        preview_root: str = "",
    ) -> list[str]:
        s = self.s
        creature, group = self._scope_values()
        canvas_w = 450 * scale
        canvas_h = 400 * scale

        cmd = [
            sys.executable, script_path(s.scripts_dir, "process_frames.py"),
            "--in_root", in_root,
            "--out_root", out_root,
        ]
        if clean_root:
            cmd += ["--clean_root", clean_root]
        if forced_root:
            cmd += ["--forced_root", forced_root, "--force-bg-color", self.le_force_bg_color.text().strip() or "#FF00FF"]
        if preview_root:
            cmd += ["--preview_root", preview_root]
        if remove_bg:
            cmd += [
                "--key", "auto",
                "--key_from", s.key_from,
                "--bg_mode", s.bg_mode,
                "--tol", str(s.tol),
                "--feather", str(s.feather),
                "--shrink", str(s.shrink),
            ]
            cmd += ["--remove-bg"]
        if reframe:
            cmd += [
                "--canvas_w", str(canvas_w),
                "--canvas_h", str(canvas_h),
                "--baseline_y", str(s.baseline_y * scale),
                "--sprite_h", str(s.sprite_h * scale if s.sprite_h > 0 else 0),
                "--sprite_w", str(getattr(s, "sprite_w", 0) * scale if getattr(s, "sprite_w", 0) > 0 else 0),
                "--prefer", str(getattr(s, "prefer", "height")),
                "--x_mode", "left_limit",
                "--left_limit_x", str(s.left_limit_x * scale),
                "--left_padding", str(s.left_padding * scale),
                "--overlay_alpha", str(s.overlay_alpha),
            ]
            cmd += ["--reframe"]
        if force_bg:
            cmd += ["--force-bg"]
        if remove_bg and s.despill:
            cmd += ["--despill"]
        if reframe and s.hex_overlay.strip():
            cmd += ["--hex_overlay", s.hex_overlay.strip()]
        if creature:
            cmd += ["--only_creature", creature]
        if group is not None:
            cmd += ["--only_group", str(group)]
        return cmd

    def _stage_values_from_ui(self, stage: str) -> dict[str, int]:
        return {
            "brightness": self._slider_adjust_to_stored("brightness", self._adjust_slider_value(getattr(self, f"sp_{stage}_brightness"))),
            "contrast": self._slider_adjust_to_stored("contrast", self._adjust_slider_value(getattr(self, f"sp_{stage}_contrast"))),
            "saturation": self._slider_adjust_to_stored("saturation", self._adjust_slider_value(getattr(self, f"sp_{stage}_saturation"))),
            "sharpness": self._slider_adjust_to_stored("sharpness", self._adjust_slider_value(getattr(self, f"sp_{stage}_sharpness"))),
            "gamma": self._slider_adjust_to_stored("gamma", self._adjust_slider_value(getattr(self, f"sp_{stage}_gamma"))),
            "highlights": self._slider_adjust_to_stored("highlights", self._adjust_slider_value(getattr(self, f"sp_{stage}_highlights"))),
            "shadows": self._slider_adjust_to_stored("shadows", self._adjust_slider_value(getattr(self, f"sp_{stage}_shadows"))),
        }

    def _apply_values_to_stage_ui(self, stage: str, values: dict[str, int]):
        for name, stored in values.items():
            self._set_adjust_slider_value(getattr(self, f"sp_{stage}_{name}"), self._stored_adjust_to_slider(name, stored))
        self._ui_to_settings()
        self._update_preview_status()
        if self.preview_window is not None and self.preview_window.isVisible() and self.preview_window.edit_stage == stage:
            self.preview_window.set_stage_values(stage, values)
            self._schedule_viewer_preview(stage)

    def _copy_adjustment_stage(self, source: str, target: str):
        values = self._stage_values_from_ui(source)
        self._apply_values_to_stage_ui(target, values)

    def _swap_adjustment_stages(self):
        input_values = self._stage_values_from_ui("input")
        output_values = self._stage_values_from_ui("output")
        self._apply_values_to_stage_ui("input", output_values)
        self._apply_values_to_stage_ui("output", input_values)

    def _previewable_stage_values(self, stage: str) -> dict[str, int]:
        if self.preview_window is not None and self.preview_window.isVisible() and self.preview_window.edit_stage == stage:
            return self.preview_window.current_values()
        return self._stage_values_from_ui(stage)

    def _stage_has_preview_adjustments(self, stage: str) -> bool:
        return any(value != 0 for value in [
            self._adjust_slider_value(getattr(self, f"sp_{stage}_brightness")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_contrast")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_saturation")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_sharpness")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_gamma")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_highlights")),
            self._adjust_slider_value(getattr(self, f"sp_{stage}_shadows")),
        ])

    def _effective_preview_stage(self) -> str | None:
        if self.preview_window is not None and self.preview_window.isVisible():
            return self.preview_window.edit_stage
        preferred = self.preview_stage_preference
        if self._stage_has_preview_adjustments(preferred):
            return preferred
        other = "output" if preferred == "input" else "input"
        if self._stage_has_preview_adjustments(other):
            return other
        return None

    def _load_preview_source_image(self, path: Path) -> Image.Image | None:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if self.preview_source_path == resolved and self.preview_source_image is not None:
            return self.preview_source_image.copy()
        try:
            with Image.open(path) as img:
                cached = img.convert("RGBA").copy()
            self.preview_source_path = resolved
            self.preview_source_image = cached
            return cached.copy()
        except Exception:
            self.preview_source_path = None
            self.preview_source_image = None
            return None

    def _pixmap_from_pil(self, img: Image.Image) -> QPixmap:
        return QPixmap.fromImage(ImageQt(img))

    def _ensure_preview_window(self) -> PreviewWindow:
        if self.preview_window is None:
            self.preview_window = PreviewWindow(self)
            self.preview_window.btn_apply_input.clicked.connect(lambda: self._apply_preview_values_to_stage("input"))
            self.preview_window.btn_apply_output.clicked.connect(lambda: self._apply_preview_values_to_stage("output"))
            self.preview_window.btn_edit_input.clicked.connect(lambda: self._open_preview_window_for_stage("input"))
            self.preview_window.btn_edit_output.clicked.connect(lambda: self._open_preview_window_for_stage("output"))
        return self.preview_window

    def _open_preview_window(self):
        self._open_preview_window_for_stage(None)

    def _open_preview_window_for_stage(self, stage: str | None):
        win = self._ensure_preview_window()
        win._fit_on_next_refresh = False
        source_stage = stage if stage in {"input", "output"} else None
        if source_stage in {"input", "output"}:
            values = self._previewable_stage_values(source_stage)
        else:
            values = {
                "brightness": 100,
                "contrast": 100,
                "saturation": 100,
                "sharpness": 100,
                "gamma": 100,
                "highlights": 0,
                "shadows": 0,
            }
        win.set_stage_values(stage, values)
        win.show()
        win.raise_()
        win.activateWindow()
        if stage in {"input", "output"}:
            self.preview_stage_preference = stage
        self._schedule_viewer_preview(stage)

    def _apply_preview_values_to_stage(self, stage: str):
        if self.preview_window is None:
            return
        self._apply_values_to_stage_ui(stage, self.preview_window.current_values())
        self.preview_window.close()

    def _current_preview_status_text(self) -> str:
        p = self.viewer_selected_path()
        stage = self._effective_preview_stage()
        if self.preview_window is not None and self.preview_window.isVisible():
            stage_text = f"Editing {stage.title()} stage" if stage else "Editing preview"
        else:
            stage_text = f"{stage.title()} stage" if stage else "No active adjustments"
        creature = self.cb_view_creature.currentText().strip() or "-"
        group = self.cb_view_group.currentText().strip() or "-"
        frame = p.name if p else "No frame selected"
        return f"{stage_text} | {creature} | {group} | {frame}"

    def _update_preview_window(self, original: QPixmap | None = None, preview: QPixmap | None = None):
        if self.preview_window is None:
            return
        self.preview_window.set_status(self._current_preview_status_text())
        if original is not None or preview is not None:
            self.preview_window.set_pixmaps(original, preview)

    def _update_preview_status(self):
        self._update_preview_window()

    def _restore_initial_viewer_state_if_needed(self):
        if not self._pending_viewer_state_restore:
            return
        scale = float(getattr(self.s, "viewer_zoom_scale", 0.0) or 0.0)
        hscroll = int(getattr(self.s, "viewer_hscroll", 0) or 0)
        vscroll = int(getattr(self.s, "viewer_vscroll", 0) or 0)
        self._pending_viewer_state_restore = False
        if scale <= 0:
            return
        try:
            t = QTransform()
            t.scale(scale, scale)
            self.viewer.setTransform(t)
            self.viewer.horizontalScrollBar().setValue(hscroll)
            self.viewer.verticalScrollBar().setValue(vscroll)
        except Exception:
            self.viewer.fit_to_view()

    def _capture_viewer_refresh_state(self):
        if self.viewer._pixmap_item.pixmap().isNull():
            self._pending_viewer_refresh_state = None
            return
        self._pending_viewer_refresh_state = (
            QTransform(self.viewer.transform()),
            int(self.viewer.horizontalScrollBar().value()),
            int(self.viewer.verticalScrollBar().value()),
        )

    def _restore_pending_viewer_refresh_state(self):
        if not self._pending_viewer_refresh_state:
            return
        transform, hscroll, vscroll = self._pending_viewer_refresh_state
        self._pending_viewer_refresh_state = None
        try:
            self.viewer.setTransform(transform)
            self.viewer.horizontalScrollBar().setValue(hscroll)
            self.viewer.verticalScrollBar().setValue(vscroll)
        except Exception:
            pass

    def _schedule_viewer_preview(self, stage: str | None = None):
        if stage is not None:
            self.preview_stage_preference = stage
        self._update_preview_status()
        self.preview_timer.start()

    def _apply_viewer_preview(self):
        p = self.viewer_selected_path()
        if not p or not p.exists():
            self.viewer.set_image(p)
            self._update_preview_window(None, None)
            self._update_preview_status()
            return

        source = self._load_preview_source_image(p)
        if source is None:
            self.viewer.set_image(p)
            self._restore_pending_viewer_refresh_state()
            self._update_preview_window(None, None)
            self._update_preview_status()
            return

        original_pm = self._pixmap_from_pil(source)
        self.viewer.set_pixmap(original_pm, preserve_view=True)
        self._restore_initial_viewer_state_if_needed()
        self._restore_pending_viewer_refresh_state()

        if self.preview_window is not None and self.preview_window.isVisible():
            try:
                preview = apply_adjustments(source, **self.preview_window.current_values())
                preview_pm = self._pixmap_from_pil(preview)
                self._update_preview_window(original_pm, preview_pm)
            except Exception as e:
                self.append_log(f"[WARN] Preview failed: {e}", "warn")
                self._update_preview_window(original_pm, original_pm)
        else:
            self._update_preview_window(original_pm, original_pm)

        self._update_preview_status()

    def _bind_adjustment_preview(self):
        for stage in ["input", "output"]:
            for name in ["brightness", "contrast", "saturation", "sharpness", "gamma", "highlights", "shadows"]:
                control = getattr(self, f"sp_{stage}_{name}", None)
                if control is not None and hasattr(control, "slider"):
                    control.slider.valueChanged.connect(lambda _=0, stage=stage: self._schedule_viewer_preview(stage))

    def _load_to_ui(self):
        s = self.s
        self.le_scripts_dir.setText(s.scripts_dir)
        self.le_input_root.setText(s.input_root)
        self.le_processed_root.setText(s.processed_root)
        self.le_anim_json_root.setText(s.anim_json_root)
        self.le_mod_assets_root.setText(s.mod_assets_root)
        self.le_mod_json_root.setText(s.mod_json_root)
        self.le_hex_overlay.setText(s.hex_overlay)
        self._refresh_scope_creature_choices()
        self._update_scope_hint()

        self.sp_baseline_y.setValue(s.baseline_y)
        self.sp_left_limit_x.setValue(s.left_limit_x)
        self.sp_left_padding.setValue(s.left_padding)
        self.sp_sprite_h.setValue(s.sprite_h)
        self.sp_sprite_w.setValue(getattr(s, "sprite_w", 0))
        self.cb_prefer.setCurrentText(getattr(s, "prefer", "height") if getattr(s, "prefer", "height") in ["height", "width", "none"] else "height")
        self.sp_tol.setValue(s.tol)
        self.sp_feather.setValue(s.feather)
        self.sp_shrink.setValue(s.shrink)
        self.chk_despill.setChecked(bool(s.despill))
        self.cb_key_from.setCurrentText(s.key_from if s.key_from in ["each", "first"] else "each")
        self.cb_bg_mode.setCurrentText(s.bg_mode if s.bg_mode in ["global", "border"] else "global")
        self.chk_remove_bg.setChecked(bool(getattr(s, "process_remove_bg", True)))
        self.chk_reframe.setChecked(bool(getattr(s, "process_reframe", True)))
        self.chk_force_bg_output.setChecked(bool(getattr(s, "process_force_bg_output", True)))
        self.le_force_bg_color.setText(getattr(s, "process_force_bg_color", "#FF00FF"))
        self.chk_res_1x.setChecked(bool(getattr(s, "gen_1x", True)))
        self.chk_res_2x.setChecked(bool(getattr(s, "gen_2x", False)))
        self.chk_res_3x.setChecked(bool(getattr(s, "gen_3x", False)))
        self.chk_res_4x.setChecked(bool(getattr(s, "gen_4x", False)))
        if hasattr(self, "le_canvas_bg"):
            self.le_canvas_bg.setText(getattr(s, "viewer_canvas_bg", "#404040"))
            self._apply_canvas_bg()

        self.sp_cols.setValue(s.split_cols)
        self.sp_rows.setValue(s.split_rows)
        self.chk_autocrop.setChecked(bool(s.split_autocrop))

        self._set_adjust_slider_value(self.sp_input_brightness, self._stored_adjust_to_slider("brightness", getattr(s, "input_brightness", 100)))
        self._set_adjust_slider_value(self.sp_input_contrast, self._stored_adjust_to_slider("contrast", getattr(s, "input_contrast", 100)))
        self._set_adjust_slider_value(self.sp_input_saturation, self._stored_adjust_to_slider("saturation", getattr(s, "input_saturation", 100)))
        self._set_adjust_slider_value(self.sp_input_sharpness, self._stored_adjust_to_slider("sharpness", getattr(s, "input_sharpness", 100)))
        self._set_adjust_slider_value(self.sp_input_gamma, self._stored_adjust_to_slider("gamma", getattr(s, "input_gamma", 100)))
        self._set_adjust_slider_value(self.sp_input_highlights, self._stored_adjust_to_slider("highlights", getattr(s, "input_highlights", 0)))
        self._set_adjust_slider_value(self.sp_input_shadows, self._stored_adjust_to_slider("shadows", getattr(s, "input_shadows", 0)))

        self._set_adjust_slider_value(self.sp_output_brightness, self._stored_adjust_to_slider("brightness", getattr(s, "output_brightness", 100)))
        self._set_adjust_slider_value(self.sp_output_contrast, self._stored_adjust_to_slider("contrast", getattr(s, "output_contrast", 100)))
        self._set_adjust_slider_value(self.sp_output_saturation, self._stored_adjust_to_slider("saturation", getattr(s, "output_saturation", 100)))
        self._set_adjust_slider_value(self.sp_output_sharpness, self._stored_adjust_to_slider("sharpness", getattr(s, "output_sharpness", 100)))
        self._set_adjust_slider_value(self.sp_output_gamma, self._stored_adjust_to_slider("gamma", getattr(s, "output_gamma", 100)))
        self._set_adjust_slider_value(self.sp_output_highlights, self._stored_adjust_to_slider("highlights", getattr(s, "output_highlights", 0)))
        self._set_adjust_slider_value(self.sp_output_shadows, self._stored_adjust_to_slider("shadows", getattr(s, "output_shadows", 0)))


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
        s.process_remove_bg = self.chk_remove_bg.isChecked()
        s.process_reframe = self.chk_reframe.isChecked()
        s.process_force_bg_output = self.chk_force_bg_output.isChecked()
        s.process_force_bg_color = self.le_force_bg_color.text().strip()
        s.gen_1x = self.chk_res_1x.isChecked()
        s.gen_2x = self.chk_res_2x.isChecked()
        s.gen_3x = self.chk_res_3x.isChecked()
        s.gen_4x = self.chk_res_4x.isChecked()
        if hasattr(self, "le_canvas_bg"):
            s.viewer_canvas_bg = self.le_canvas_bg.text().strip()
        try:
            s.viewer_zoom_scale = float(self.viewer.transform().m11())
            s.viewer_hscroll = int(self.viewer.horizontalScrollBar().value())
            s.viewer_vscroll = int(self.viewer.verticalScrollBar().value())
        except Exception:
            pass

        s.split_cols = self.sp_cols.value()
        s.split_rows = self.sp_rows.value()
        s.split_autocrop = self.chk_autocrop.isChecked()

        s.input_brightness = self._slider_adjust_to_stored("brightness", self._adjust_slider_value(self.sp_input_brightness))
        s.input_contrast = self._slider_adjust_to_stored("contrast", self._adjust_slider_value(self.sp_input_contrast))
        s.input_saturation = self._slider_adjust_to_stored("saturation", self._adjust_slider_value(self.sp_input_saturation))
        s.input_sharpness = self._slider_adjust_to_stored("sharpness", self._adjust_slider_value(self.sp_input_sharpness))
        s.input_gamma = self._slider_adjust_to_stored("gamma", self._adjust_slider_value(self.sp_input_gamma))
        s.input_highlights = self._slider_adjust_to_stored("highlights", self._adjust_slider_value(self.sp_input_highlights))
        s.input_shadows = self._slider_adjust_to_stored("shadows", self._adjust_slider_value(self.sp_input_shadows))

        s.output_brightness = self._slider_adjust_to_stored("brightness", self._adjust_slider_value(self.sp_output_brightness))
        s.output_contrast = self._slider_adjust_to_stored("contrast", self._adjust_slider_value(self.sp_output_contrast))
        s.output_saturation = self._slider_adjust_to_stored("saturation", self._adjust_slider_value(self.sp_output_saturation))
        s.output_sharpness = self._slider_adjust_to_stored("sharpness", self._adjust_slider_value(self.sp_output_sharpness))
        s.output_gamma = self._slider_adjust_to_stored("gamma", self._adjust_slider_value(self.sp_output_gamma))
        s.output_highlights = self._slider_adjust_to_stored("highlights", self._adjust_slider_value(self.sp_output_highlights))
        s.output_shadows = self._slider_adjust_to_stored("shadows", self._adjust_slider_value(self.sp_output_shadows))

    def steps_select_all(self):
        self.chk_split.setChecked(True)
        self.chk_adjust_input.setChecked(True)
        self.chk_process.setChecked(True)
        self.chk_adjust_output.setChecked(True)
        self.chk_json.setChecked(True)
        self.chk_deploy.setChecked(True)

    def steps_select_none(self):
        self.chk_split.setChecked(False)
        self.chk_adjust_input.setChecked(False)
        self.chk_process.setChecked(False)
        self.chk_adjust_output.setChecked(False)
        self.chk_json.setChecked(False)
        self.chk_deploy.setChecked(False)

    def refresh_ui_state(self):
        # Keep pipeline step checkboxes always interactive; validation happens on Run.
        self.chk_split.setEnabled(True)
        self.chk_adjust_input.setEnabled(True)
        self.chk_process.setEnabled(True)
        self.chk_adjust_output.setEnabled(True)
        self.chk_json.setEnabled(True)
        self.chk_deploy.setEnabled(True)

        self.btn_run.setEnabled(any([
            self.chk_split.isChecked(),
            self.chk_adjust_input.isChecked(),
            self.chk_process.isChecked(),
            self.chk_adjust_output.isChecked(),
            self.chk_json.isChecked(),
            self.chk_deploy.isChecked(),
        ]))

        creature, group = self._scope_values()
        has_creature = bool(creature)
        has_group = has_creature and (group is not None)
        for btn in [self.btn_params_load_creature, self.btn_params_save_creature, self.btn_adjust_load_creature, self.btn_adjust_save_creature]:
            btn.setEnabled(has_creature)
        for btn in [self.btn_params_load_group, self.btn_params_save_group, self.btn_adjust_load_group, self.btn_adjust_save_group]:
            btn.setEnabled(has_group)
        self.btn_scope_save_profile.setEnabled(True)

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
            # Embedded bar not present (patch mismatch) - fallback to popup so the button is never a no-op.
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
        if "adjust_frames" in base:
            return "adjust"
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
        self.log.moveCursor(QTextCursor.End)
        self.log.ensureCursorVisible()
        try:
            sb = self.log.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass
        if self.log_dialog and self.log_dialog.isVisible():
            # keep popup in sync (cheap but effective)
            self.log_dialog.refresh()

    # ---------------- actions: reset/cleanup ----------------
    def reset_paths_defaults(self):
        sd = Path(self.le_scripts_dir.text().strip() or "./scripts")
        base = sd.parent if sd.name.lower() == "scripts" else sd

        self.le_input_root.setText(str((base / "inputs").resolve()))
        self.le_processed_root.setText(str((base / "outputs").resolve()))
        self.le_anim_json_root.setText(str((base / "anim_json").resolve()))

        self.append_log("[INFO] Paths reset to defaults relative to scripts folder.", "info")
        self._refresh_scope_creature_choices()
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
        self._refresh_scope_creature_choices()
        self.viewer_refresh_all(keep_selection=True)

    def clear_outputs(self):
        processed = Path(self.le_processed_root.text().strip())
        animjson = Path(self.le_anim_json_root.text().strip())

        targets = []
        if processed.parent.exists():
            targets += [
                processed,
                processed.parent / "cleaned_alpha",
                processed.parent / "forced_bg",
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

        self.viewer_refresh_all(keep_selection=True)
        self.json_refresh_all(keep_selection=False)
        self._refresh_scope_creature_choices()

    # ---------------- scope ----------------
    def _scope_values(self):
        creature = self.le_only_creature.currentText().strip()
        group = self.cb_only_group.currentData()
        return creature, group

    def _creature_profile_path(self, creature: str) -> Path:
        return Path(self.le_input_root.text().strip()) / creature / "_pipeline_profile.json"

    def _group_profile_path(self, creature: str, group: int) -> Path:
        return Path(self.le_input_root.text().strip()) / creature / f"group{group}" / "_pipeline_profile.json"

    def _read_profile_file(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_profile_file(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _profile_scope_level(self) -> str:
        creature, group = self._scope_values()
        if creature and group is not None:
            return "group"
        if creature:
            return "creature"
        return "global"

    def _confirm_profile_save(self, section: str | None, level: str) -> bool:
        creature, group = self._scope_values()
        if level == "group":
            target = f"creature '{creature}', group {group}"
        elif level == "creature":
            target = f"creature '{creature}'"
        else:
            target = "global defaults"
        what = "both Process Frames and Image Adjustments" if section is None else section.replace("_", " ").title()
        resp = QMessageBox.question(
            self,
            "Save Profile",
            f"Save {what} to {target}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return resp == QMessageBox.Yes

    def _collect_process_profile_from_ui(self) -> dict:
        return {
            "process_remove_bg": self.chk_remove_bg.isChecked(),
            "process_reframe": self.chk_reframe.isChecked(),
            "process_force_bg_output": self.chk_force_bg_output.isChecked(),
            "process_force_bg_color": self.le_force_bg_color.text().strip() or "#FF00FF",
            "gen_1x": self.chk_res_1x.isChecked(),
            "gen_2x": self.chk_res_2x.isChecked(),
            "gen_3x": self.chk_res_3x.isChecked(),
            "gen_4x": self.chk_res_4x.isChecked(),
            "baseline_y": self.sp_baseline_y.value(),
            "left_limit_x": self.sp_left_limit_x.value(),
            "left_padding": self.sp_left_padding.value(),
            "sprite_h": self.sp_sprite_h.value(),
            "sprite_w": self.sp_sprite_w.value(),
            "prefer": self.cb_prefer.currentText(),
            "tol": self.sp_tol.value(),
            "feather": self.sp_feather.value(),
            "shrink": self.sp_shrink.value(),
            "despill": self.chk_despill.isChecked(),
            "key_from": self.cb_key_from.currentText(),
            "bg_mode": self.cb_bg_mode.currentText(),
        }

    def _apply_process_profile_to_ui(self, data: dict):
        self.chk_remove_bg.setChecked(bool(data.get("process_remove_bg", True)))
        self.chk_reframe.setChecked(bool(data.get("process_reframe", True)))
        self.chk_force_bg_output.setChecked(bool(data.get("process_force_bg_output", False)))
        self.le_force_bg_color.setText(str(data.get("process_force_bg_color", "#FF00FF")))
        self.chk_res_1x.setChecked(bool(data.get("gen_1x", True)))
        self.chk_res_2x.setChecked(bool(data.get("gen_2x", False)))
        self.chk_res_3x.setChecked(bool(data.get("gen_3x", False)))
        self.chk_res_4x.setChecked(bool(data.get("gen_4x", False)))
        self.sp_baseline_y.setValue(int(data.get("baseline_y", self.sp_baseline_y.value())))
        self.sp_left_limit_x.setValue(int(data.get("left_limit_x", self.sp_left_limit_x.value())))
        self.sp_left_padding.setValue(int(data.get("left_padding", self.sp_left_padding.value())))
        self.sp_sprite_h.setValue(int(data.get("sprite_h", self.sp_sprite_h.value())))
        self.sp_sprite_w.setValue(int(data.get("sprite_w", self.sp_sprite_w.value())))
        prefer = str(data.get("prefer", self.cb_prefer.currentText()))
        if prefer in ["height", "width", "none"]:
            self.cb_prefer.setCurrentText(prefer)
        self.sp_tol.setValue(int(data.get("tol", self.sp_tol.value())))
        self.sp_feather.setValue(int(data.get("feather", self.sp_feather.value())))
        self.sp_shrink.setValue(int(data.get("shrink", self.sp_shrink.value())))
        self.chk_despill.setChecked(bool(data.get("despill", self.chk_despill.isChecked())))
        key_from = str(data.get("key_from", self.cb_key_from.currentText()))
        if key_from in ["each", "first"]:
            self.cb_key_from.setCurrentText(key_from)
        bg_mode = str(data.get("bg_mode", self.cb_bg_mode.currentText()))
        if bg_mode in ["global", "border"]:
            self.cb_bg_mode.setCurrentText(bg_mode)
        self._ui_to_settings()
        self.refresh_ui_state()

    def _collect_adjust_profile_from_ui(self) -> dict:
        return {
            "input_brightness": self._slider_adjust_to_stored("brightness", self._adjust_slider_value(self.sp_input_brightness)),
            "input_contrast": self._slider_adjust_to_stored("contrast", self._adjust_slider_value(self.sp_input_contrast)),
            "input_saturation": self._slider_adjust_to_stored("saturation", self._adjust_slider_value(self.sp_input_saturation)),
            "input_sharpness": self._slider_adjust_to_stored("sharpness", self._adjust_slider_value(self.sp_input_sharpness)),
            "input_gamma": self._slider_adjust_to_stored("gamma", self._adjust_slider_value(self.sp_input_gamma)),
            "input_highlights": self._slider_adjust_to_stored("highlights", self._adjust_slider_value(self.sp_input_highlights)),
            "input_shadows": self._slider_adjust_to_stored("shadows", self._adjust_slider_value(self.sp_input_shadows)),
            "output_brightness": self._slider_adjust_to_stored("brightness", self._adjust_slider_value(self.sp_output_brightness)),
            "output_contrast": self._slider_adjust_to_stored("contrast", self._adjust_slider_value(self.sp_output_contrast)),
            "output_saturation": self._slider_adjust_to_stored("saturation", self._adjust_slider_value(self.sp_output_saturation)),
            "output_sharpness": self._slider_adjust_to_stored("sharpness", self._adjust_slider_value(self.sp_output_sharpness)),
            "output_gamma": self._slider_adjust_to_stored("gamma", self._adjust_slider_value(self.sp_output_gamma)),
            "output_highlights": self._slider_adjust_to_stored("highlights", self._adjust_slider_value(self.sp_output_highlights)),
            "output_shadows": self._slider_adjust_to_stored("shadows", self._adjust_slider_value(self.sp_output_shadows)),
        }

    def _apply_adjust_profile_to_ui(self, data: dict):
        for key, value in data.items():
            if hasattr(self.s, key):
                setattr(self.s, key, value)
        self._set_adjust_slider_value(self.sp_input_brightness, self._stored_adjust_to_slider("brightness", int(data.get("input_brightness", 100))))
        self._set_adjust_slider_value(self.sp_input_contrast, self._stored_adjust_to_slider("contrast", int(data.get("input_contrast", 100))))
        self._set_adjust_slider_value(self.sp_input_saturation, self._stored_adjust_to_slider("saturation", int(data.get("input_saturation", 100))))
        self._set_adjust_slider_value(self.sp_input_sharpness, self._stored_adjust_to_slider("sharpness", int(data.get("input_sharpness", 100))))
        self._set_adjust_slider_value(self.sp_input_gamma, self._stored_adjust_to_slider("gamma", int(data.get("input_gamma", 100))))
        self._set_adjust_slider_value(self.sp_input_highlights, self._stored_adjust_to_slider("highlights", int(data.get("input_highlights", 0))))
        self._set_adjust_slider_value(self.sp_input_shadows, self._stored_adjust_to_slider("shadows", int(data.get("input_shadows", 0))))
        self._set_adjust_slider_value(self.sp_output_brightness, self._stored_adjust_to_slider("brightness", int(data.get("output_brightness", 100))))
        self._set_adjust_slider_value(self.sp_output_contrast, self._stored_adjust_to_slider("contrast", int(data.get("output_contrast", 100))))
        self._set_adjust_slider_value(self.sp_output_saturation, self._stored_adjust_to_slider("saturation", int(data.get("output_saturation", 100))))
        self._set_adjust_slider_value(self.sp_output_sharpness, self._stored_adjust_to_slider("sharpness", int(data.get("output_sharpness", 100))))
        self._set_adjust_slider_value(self.sp_output_gamma, self._stored_adjust_to_slider("gamma", int(data.get("output_gamma", 100))))
        self._set_adjust_slider_value(self.sp_output_highlights, self._stored_adjust_to_slider("highlights", int(data.get("output_highlights", 0))))
        self._set_adjust_slider_value(self.sp_output_shadows, self._stored_adjust_to_slider("shadows", int(data.get("output_shadows", 0))))
        self._ui_to_settings()
        self._update_preview_status()

    def _load_profile_into_ui(self, section: str, level: str):
        creature, group = self._scope_values()
        if level == "global":
            profile = (self.s.global_profiles or {}).get(section, {})
        elif level == "creature" and creature:
            profile = self._read_profile_file(self._creature_profile_path(creature)).get(section, {})
        elif level == "group" and creature and group is not None:
            profile = self._read_profile_file(self._group_profile_path(creature, group)).get(section, {})
        else:
            return
        if not profile:
            self.append_log(f"[WARN] No {section} profile found for {level}.", "warn")
            return
        if section == "process_frames":
            self._apply_process_profile_to_ui(profile)
        else:
            self._apply_adjust_profile_to_ui(profile)
        self.append_log(f"[OK] Loaded {section} profile from {level}.", "ok")

    def _save_profile_from_ui(self, section: str, level: str):
        if not self._confirm_profile_save(section, level):
            return
        creature, group = self._scope_values()
        profile = self._collect_process_profile_from_ui() if section == "process_frames" else self._collect_adjust_profile_from_ui()
        if level == "global":
            if not self.s.global_profiles:
                self.s.global_profiles = {}
            self.s.global_profiles[section] = profile
            self._ui_to_settings()
            save_settings(self.settings_path, self.s)
            self.append_log(f"[OK] Saved {section} profile to global settings.", "ok")
            return
        if level == "creature" and creature:
            path = self._creature_profile_path(creature)
        elif level == "group" and creature and group is not None:
            path = self._group_profile_path(creature, group)
        else:
            return
        data = self._read_profile_file(path)
        data[section] = profile
        self._write_profile_file(path, data)
        self.append_log(f"[OK] Saved {section} profile to {path}.", "ok")

    def _save_scope_profile_bundle(self):
        level = self._profile_scope_level()
        if not self._confirm_profile_save(None, level):
            return
        creature, group = self._scope_values()
        process_profile = self._collect_process_profile_from_ui()
        adjust_profile = self._collect_adjust_profile_from_ui()
        if level == "global":
            if not self.s.global_profiles:
                self.s.global_profiles = {}
            self.s.global_profiles["process_frames"] = process_profile
            self.s.global_profiles["image_adjustments"] = adjust_profile
            self._ui_to_settings()
            save_settings(self.settings_path, self.s)
            self.append_log("[OK] Saved full profile bundle to global settings.", "ok")
            return
        path = self._group_profile_path(creature, group) if level == "group" else self._creature_profile_path(creature)
        data = self._read_profile_file(path)
        data["process_frames"] = process_profile
        data["image_adjustments"] = adjust_profile
        self._write_profile_file(path, data)
        self.append_log(f"[OK] Saved full profile bundle to {path}.", "ok")

    def _scope_creature_set_text(self, value: str):
        value = value.strip()
        self.le_only_creature.blockSignals(True)
        idx = self.le_only_creature.findText(value, Qt.MatchFixedString) if value else -1
        if idx >= 0:
            self.le_only_creature.setCurrentIndex(idx)
        else:
            self.le_only_creature.setCurrentIndex(-1)
            self.le_only_creature.setEditText(value)
        self.le_only_creature.blockSignals(False)
        self.refresh_ui_state()

    def _refresh_scope_creature_choices(self):
        current = self.le_only_creature.currentText().strip()
        root_text = self.le_input_root.text().strip()
        creatures = []
        if root_text:
            root = Path(root_text)
            if root.exists() and root.is_dir():
                creatures = sorted(
                    p.name for p in root.iterdir()
                    if p.is_dir() and CREATURE_ID_RE.match(p.name)
                )
        self.le_only_creature.blockSignals(True)
        self.le_only_creature.clear()
        self.le_only_creature.addItem("")
        for creature in creatures:
            self.le_only_creature.addItem(creature)
        if current:
            idx = self.le_only_creature.findText(current, Qt.MatchFixedString)
            if idx >= 0:
                self.le_only_creature.setCurrentIndex(idx)
            else:
                self.le_only_creature.setEditText(current)
        else:
            self.le_only_creature.setCurrentIndex(0)
        self.le_only_creature.blockSignals(False)

    def _use_viewer_selection_for_scope(self):
        creature = self.cb_view_creature.currentData()
        group = self.cb_view_group.currentData()
        if creature:
            self._scope_creature_set_text(str(creature))
        if group is None:
            self.cb_only_group.setCurrentIndex(0)
        else:
            idx = self.cb_only_group.findData(group)
            if idx >= 0:
                self.cb_only_group.setCurrentIndex(idx)
        self._update_scope_hint()

    def _update_scope_hint(self):
        if self.chk_split.isChecked():
            self.lb_scope_hint.setText("Scope filters existing content for most steps. With Split enabled, it also defines the destination creature/group.")
        else:
            self.lb_scope_hint.setText("Scope filters existing content for the selected pipeline steps. Empty creature means all creatures.")

    # ---------------- image viewer ----------------
    def viewer_source_root(self) -> Path | None:
        src = self.cb_view_source.currentText()
        input_root = Path(self.le_input_root.text().strip()) if is_nonempty(self.le_input_root.text()) else None
        processed_root = Path(self.le_processed_root.text().strip()) if is_nonempty(self.le_processed_root.text()) else None
        mod_assets_root = Path(self.le_mod_assets_root.text().strip()) if is_nonempty(self.le_mod_assets_root.text()) else None
        scale = int(self.cb_view_scale.currentData() or 1) if hasattr(self, "cb_view_scale") else 1

        if src.startswith("Inputs") and input_root:
            return input_root
        if src.startswith("Outputs") and processed_root:
            scale_root = processed_root / f"{scale}x"
            return scale_root if scale_root.exists() else processed_root
        if src.startswith("Deployed") and mod_assets_root:
            return self._deploy_scale_root(scale)

        if processed_root:
            parent = processed_root.parent
            if src.startswith("Previews"):
                scale_root = parent / "previews" / f"{scale}x"
                return scale_root if scale_root.exists() else (parent / "previews")
            if src.startswith("Cleaned"):
                return parent / "cleaned_alpha"
            if src.startswith("Forced"):
                return parent / "forced_bg"
        return None

    def viewer_refresh_all(self, keep_selection: bool = True):
        prev_src = self.cb_view_source.currentIndex()
        prev_cre = self.cb_view_creature.currentData()
        prev_gid = self.cb_view_group.currentData()
        prev_frame = self.cb_view_frame.currentData()

        if keep_selection:
            self._capture_viewer_refresh_state()

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
        if not keep_selection:
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
                if i == -1:
                    self.cb_view_creature.addItem(str(prev_cre), prev_cre)
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
        if not keep_selection:
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
            if ig == -1:
                self.cb_view_group.addItem(group_label(int(prev_gid)), prev_gid)
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
        if not keep_selection:
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
        else:
            self.viewer.set_image(None)
            self.preview_source_path = None
            self.preview_source_image = None

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
            self.preview_source_path = None
            self.preview_source_image = None
        else:
            self.preview_source_path = None
            self.preview_source_image = None
        self._schedule_viewer_preview()

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
            self._open_folder_path(cand.resolve())
        else:
            self.append_log(f"[Viewer] Folder not found: {folder}", "warn")

    def _open_folder_path(self, folder: Path):
        try:
            if folder.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except Exception as e:
            self.append_log(f"[WARN] Could not open folder: {folder} ({e})", "warn")

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

    def json_open_folder(self):
        root = self.json_source_root()
        if root and root.exists():
            self._open_folder_path(root.resolve())

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

        if self.chk_adjust_input.isChecked():
            Path(self.s.input_root).mkdir(parents=True, exist_ok=True)
            if not self.chk_split.isChecked() and not self._require_scope_content(self.s.input_root, "Adjust Input"):
                return False

        if self.chk_process.isChecked():
            Path(self.s.input_root).mkdir(parents=True, exist_ok=True)
            Path(self.s.processed_root).mkdir(parents=True, exist_ok=True)
            if not (
                self.chk_remove_bg.isChecked()
                or self.chk_reframe.isChecked()
                or self.chk_force_bg_output.isChecked()
            ):
                QMessageBox.critical(
                    self,
                    "Error",
                    "Process Frames requires at least one action: Remove Background, Reframe, or Force Background.",
                )
                return False
            if self.chk_reframe.isChecked() and not self._selected_process_scales():
                QMessageBox.critical(self, "Error", "Process Frames requires at least one output resolution (1x, 2x, 3x or 4x).")
                return False
            if self.chk_reframe.isChecked() and not self.chk_remove_bg.isChecked():
                cleaned_root = str(Path(self.s.processed_root).parent / "cleaned_alpha")
                if not self._scope_has_png_content(cleaned_root):
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Reframe without Remove Background requires cleaned alpha frames for the selected scope.\n\nRun Remove Background first, or select a scope that already has cleaned_alpha content.",
                    )
                    return False

        if self.chk_adjust_output.isChecked():
            selected_scales = self._selected_process_scales()
            if not selected_scales:
                QMessageBox.critical(self, "Error", "Adjust Output requires at least one selected process resolution.")
                return False
            if not self.chk_process.isChecked():
                found_any = False
                for scale in selected_scales:
                    Path(self._processed_scale_root(scale)).mkdir(parents=True, exist_ok=True)
                    if self._scope_has_png_content(self._processed_scale_root(scale)):
                        found_any = True
                if not found_any:
                    QMessageBox.warning(
                        self,
                        "Adjust Output",
                        "No PNG content was found for the selected scope in any selected processed resolution.\n\nThe 'Adjust Output' step will be aborted.",
                    )
                    return False

        if self.chk_json.isChecked():
            Path(self.s.anim_json_root).mkdir(parents=True, exist_ok=True)
            if self.chk_process.isChecked() and 1 not in self._selected_process_scales():
                QMessageBox.critical(self, "Error", "Build Json currently reads from 1x processed output, so 1x must be selected in Process Frames output resolutions.")
                return False
            if self.chk_process.isChecked() and not self.chk_reframe.isChecked():
                QMessageBox.critical(self, "Error", "Build Json currently requires Reframe to be enabled because it reads from processed output canvases.")
                return False

        if self.chk_deploy.isChecked():
            if not self.s.mod_assets_root.strip() or not self.s.mod_json_root.strip():
                QMessageBox.critical(self, "Error", "Deploy requires both Mod Assets Root and Mod Json Root.")
                return False
            if self.chk_process.isChecked() and 1 not in self._selected_process_scales():
                QMessageBox.critical(self, "Error", "Deploy currently uses 1x processed output, so 1x must be selected in Process Frames output resolutions.")
                return False
            if self.chk_process.isChecked() and not self.chk_reframe.isChecked():
                QMessageBox.critical(self, "Error", "Deploy currently requires Reframe to be enabled because it copies processed output canvases.")
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

        if self.chk_adjust_input.isChecked():
            self._append_adjust_command(cmds, s.input_root, "input")

        if self.chk_process.isChecked():
            cleaned_root = str(Path(s.processed_root).parent / "cleaned_alpha")
            forced_root = str(Path(s.processed_root).parent / "forced_bg") if self.chk_force_bg_output.isChecked() else ""

            if self.chk_remove_bg.isChecked() or self.chk_force_bg_output.isChecked():
                cmds.append(self._build_process_command(
                    s.input_root,
                    self._processed_scale_root(1),
                    scale=1,
                    remove_bg=self.chk_remove_bg.isChecked(),
                    reframe=False,
                    force_bg=False,
                    clean_root=cleaned_root if self.chk_remove_bg.isChecked() else "",
                    forced_root=forced_root,
                    preview_root="",
                ))

            if self.chk_reframe.isChecked():
                process_in_root = cleaned_root if not self.chk_remove_bg.isChecked() else cleaned_root
                for scale in self._selected_process_scales():
                    cmds.append(self._build_process_command(
                        process_in_root,
                        self._processed_scale_root(scale),
                        scale=scale,
                        remove_bg=False,
                        reframe=True,
                        force_bg=False,
                        clean_root="",
                        forced_root="",
                        preview_root=self._aux_scale_root("previews", scale),
                    ))

        if self.chk_adjust_output.isChecked():
            for scale in self._selected_process_scales():
                self._append_adjust_command(cmds, self._processed_scale_root(scale), "output")

        if self.chk_json.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "build_anim_json.py"),
                "--input_root", self._processed_scale_root(1),
                "--output_root", s.anim_json_root,
                "--basepath_prefix", "battle/",
            ]
            if creature:
                cmd += ["--only_creature", creature]
            cmds.append(cmd)

        if self.chk_deploy.isChecked():
            cmd = [
                sys.executable, script_path(s.scripts_dir, "deploy_assets.py"),
                "--in_root", self._processed_scale_root(1),
                "--out_root", s.mod_assets_root,
                "--json_in", s.anim_json_root,
                "--json_out", s.mod_json_root,
            ]
            for scale in [2, 3, 4]:
                if scale in self._selected_process_scales():
                    cmd += [f"--in_root_{scale}x", self._processed_scale_root(scale)]
            if creature:
                cmd += ["--only_creature", creature]
            if group is not None:
                cmd += ["--only_group", str(group)]
            cmds.append(cmd)

        return cmds

    def on_run(self):
        if not self.validate():
            return

        for toggle_name in ["btn_toggle_paths", "btn_toggle_params", "btn_toggle_adjustments"]:
            toggle = getattr(self, toggle_name, None)
            if toggle is not None and toggle.isChecked():
                toggle.setChecked(False)

        # Confirm risky operation: splitting without scope produces unstructured output
        if self.chk_split.isChecked() and not self.le_only_creature.currentText().strip():
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
            self._refresh_scope_creature_choices()
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







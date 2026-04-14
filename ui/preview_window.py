from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .viewer import ImageView
from .widgets import ToggleSwitch


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

        self.original_pm = None
        self.preview_pm = None
        self.show_original = False
        self.edit_stage = "input"
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


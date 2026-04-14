import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStyle,
    QToolButton,
    QVBoxLayout,
)

VALID_GROUPS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51]
GROUP_NAMES = {
    0: "(Basic)Movement",
    1: "(Basic)Mouse over",
    2: "(Basic)Idle",
    3: "(Basic)Hitted",
    4: "(Basic)Defence",
    5: "(Basic)Death",
    6: "(Basic)Death (ranged)",
    7: "(Rotation)Turn left",
    8: "(Rotation)Turn right",
    11: "(Melee)Attack (up)",
    12: "(Melee)Attack (front)",
    13: "(Melee)Attack (down)",
    14: "(Ranged)Shooting (up)",
    15: "(Ranged)Shooting (front)",
    16: "(Ranged)Shooting (down)",
    17: "(Special)Special (up)",
    18: "(Special)Special (front)",
    19: "(Special)Special (down)",
    20: "Movement start",
    21: "Movement end",
    22: "Dead",
    23: "Dead (ranged)",
    24: "Resurrection",
    30: "(Spellcast)Cast (up)",
    31: "(Spellcast)Cast (front)",
    32: "(Spellcast)Cast (down)",
    40: "(Group)Group Attack (up)",
    41: "(Group)Group Attack (front)",
    42: "(Group)Group Attack (down)",
    50: "Teleportation start",
    51: "Teleportation end",
}


def group_label(gid: int) -> str:
    return f"{gid} - {GROUP_NAMES.get(gid, 'Unknown')}"


class SplitDialog(QDialog):
    def __init__(self, parent=None, *, sheet_path: str = "", cols: int = 6, rows: int = 6,
                 autocrop: bool = True, output_root: str = "", creatures: list[str] | None = None,
                 default_creature: str = "", default_group: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Split Spritesheet")
        self.setModal(True)
        self.resize(760, 280)

        root = QVBoxLayout(self)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        root.addLayout(grid)

        self.le_sheet = QLineEdit(sheet_path)
        self.btn_browse_sheet = QPushButton("Browse...")
        self.btn_open_sheet = QToolButton()
        self.btn_open_sheet.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_open_sheet.setAutoRaise(True)

        self.sp_cols = QSpinBox()
        self.sp_cols.setRange(1, 200)
        self.sp_cols.setValue(cols)
        self.sp_rows = QSpinBox()
        self.sp_rows.setRange(1, 200)
        self.sp_rows.setValue(rows)
        self.chk_autocrop = QCheckBox("Auto Crop")
        self.chk_autocrop.setChecked(bool(autocrop))

        self.cb_creature = QComboBox()
        self.cb_creature.setEditable(True)
        self.cb_creature.setInsertPolicy(QComboBox.NoInsert)
        self.cb_creature.addItem("")
        for creature in (creatures or []):
            self.cb_creature.addItem(creature)
        if default_creature:
            idx = self.cb_creature.findText(default_creature, Qt.MatchFixedString)
            if idx >= 0:
                self.cb_creature.setCurrentIndex(idx)
            else:
                self.cb_creature.setEditText(default_creature)

        self.cb_group = QComboBox()
        self.cb_group.addItem("None", None)
        for g in VALID_GROUPS:
            self.cb_group.addItem(group_label(g), g)
        if default_group is not None:
            idx = self.cb_group.findData(default_group)
            if idx >= 0:
                self.cb_group.setCurrentIndex(idx)

        self.le_output_root = QLineEdit(output_root)
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_open_output = QToolButton()
        self.btn_open_output.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.btn_open_output.setAutoRaise(True)

        self.lb_destination = QLabel("")
        self.lb_destination.setStyleSheet("color: #4b5e77;")

        grid.addWidget(QLabel("Spritesheet"), 0, 0)
        grid.addWidget(self.le_sheet, 0, 1)
        grid.addWidget(self.btn_browse_sheet, 0, 2)
        grid.addWidget(self.btn_open_sheet, 0, 3)

        grid.addWidget(QLabel("Cols"), 1, 0)
        grid.addWidget(self.sp_cols, 1, 1)
        grid.addWidget(QLabel("Rows"), 1, 2)
        grid.addWidget(self.sp_rows, 1, 3)
        grid.addWidget(self.chk_autocrop, 2, 1, 1, 2)

        grid.addWidget(QLabel("Creature"), 3, 0)
        grid.addWidget(self.cb_creature, 3, 1, 1, 3)
        grid.addWidget(QLabel("Group"), 4, 0)
        grid.addWidget(self.cb_group, 4, 1, 1, 3)

        grid.addWidget(QLabel("Output Root"), 5, 0)
        grid.addWidget(self.le_output_root, 5, 1)
        grid.addWidget(self.btn_browse_output, 5, 2)
        grid.addWidget(self.btn_open_output, 5, 3)

        grid.addWidget(QLabel("Destination"), 6, 0)
        grid.addWidget(self.lb_destination, 6, 1, 1, 3)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_run = QPushButton("Run Split")
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_run)
        root.addLayout(btns)

        self.btn_browse_sheet.clicked.connect(self._browse_sheet)
        self.btn_open_sheet.clicked.connect(self._open_sheet_folder)
        self.btn_browse_output.clicked.connect(self._browse_output)
        self.btn_open_output.clicked.connect(self._open_output_folder)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_run.clicked.connect(self.accept)
        self.cb_creature.currentTextChanged.connect(self._update_destination)
        self.cb_group.currentIndexChanged.connect(self._update_destination)
        self.le_output_root.textChanged.connect(self._update_destination)
        self._update_destination()

    def _browse_sheet(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Spritesheet", os.getcwd(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
        )
        if f:
            self.le_sheet.setText(f)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Root", self.le_output_root.text().strip() or os.getcwd())
        if folder:
            self.le_output_root.setText(folder)

    def _open_sheet_folder(self):
        target = Path(self.le_sheet.text().strip()).parent if self.le_sheet.text().strip() else Path.cwd()
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _open_output_folder(self):
        target = Path(self.le_output_root.text().strip()) if self.le_output_root.text().strip() else Path.cwd()
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _update_destination(self):
        out_root = self.le_output_root.text().strip()
        creature = self.cb_creature.currentText().strip()
        group = self.cb_group.currentData()
        if out_root and creature and group is not None:
            self.lb_destination.setText(str(Path(out_root) / creature / f"group{group}"))
        elif out_root:
            self.lb_destination.setText(str(Path(out_root)))
        else:
            self.lb_destination.setText("-")

    def values(self) -> dict:
        return {
            "sheet_path": self.le_sheet.text().strip(),
            "cols": int(self.sp_cols.value()),
            "rows": int(self.sp_rows.value()),
            "autocrop": bool(self.chk_autocrop.isChecked()),
            "creature": self.cb_creature.currentText().strip(),
            "group": self.cb_group.currentData(),
            "output_root": self.le_output_root.text().strip(),
        }


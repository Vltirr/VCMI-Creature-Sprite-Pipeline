from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from core.groups import CREATURE_ID_RE, VALID_GROUPS, group_label


class CleanupInputDialog(QDialog):
    def __init__(self, parent=None, *, input_root: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Clean Input")
        self.input_root = Path(input_root).expanduser()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        info = QLabel(
            "Choose the input folder to clean. The selected path must stay inside the configured Input root."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.lb_root = QLabel(str(self.input_root))
        self.lb_root.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.cb_creature = QComboBox()
        self.cb_group = QComboBox()
        form.addRow("Input root", self.lb_root)
        form.addRow("Creature", self.cb_creature)
        form.addRow("Group", self.cb_group)
        layout.addLayout(form)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.cb_creature.currentIndexChanged.connect(self._refresh_groups)
        self._refresh_creatures()

    def _refresh_creatures(self):
        self.cb_creature.blockSignals(True)
        self.cb_creature.clear()
        self.cb_creature.addItem("All inputs", None)
        if self.input_root.exists() and self.input_root.is_dir():
            creatures = sorted(
                p.name for p in self.input_root.iterdir()
                if p.is_dir() and CREATURE_ID_RE.match(p.name)
            )
            for creature in creatures:
                self.cb_creature.addItem(creature, creature)
        self.cb_creature.blockSignals(False)
        self._refresh_groups()

    def _refresh_groups(self):
        creature = self.cb_creature.currentData()
        self.cb_group.clear()
        self.cb_group.addItem("All groups", None)
        self.cb_group.setEnabled(bool(creature))
        if not creature:
            return
        creature_dir = self.input_root / creature
        existing = set()
        if creature_dir.exists() and creature_dir.is_dir():
            for p in creature_dir.iterdir():
                if p.is_dir() and p.name.startswith("group"):
                    try:
                        existing.add(int(p.name.replace("group", "", 1)))
                    except ValueError:
                        pass
        for group in VALID_GROUPS:
            if group in existing:
                self.cb_group.addItem(group_label(group), group)

    def values(self) -> dict:
        creature = self.cb_creature.currentData()
        group = self.cb_group.currentData() if creature else None
        target = self.input_root
        if creature:
            target = target / creature
            if group is not None:
                target = target / f"group{group}"
        return {
            "creature": creature,
            "group": group,
            "target": target,
            "is_all_inputs": creature is None,
        }

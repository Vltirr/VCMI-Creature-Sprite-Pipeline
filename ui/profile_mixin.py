import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from core.groups import CREATURE_ID_RE, VALID_GROUPS, group_label
from core.paths import exists_file, quote_cmd, script_path
from core.profiles import creature_profile_path, group_profile_path, profile_has_section, read_profile_file, write_profile_file
from core.settings import save_settings
from ui.split_dialog import SplitDialog


class ProfileMixin:
    def _scope_values(self):
        creature = self.le_only_creature.currentText().strip()
        group = self._selected_group_value()
        return creature, group

    def _creature_profile_path(self, creature: str) -> Path:
        return creature_profile_path(self.le_input_root.text().strip(), creature)

    def _group_profile_path(self, creature: str, group: int) -> Path:
        return group_profile_path(self.le_input_root.text().strip(), creature, group)

    def _read_profile_file(self, path: Path) -> dict:
        return read_profile_file(path)

    def _profile_has_section(self, path: Path, section: str) -> bool:
        return profile_has_section(path, section)

    def _write_profile_file(self, path: Path, data: dict):
        write_profile_file(path, data)

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
            "edge_bleed_radius": self.sp_edge_bleed_radius.value(),
            "despill": self.chk_despill.isChecked(),
            "key_from": self.cb_key_from.currentText(),
            "bg_mode": self.cb_bg_mode.currentText(),
        }

    def _apply_process_profile_to_ui(self, data: dict):
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
        self.sp_edge_bleed_radius.setValue(int(data.get("edge_bleed_radius", self.sp_edge_bleed_radius.value())))
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
            self.refresh_ui_state()
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
        self.refresh_ui_state()

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

    def _scope_group_has_png(self, creature: str, group: int) -> bool:
        if not creature:
            return False
        root_text = self.le_input_root.text().strip()
        if not root_text:
            return False
        gdir = Path(root_text) / creature / f"group{group}"
        if not gdir.exists() or not gdir.is_dir():
            return False
        return any(p.is_file() and p.suffix.lower() == ".png" for p in gdir.iterdir())

    def _refresh_scope_group_choices(self, preferred_group: int | None = None, select_first_with_content: bool = False):
        creature = self.le_only_creature.currentText().strip()
        current_group = self.cb_only_group.currentData()
        self.cb_only_group.blockSignals(True)
        self.cb_only_group.clear()
        self.cb_only_group.addItem("All", None)

        first_with_content_index = -1
        for g in VALID_GROUPS:
            self.cb_only_group.addItem(group_label(g), g)
            idx = self.cb_only_group.count() - 1
            if self._scope_group_has_png(creature, g):
                font = QFont()
                font.setBold(True)
                self.cb_only_group.setItemData(idx, font, Qt.FontRole)
                if first_with_content_index == -1:
                    first_with_content_index = idx

        target_idx = 0
        wanted_group = preferred_group if preferred_group is not None else current_group
        if preferred_group is None and select_first_with_content and first_with_content_index >= 0:
            target_idx = first_with_content_index
        elif wanted_group is not None:
            idx = self.cb_only_group.findData(wanted_group)
            if idx >= 0:
                target_idx = idx
        self.cb_only_group.setCurrentIndex(target_idx)
        self.cb_only_group.blockSignals(False)
        self.refresh_ui_state()

    def _update_scope_hint(self):
        self.lb_scope_hint.setText("Scope filters existing content for the selected pipeline steps. Empty creature means all creatures.")

    def open_split_dialog(self):
        if getattr(self, "proc", None):
            QMessageBox.information(self, "Split Spritesheet", "Wait for the current process to finish before starting a split.")
            return
        creatures = []
        root_text = self.le_input_root.text().strip()
        if root_text:
            root = Path(root_text)
            if root.exists() and root.is_dir():
                creatures = sorted(
                    p.name for p in root.iterdir()
                    if p.is_dir() and CREATURE_ID_RE.match(p.name)
                )
        creature, group = self._scope_values()
        dlg = SplitDialog(
            self,
            sheet_path=getattr(self.s, "split_sheet_path", ""),
            cols=self.s.split_cols,
            rows=self.s.split_rows,
            autocrop=self.s.split_autocrop,
            output_root=self.s.input_root,
            creatures=creatures,
            default_creature=getattr(self.s, "split_target_creature", ""),
            default_group=(getattr(self.s, "split_target_group", -1) if getattr(self.s, "split_target_group", -1) >= 0 else None),
        )
        if dlg.exec() != QDialog.Accepted:
            return
        values = dlg.values()
        if not values["sheet_path"] or not exists_file(values["sheet_path"]):
            QMessageBox.critical(self, "Split Spritesheet", "The spritesheet file is missing or invalid.")
            return
        if (not values["creature"]) and (values["group"] is not None):
            QMessageBox.critical(
                self,
                "Split Spritesheet",
                "Group requires a creature. Leave both empty for flat output, or provide a creature with an optional group.",
            )
            return
        if not values["output_root"]:
            QMessageBox.critical(self, "Split Spritesheet", "Output root is required.")
            return

        self.s.split_sheet_path = values["sheet_path"]
        self.s.split_cols = values["cols"]
        self.s.split_rows = values["rows"]
        self.s.split_autocrop = values["autocrop"]
        self.s.split_target_creature = values["creature"]
        self.s.split_target_group = int(values["group"]) if values["group"] is not None else -1
        save_settings(self.settings_path, self.s)

        cmd = [
            sys.executable, script_path(self.s.scripts_dir, "slice_sheet.py"),
            values["sheet_path"],
            values["output_root"],
            "--cols", str(values["cols"]),
            "--rows", str(values["rows"]),
        ]
        if values["autocrop"]:
            cmd += ["--auto_crop", "--crop_mode", "center"]
        if values["creature"]:
            cmd += ["--creature", values["creature"]]
        if values["group"] is not None:
            cmd += ["--group", str(values["group"])]
        self._start_command_queue([cmd], "=== SPLIT START ===")

    def _start_command_queue(self, cmds: list[list[str]], start_label: str = "=== RUN START ==="):
        if not cmds:
            QMessageBox.information(self, "Nothing To Run", "No commands to run.")
            return
        try:
            if hasattr(self, "btn_toggle_log") and hasattr(self, "log_body") and (not self.log_body.isVisible()):
                self.btn_toggle_log.setChecked(True)
                if hasattr(self, "splitter"):
                    sizes = self.splitter.sizes()
                    total = max(1, sum(sizes))
                    log_h = min(180, max(120, total // 4))
                    self.splitter.setSizes([max(200, total - log_h), log_h])
        except Exception:
            pass

        self.queue = cmds
        self.append_log(start_label, "info")
        for c in cmds:
            self.append_log("> " + quote_cmd(c), "cmd")

        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._run_next()

    # ---------------- image viewer ----------------

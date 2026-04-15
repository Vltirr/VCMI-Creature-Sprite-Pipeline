from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtWidgets import QMessageBox, QSizePolicy, QSpacerItem

from core.cleanup import remove_path_safely
from core.groups import CREATURE_ID_RE
from core.paths import is_nonempty
from core.viewer_sources import deploy_scale_root, source_has_png, viewer_source_root_for_label


class ViewerJsonMixin:
    def _viewer_source_is_cleanable(self) -> bool:
        src = self.cb_view_source.currentText() if hasattr(self, "cb_view_source") else ""
        return (
            src.startswith("Outputs")
            or src.startswith("Cleaned")
            or src.startswith("Previews")
            or src.startswith("Forced")
            or src.startswith("Deployed")
        )

    def _viewer_source_is_all_generated(self) -> bool:
        return hasattr(self, "cb_view_source") and self.cb_view_source.currentText().strip() == ""

    def _viewer_source_description(self, *, all_resolutions: bool = False) -> str:
        src = self.cb_view_source.currentText().strip() if hasattr(self, "cb_view_source") else ""
        scale = self.cb_view_scale.currentData() if hasattr(self, "cb_view_scale") else None
        if not src:
            return "all generated outputs"
        if all_resolutions and (src.startswith("Outputs") or src.startswith("Previews") or src.startswith("Deployed")):
            return src
        if src.startswith("Outputs") and scale:
            return f"Outputs {scale}x"
        if src.startswith("Previews") and scale:
            return f"Previews {scale}x"
        if src.startswith("Deployed") and scale:
            return f"Deployed {scale}x"
        return src

    def _all_generated_cleanup_roots(self) -> list[Path]:
        processed = Path(self.le_processed_root.text().strip())
        parent = processed.parent
        roots = [processed / f"{scale}x" for scale in [1, 2, 3, 4]]
        roots.append(processed)
        roots.extend(parent / "previews" / f"{scale}x" for scale in [1, 2, 3, 4])
        roots.extend([parent / "previews", parent / "cleaned_alpha", parent / "forced_bg"])
        unique: list[Path] = []
        seen = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                unique.append(root)
                seen.add(key)
        return unique

    def _viewer_source_scale_roots(self, src: str) -> list[Path]:
        processed = Path(self.le_processed_root.text().strip())
        parent = processed.parent
        roots: list[Path] = []
        if src.startswith("Outputs"):
            roots = [processed / f"{scale}x" for scale in [1, 2, 3, 4]]
            roots.append(processed)
        elif src.startswith("Previews"):
            roots = [parent / "previews" / f"{scale}x" for scale in [1, 2, 3, 4]]
            roots.append(parent / "previews")
        elif src.startswith("Deployed"):
            for scale in [1, 2, 3, 4]:
                root = deploy_scale_root(self.le_mod_assets_root.text().strip(), scale)
                if root:
                    roots.append(root)
        else:
            root = self.viewer_source_root()
            if root:
                roots = [root]
        unique: list[Path] = []
        seen = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                unique.append(root)
                seen.add(key)
        return unique

    def _viewer_source_root_for_label(self, src: str) -> Path | None:
        scale = int(self.cb_view_scale.currentData() or 1) if hasattr(self, "cb_view_scale") else 1
        return viewer_source_root_for_label(
            src,
            input_root=self.le_input_root.text().strip(),
            processed_root=self.le_processed_root.text().strip(),
            mod_assets_root=self.le_mod_assets_root.text().strip(),
            scale=scale,
        )

    def _viewer_source_root_for_label_at_scale(self, src: str, scale: int) -> Path | None:
        return viewer_source_root_for_label(
            src,
            input_root=self.le_input_root.text().strip(),
            processed_root=self.le_processed_root.text().strip(),
            mod_assets_root=self.le_mod_assets_root.text().strip(),
            scale=scale,
        )

    def viewer_source_root(self) -> Path | None:
        return self._viewer_source_root_for_label(self.cb_view_source.currentText())

    def _viewer_source_has_png(self, src: str) -> bool:
        if not src.strip():
            return False
        root = self._viewer_source_root_for_label(src)
        creature, gid = self._scope_values()
        return source_has_png(root, creature, gid)

    def _refresh_view_source_choices(self):
        if not hasattr(self, "cb_view_source"):
            return
        for idx in range(self.cb_view_source.count()):
            text = self.cb_view_source.itemText(idx)
            font = QFont()
            font.setBold(self._viewer_source_has_png(text))
            self.cb_view_source.setItemData(idx, font, Qt.FontRole)

    def _refresh_view_scale_choices(self):
        if not hasattr(self, "cb_view_scale"):
            return
        src = self.cb_view_source.currentText() if hasattr(self, "cb_view_source") else ""
        creature, gid = self._scope_values()
        for idx in range(self.cb_view_scale.count()):
            scale = self.cb_view_scale.itemData(idx)
            font = QFont()
            has_png = False
            try:
                root = self._viewer_source_root_for_label_at_scale(src, int(scale))
                has_png = source_has_png(root, creature, gid)
            except Exception:
                has_png = False
            font.setBold(has_png)
            self.cb_view_scale.setItemData(idx, font, Qt.FontRole)

    def viewer_refresh_all(self, keep_selection: bool = True):
        prev_src = self.cb_view_source.currentIndex()
        prev_frame = self.cb_view_frame.currentData()

        if keep_selection:
            self._capture_viewer_refresh_state()

        root = self.viewer_source_root()
        creature, gid = self._scope_values()

        self.cb_view_frame.blockSignals(True)

        self.cb_view_frame.clear()
        self.cb_view_frame.addItem("(Select)", None)
        self.viewer_stop_anim()
        if not keep_selection:
            self.viewer.set_image(None)
        self.cb_view_frame.blockSignals(False)

        self.cb_view_source.setCurrentIndex(prev_src)
        self._refresh_view_source_choices()
        self._refresh_view_scale_choices()
        if root and creature and gid is not None:
            gdir = root / creature / f"group{gid}"
            if gdir.exists():
                frames = sorted([p.name for p in gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"])
                self.cb_view_frame.blockSignals(True)
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
            self._refresh_cleanup_buttons()

    def viewer_selected_path(self) -> Path | None:
        root = self.viewer_source_root()
        creature, gid = self._scope_values()
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
        self._refresh_cleanup_buttons()
        self._schedule_viewer_preview()

    def _viewer_selection_target_for_root(self, root: Path) -> Path | None:
        creature, gid = self._scope_values()
        if not creature:
            return None
        if gid is not None:
            return root / creature / f"group{gid}"
        return root / creature

    def _viewer_selection_targets(self) -> list[tuple[Path, Path]]:
        _, gid = self._scope_values()
        if self._viewer_source_is_all_generated() or gid is None:
            targets: list[tuple[Path, Path]] = []
            for root in self._all_generated_cleanup_roots():
                target = self._viewer_selection_target_for_root(root)
                if target and target.exists():
                    targets.append((root, target))
            return targets

        root = self.viewer_source_root()
        if not root:
            return []
        src = self.cb_view_source.currentText().strip() if hasattr(self, "cb_view_source") else ""
        roots = self._viewer_source_scale_roots(src)
        targets: list[tuple[Path, Path]] = []
        for root in roots:
            target = self._viewer_selection_target_for_root(root)
            if target and target.exists():
                targets.append((root, target))
        return targets

    def _refresh_cleanup_buttons(self):
        if not hasattr(self, "btn_clean_frame"):
            return
        cleanable = self._viewer_source_is_cleanable()
        all_generated = self._viewer_source_is_all_generated()
        _, gid = self._scope_values()
        selected_path = self.viewer_selected_path()
        selection_targets = self._viewer_selection_targets()
        self.btn_clean_frame.setEnabled(bool(cleanable and selected_path and selected_path.exists() and selected_path.is_file()))
        self.btn_clean_selection.setEnabled(bool((cleanable or all_generated or gid is None) and selection_targets))

    def _target_summary_text(self, targets: list[tuple[Path, Path]]) -> str:
        src = self.cb_view_source.currentText().strip() if hasattr(self, "cb_view_source") else ""
        creature, gid = self._scope_values()
        if not targets:
            return ""
        suffix = creature
        if creature and gid is not None:
            suffix = f"{creature}\\group{gid}"

        processed = Path(self.le_processed_root.text().strip())
        parent = processed.parent
        if self._viewer_source_is_all_generated() or gid is None:
            lines = []
            previews_root = parent / "previews"
            if any(str(target).startswith(str(processed)) for _, target in targets):
                lines.append(str(processed / "<all-resolutions>" / suffix))
            if any(str(target).startswith(str(previews_root)) for _, target in targets):
                lines.append(str(previews_root / "<all-resolutions>" / suffix))
            if any("cleaned_alpha" in target.parts for _, target in targets):
                lines.append(str(parent / "cleaned_alpha" / suffix))
            if any("forced_bg" in target.parts for _, target in targets):
                lines.append(str(parent / "forced_bg" / suffix))
            return "\n".join(lines)
        if src.startswith("Outputs"):
            return str(processed / "<all-resolutions>" / suffix)
        if src.startswith("Previews"):
            return str(parent / "previews" / "<all-resolutions>" / suffix)
        if src.startswith("Deployed"):
            return "<deployed resolution root>\\" + suffix
        return "\n".join(str(target) for _, target in targets)

    def _confirm_delete_html(self, title: str, main_html: str, target_text: Path | str) -> bool:
        target_html = "<br>".join(escape(line) for line in str(target_text).splitlines() if line)
        target_html = target_html.replace("&lt;all-resolutions&gt;", "<i>&lt;all-resolutions&gt;</i>")
        text = (
            f"{main_html}<br><br>"
            f"Delete:<br><code>{target_html}</code><br><br>"
            "This cannot be undone."
        )
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Question)
        box.setTextFormat(Qt.RichText)
        box.setText(text)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setMinimumWidth(720)
        layout = box.layout()
        if layout is not None:
            layout.addItem(QSpacerItem(680, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), layout.rowCount(), 0, 1, layout.columnCount())
        resp = box.exec()
        return resp == QMessageBox.Yes

    def _confirm_delete_path(self, title: str, target: Path | str, extra: str = "") -> bool:
        return self._confirm_delete_html(title, escape(extra), target)

    def clean_viewer_frame(self):
        if not self._viewer_source_is_cleanable():
            return
        root = self.viewer_source_root()
        target = self.viewer_selected_path()
        if not (root and target and target.exists() and target.is_file()):
            QMessageBox.information(self, "Clean Frame", "No generated frame is currently visible.")
            self._refresh_cleanup_buttons()
            return
        source_text = self._viewer_source_description()
        frame_name = target.name
        creature, gid = self._scope_values()
        group_html = f", <b>group {gid}</b>" if gid is not None else ""
        main_html = (
            f"This will delete only the visible <b>{escape(source_text)}</b> frame "
            f"<b>{escape(frame_name)}</b> for creature <b>{escape(creature)}</b>{group_html}."
        )
        if not self._confirm_delete_html("Clean Frame", main_html, target):
            return
        try:
            result = remove_path_safely(target, root)
            self.append_log(f"[OK] Cleaned frame: {target} ({result.files} file removed)", "ok")
        except Exception as e:
            QMessageBox.critical(self, "Clean Frame", str(e))
            self.append_log(f"[ERROR] Clean Frame failed: {e}", "error")
            return
        self.viewer_refresh_all(keep_selection=True)
        self.json_refresh_all(keep_selection=True)
        self._refresh_scope_creature_choices()
        self._refresh_scope_group_choices(select_first_with_content=True)

    def clean_viewer_selection(self):
        creature, gid = self._scope_values()
        if not (self._viewer_source_is_cleanable() or self._viewer_source_is_all_generated() or gid is None):
            return
        targets = self._viewer_selection_targets()
        if not creature:
            QMessageBox.information(self, "Clean Selection", "Select a creature first.")
            self._refresh_cleanup_buttons()
            return
        if not targets:
            QMessageBox.information(self, "Clean Selection", "Nothing to clean for the current source and scope.")
            self._refresh_cleanup_buttons()
            return
        source_text = (
            "all generated outputs"
            if gid is None
            else self._viewer_source_description(all_resolutions=bool(len(targets) > 1))
        )
        target_text = self._target_summary_text(targets)
        group_html = f", <b>group {gid}</b>" if gid is not None else ""
        main_html = (
            f"This will delete <b>{escape(source_text)}</b> for creature "
            f"<b>{escape(creature)}</b>{group_html}."
        )
        if not self._confirm_delete_html("Clean Selection", main_html, target_text):
            return
        total_files = 0
        total_folders = 0
        try:
            for root, target in targets:
                result = remove_path_safely(target, root)
                total_files += result.files
                total_folders += result.folders
                self.append_log(f"[OK] Cleaned selection: {target} ({result.files} files, {result.folders} folders removed)", "ok")
        except Exception as e:
            QMessageBox.critical(self, "Clean Selection", str(e))
            self.append_log(f"[ERROR] Clean Selection failed: {e}", "error")
            return
        scope_text = f"creature '{creature}'"
        if gid is not None:
            scope_text += f", group {gid}"
        self.append_log(f"[OK] Cleaned {source_text} for {scope_text}: {total_files} files, {total_folders} folders removed.", "ok")
        self.viewer_refresh_all(keep_selection=True)
        self.json_refresh_all(keep_selection=True)
        self._refresh_scope_creature_choices()
        self._refresh_scope_group_choices(select_first_with_content=True)

    def viewer_open_folder(self):
        root = self.viewer_source_root()
        if not root:
            return

        creature, gid = self._scope_values()

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


from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices

from core.groups import CREATURE_ID_RE
from core.paths import is_nonempty
from core.viewer_sources import source_has_png, viewer_source_root_for_label


class ViewerJsonMixin:
    def _viewer_source_root_for_label(self, src: str) -> Path | None:
        scale = int(self.cb_view_scale.currentData() or 1) if hasattr(self, "cb_view_scale") else 1
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
        self._schedule_viewer_preview()

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


# Developer Notes

This document tracks architecture decisions and future work. It should not duplicate user-facing documentation from `README.md`, `docs/PIPELINE.md`, or `docs/SCRIPTS.md`.

## Current Architecture

- `vcmi_creature_sprite_pipeline.py` is the GUI entrypoint.
- `ui/` contains PySide UI code.
- `ui/main_window.py` still owns the main window shell, signal wiring, process queue lifecycle, and several panel-building methods.
- `ui/profile_mixin.py` owns scope/profile/split-related UI behavior.
- `ui/viewer_mixin.py` owns image and JSON viewer behavior.
- `ui/viewer.py`, `ui/preview_window.py`, `ui/split_dialog.py`, `ui/log_dialog.py`, and `ui/widgets.py` contain reusable UI pieces.
- `core/` contains non-UI helpers for settings, paths, profiles, groups, viewer source resolution, command construction, and image adjustments.
- CLI scripts in `scripts/` are still usable standalone and are called by the GUI.

## Current Workflow Decisions

- `Scope` is the single creature/group selector for both pipeline filtering and viewer browsing.
- The scope creature control is an editable combo box populated from `workspace/inputs/`.
- Split spritesheet import is a separate dialog, not a pipeline checkbox.
- `Save Profile` stores both Process Frames and Image Adjustments at the active scope level.
- Profile loading is explicit; changing scope does not automatically load profiles.
- Global defaults are stored in `settings.json`.
- Current working values are also persisted in `settings.json`.
- Creature profiles are stored in `workspace/inputs/<creature_id>/_pipeline_profile.json`.
- Group profiles are stored in `workspace/inputs/<creature_id>/groupN/_pipeline_profile.json`.
- Process Frames operation toggles are session/run choices and are not saved to or loaded from global, creature, or group profiles.
- `Image Adjustments` in the main window is a compact summary, not the primary editor.
- The external preview editor is the main live image-editing surface.
- The preview editor opens in `Single` mode by default.
- The main viewer should remain a stable browsing surface for the selected source/frame.
- Viewer `Source` entries are shown in bold when that source has PNGs for the current scope.
- Viewer `Clean Frame` deletes only the currently visible generated PNG.
- Viewer `Clean Selection` deletes generated content for the selected scope.
- With a creature and group selected, `Clean Selection` can target the current cleanable source (`Outputs`, `Previews`, `Cleaned Alpha`, `Forced Background`, or `Deployed`).
- With the viewer source left empty, `Clean Selection` targets all generated workspace roots for the selected creature or creature/group, excluding deployed mod folders.
- With scope group set to `All`, `Clean Selection` targets all generated workspace roots for the selected creature and ignores the viewer source.
- `Clean Input...` uses a separate protected dialog and validates that the target remains inside the configured Input root.
- Global `Clear Outputs` remains available for clearing all generated workspace outputs and generated animation JSON.
- `Remove Background` includes optional edge color bleed controlled by radius (`0 = off`).
- Multi-resolution processing currently supports `1x`, `2x`, `3x`, and `4x`.
- Processed outputs live under `workspace/outputs/<scale>x/...`.
- Previews live under `workspace/previews/<scale>x/...`.
- `workspace/cleaned_alpha/...` and `workspace/forced_bg/...` are shared helper roots across resolutions.

## Documentation Conventions

- `README.md` should stay focused on quick start, high-level workflow, and repository layout.
- `docs/PIPELINE.md` should describe pipeline flow, folder conventions, and GUI behavior.
- `docs/SCRIPTS.md` should stay focused on standalone CLI usage only.
- `docs/DEV_NOTES.md` should track architecture decisions, implementation order, and future work.
- Internal helper modules such as `core/image_adjustments.py` do not need standalone user-facing docs unless they become public entry points.
- Update documentation in the same branch as each behavior or architecture change.

## Next Implementation Roadmap

### 1) Protect canonical input and output roots

Goal:
- prevent image-adjustment steps from overwriting canonical roots that later stages depend on.

Current concern:
- `Adjust Input` can overwrite `workspace/inputs`.
- `Adjust Output` can overwrite `workspace/outputs/<scale>x`.
- This makes retries and source-of-truth reasoning harder.

Future direction:
- keep `workspace/inputs/` as immutable source frames.
- add a dedicated post-input-adjustment root.
- add a dedicated raw process output root before output adjustments.
- make preview behavior explicit so users know whether they are viewing canonical input, adjusted input, raw processed output, or final adjusted output.
- deploy should prefer final adjusted output, or fall back to raw processed output if adjusted output does not exist.

Implementation notes:
- keep command construction in `core/process_commands.py`.
- keep path/profile helpers in `core/`.
- keep UI choices and confirmations in `ui/`.
- decide names carefully before implementation to avoid another confusing folder migration.

### 2) Improve difficult background-removal cases

Goal:
- handle cases where floor shadows or low-contrast ground remnants survive chroma cleanup.

Investigation paths:
- tune edge color bleed behavior.
- add an optional mask cleanup pass.
- add an optional shadow/floor suppression pass.
- review whether current shrink/feather/despill ordering is ideal for these cases.

Constraint:
- avoid making default background removal more destructive.
- prefer optional controls that can be enabled for difficult sprites.

### 3) Continue evolving `process_frames.py`

Goal:
- reduce the internal size and coupling of `process_frames.py` while keeping CLI compatibility.

Candidate splits:
- frame discovery
- background removal
- edge color bleed
- reframing/alignment
- forced background generation
- preview generation
- operation orchestration

Preferred approach:
- extract reusable pure functions first.
- keep the existing CLI arguments stable.
- add focused tests around extracted behavior where practical.

### 4) Continue splitting `ui/main_window.py`

Goal:
- reduce merge conflicts and lower the blast radius of UI changes.

Candidate splits:
- paths panel
- pipeline steps panel
- process options panel
- image adjustments panel
- run queue/controller
- log panel wiring

Preferred approach:
- keep each split behavior-neutral.
- avoid UI redesign while moving code.
- verify with `py_compile` and a GUI smoke test after each split.

## Later Backlog

### Preview and viewer polish

- continue refining preview toolbar density and control placement.
- keep preview actions close to the image rather than at the bottom of the window.
- preserve zoom and scroll state reliably between sessions.
- continue polishing multi-resolution browsing so scale selection stays obvious but low-noise.

### Scope model reconsideration

- current scope works as the unified selector for viewer and pipeline.
- later, evaluate whether split import needs its own destination model separate from processing/viewer scope.

### Tests

High-value areas:
- JSON generation with group-prefixed frames (`groupN/frame.png`)
- deploy merging groups from incoming JSON
- process resize preference (`sprite_h` vs `sprite_w` / `prefer`)
- profile save/load behavior by global, creature, and group
- command construction for selected scope and selected resolutions

### Packaging

- PyInstaller Windows build.
- real `.ico` application icon.

### Execution model

- consider moving from `QProcess` to `QThread` or `QRunnable` only after more pipeline operations are callable as Python functions.

## Risks To Keep In Mind

- folder semantics can become confusing quickly if raw, adjusted, helper, and deployable outputs are not named carefully.
- cleanup actions must be scoped and confirmed to avoid accidental data loss.
- exposing independently runnable stages in the GUI needs careful UX so users understand the active operation combination.
- large UI changes should be split into small branches to reduce merge conflicts.

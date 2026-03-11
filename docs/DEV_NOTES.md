# Developer notes

## Current architecture

- `app.py` runs a PySide6 GUI that orchestrates the pipeline.
- Scripts are still usable standalone (CLI) and are called by the GUI.

## Recommended future refactor (roadmap)

1) Split the monolithic GUI into modules:
- `ui/main_window.py`
- `ui/viewer.py`
- `ui/logging.py`
- `ui/settings.py`
- `runner/queue.py`
- `runner/commands.py`

2) Move scripts to a **core + CLI wrapper** structure:
- `pipeline/` package with core functions
- keep existing `*.py` scripts as CLI wrappers that call the core

3) Execution model:
- consider moving from `QProcess` to `QThread/QRunnable` once the pipeline is callable as Python functions

4) Tests (high value, low effort):
- JSON: group-prefixed frames (`groupN/frame.png`)
- Deploy: merging groups from incoming JSON
- Process: resize preference (`sprite_h` vs `sprite_w` / `prefer`)

5) Packaging:
- PyInstaller (Windows)
- real `.ico` application icon

## Current UI direction

Recent UI decisions worth preserving:
- `Image Adjustments` in the main window is now a compact read-only summary, not the primary editor.
- The real image-editing workflow lives in the external preview editor window.
- The main viewer should remain a stable browsing surface that shows the original selected frame.
- The preview editor is the only place that should show live adjusted imagery.

## Near-term UX backlog

1) Preview window comparison mode:
- add an optional persistent original-versus-adjusted comparison mode
- likely side-by-side rather than a wipe slider

2) Preview window polish:
- continue refining toolbar density and control placement
- keep preview actions close to the image rather than at the bottom of the window

3) Main window adjustments summary:
- keep the compact `Input stage` / `Output stage` summary layout
- avoid reintroducing full sliders into the main window unless there is a very strong reason

4) Viewer ergonomics:
- preserve zoom and scroll state reliably between sessions
- keep the preview-launch entry point near the viewer tabs without interfering with canvas interaction

## Documentation conventions

- `docs/SCRIPTS.md` should stay focused on standalone CLI usage only.
- `docs/PIPELINE.md` should describe the pipeline flow, folder conventions, and GUI behavior.
- Internal helper modules such as `image_adjustments.py` do not need standalone user-facing docs unless they become public entry points.

## Next pipeline evolution

### 1) Multi-resolution output pipeline

Goal:
- support VCMI asset generation for `1x`, `2x`, `3x`, and `4x`
- treat `4x` as the master working resolution
- generate lower resolutions from the same run when desired
- allow regenerating `3x`, `2x`, and `1x` from an already edited `4x` baseline

Design direction:
- separate the concept of a master resolution from derived resolutions
- keep folder conventions explicit enough that inputs, processed masters, and derived outputs do not become ambiguous
- avoid a layout where multiple resolutions are mixed together without a clear naming or directory strategy

### 2) Independently runnable process stages

Goal:
- make `process_frames` operations runnable independently instead of only as one monolithic step

Candidate operations:
- chroma removal
- resize / scale
- alignment / reframing into target canvas
- forced solid background generation

Design direction:
- the GUI should be able to compose these operations as needed
- this is especially important for a `4x`-master workflow where edited frames may need only partial regeneration afterwards
- longer term, this likely argues for splitting `process_frames.py` into reusable core operations with a thin orchestration layer on top

### 3) Hierarchical settings

Goal:
- stop relying only on global defaults for `process_frames` and image adjustments
- allow settings to vary by creature and animation group

Preferred model:
- global defaults
- per-creature overrides
- per-group overrides
- optional per-resolution overrides later if the multi-resolution workflow requires them

Why this matters:
- different creatures often need different baselines, paddings, and cleanup settings
- different animation groups may need different offsets or treatment
- multi-resolution processing will make fixed global settings even less practical

### Suggested implementation order

1. Define the multi-resolution workflow and folder model first.
2. Refactor process stages so they can run independently.
3. Add hierarchical settings once the real processing model is clear.

### Risks to keep in mind

- mixing multiple resolutions in the same roots without a strong convention will make viewer, deploy, and JSON generation harder to reason about
- exposing independently runnable stages in the GUI will need careful UX so the active combination of operations stays understandable


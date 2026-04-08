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

1) Preview window polish:
- continue refining toolbar density and control placement
- keep preview actions close to the image rather than at the bottom of the window
- keep the `Single` / `Compare` mode selector visually obvious and low-friction

2) Main window adjustments summary:
- keep the compact `Input stage` / `Output stage` summary layout
- avoid reintroducing full sliders into the main window unless there is a very strong reason

3) Viewer ergonomics:
- preserve zoom and scroll state reliably between sessions
- keep the preview-launch entry point near the viewer tabs without interfering with canvas interaction
- continue polishing multi-resolution browsing so scale selection stays obvious but low-noise

4) Scope and selection UX:
- current status:
  - `Scope` is now the single creature/group selector for both pipeline filtering and viewer browsing
  - the scope creature control is now an editable combo box populated from `inputs`
  - `Save Profile` stores both Process Frames and Image Adjustments at the active scope level
- later option to evaluate:
  - split the current scope into:
    - a dedicated split destination selector
    - a separate processing/filter scope for the rest of the pipeline

5) Image adjustment value transfer:
- current status:
  - the main window now provides compact arrow actions between `Input stage` and `Output stage`
  - supported actions:
    - copy input adjustments to output
    - copy output adjustments to input
    - swap both adjustment sets

6) Background cleanup quality:
- current status:
  - `Remove Background` now includes an optional `edge color bleed` pass controlled by radius (`0 = off`)
  - it runs after chroma cleanup / despill / shrink and before reframe
- likely future refinement:
  - keep tuning aggressiveness and neighborhood selection based on real sprite cases

7) Protect canonical input/output roots from image-adjustment writes:
- current concern:
  - `Adjust Input` and `Adjust Output` can overwrite the same roots later stages depend on
  - this makes it harder to reason about source-of-truth imagery and to retry later steps safely
- future direction:
  - keep `inputs/` as immutable source frames
  - add a dedicated post-input-adjustment root so input previews and later steps do not modify canonical inputs
  - add a dedicated pre-output-adjustment root so `process_frames` output exists separately from the final adjusted output root
  - make preview behavior explicit:
    - input preview should operate from the canonical input-side source chosen by the final design
    - output preview should always operate from the pre-output-adjustment process result
  - deploy should prefer the final adjusted output root, or fall back to the raw process output root if no adjusted output exists
- naming of these new roots should be decided carefully before implementation to avoid another round of confusing folder semantics

8) Refactor `app.py` into smaller modules:
- `app.py` now contains too much UI, viewer, dialog, settings, and pipeline orchestration logic in one file
- risks of keeping it monolithic:
  - harder to understand and modify safely
  - localized changes have broader regression risk
  - merge conflicts become more likely when multiple branches touch unrelated UI areas
- preferred future split:
  - main window shell / layout wiring
  - viewer logic
  - preview window
  - split dialog
  - settings/profile persistence helpers
  - pipeline command building / orchestration

6) Open-folder shortcuts:
- current status:
  - `Open Folder` actions now exist in the main `Paths` area
  - `Open Folder` is available in the JSON tab/panel
  - the existing viewer `Open Folder` action remains in place

7) Profile persistence:
- current status:
  - global defaults are stored in `settings.json`
  - current working values are also persisted in `settings.json`
  - creature profiles are stored in `inputs/<creature_id>/_pipeline_profile.json`
  - group profiles are stored in `inputs/<creature_id>/groupN/_pipeline_profile.json`
  - loading is explicit; changing scope does not auto-load profiles

## Documentation conventions

- `docs/SCRIPTS.md` should stay focused on standalone CLI usage only.
- `docs/PIPELINE.md` should describe the pipeline flow, folder conventions, and GUI behavior.
- Internal helper modules such as `image_adjustments.py` do not need standalone user-facing docs unless they become public entry points.

## Next pipeline evolution

### 1) Multi-resolution output pipeline

Goal:
- support VCMI asset generation for `1x`, `2x`, `3x`, and `4x`
- allow the GUI to orchestrate whichever output scales are selected
- keep folder conventions explicit enough that multi-resolution outputs stay easy to reason about

Current implementation status:
- the GUI can already generate `1x`, `2x`, `3x`, and `4x` processed outputs by orchestrating repeated calls to `scripts/process_frames.py`
- processed outputs are stored under `outputs/<scale>x/...`
- previews are stored under `previews/<scale>x/...`
- cleaned and forced helper outputs are intentionally shared across resolutions as `cleaned_alpha/...` and `forced_bg/...`
- JSON build and deploy currently treat `1x` as the primary source, while deploy can also copy `2x/3x/4x` assets into `sprites2x/3x/4x`

### 2) Independently runnable process stages

Goal:
- make `process_frames` operations runnable independently instead of only as one monolithic step

Current GUI-aligned operations:
- background removal
- reframing into explicit canvases
- forced background helper generation

Design direction:
- the GUI should be able to compose these operations as needed
- helper outputs should stay clearly separate from main processed outputs
- longer term, this still argues for splitting `process_frames.py` into reusable core operations with a thin orchestration layer on top

Deferred follow-up:
- continue decoupling the internal `process_frames.py` implementation into smaller reusable units such as frame discovery, background removal, reframing, forced background generation, and preview generation

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

### 4) Resolution-specific overrides

Goal:
- keep the current simple `1x`-driven UI as the default
- allow later overrides for selected parameters per resolution when needed

Design direction:
- keep the scaling/orchestration logic in the GUI layer
- let the script continue to execute only the explicit numeric parameters it receives
- add per-resolution overrides only after the base hierarchical settings model is in place

### Suggested implementation order

1. Define the multi-resolution workflow and folder model first.
2. Refactor process stages so they can run independently.
3. Add hierarchical settings once the real processing model is clear.

### Risks to keep in mind

- mixing multiple resolutions in the same roots without a strong convention will make viewer, deploy, and JSON generation harder to reason about
- exposing independently runnable stages in the GUI will need careful UX so the active combination of operations stays understandable


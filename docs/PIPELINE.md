# Pipeline overview

This project converts spritesheets or loose frames into:

- processed creature frames in one or more resolutions (`1x`, `2x`, `3x`, `4x`)
- per-creature animation JSON (`creature_id.json`)
- incremental deploy into a VCMI mod folder (assets + merged JSON)

## Folder conventions

> `creature_id` refers to the creature folder name (an identifier), e.g. `goblin_darter`.

Working roots are configurable in the GUI and/or via CLI.

Expected layout under any root:

```text
<root>/
  goblin_darter/
    group0/
      frame_000.png
      frame_001.png
  lizard_archer/
    group2/
      frame_000.png
```

The GUI viewer assumes this convention for browsing.

## Steps

### Split spritesheet (optional import tool)
`scripts/slice_sheet.py` cuts a grid spritesheet into frames.

- Structured mode: with `--creature <creature_id>` and `--group N`, writes into `out_root/creature_id/groupN/`
- Creature-only mode: with `--creature <creature_id>` only, writes into `out_root/creature_id/`
- Quick mode: if no `--creature/--group` are provided, writes directly into `out_root/`
- In the GUI this is opened from `Split Spritesheet...` and is no longer part of the main pipeline step checklist

### 1) Adjust input (optional)
`scripts/adjust_frames.py` can run on `workspace/inputs` before `scripts/process_frames.py`.

- Reads `workspace/inputs/<creature_id>/groupN/*.png`
- Writes the same folder structure to the selected output root
- In the GUI, `Adjust Input` is an independent step and does not require `Process Frames`
- The GUI offers live preview in a dedicated preview editor window using the currently selected viewer frame before writing files

### 2) Process frames
`scripts/process_frames.py` reads frames and outputs aligned sprites for one requested target canvas.

Key operations:
- chroma key removal (`tol`, `feather`, `shrink`, `bg_mode`, `key_from`, `despill`, optional `edge bleed`)
- scaling (keeps aspect ratio by default; optional small distortion via `prefer=none`)
- alignment/anchoring into the requested canvas using baseline/left-limit parameters
- optional preview overlay alpha (`overlay_alpha`) for the preview PNGs

The GUI currently orchestrates multi-resolution processing by calling `scripts/process_frames.py` multiple times, once per selected resolution:
- `workspace/outputs/1x/...`
- `workspace/outputs/2x/...`
- `workspace/outputs/3x/...`
- `workspace/outputs/4x/...`

Auxiliary outputs:
- `workspace/previews/<scale>x/...` remain separated by resolution
- `workspace/cleaned_alpha/...` and `workspace/forced_bg/...` are shared because they represent helper/base imagery regardless of final target scale

GUI-facing process operations:
- `Remove Background` runs chroma/key cleanup and can emit `workspace/cleaned_alpha/...`
- `Edge Bleed` is an optional final cleanup pass inside `Remove Background`; it recolors contaminated edge pixels using nearby interior sprite color while preserving alpha
- `Reframe` resizes, aligns, and writes main processed outputs under `workspace/outputs/<scale>x/...`
- when `Reframe` runs without `Remove Background` in the same execution, the GUI reuses the matching frames from `workspace/cleaned_alpha/...` as the process input
- `Force Background` writes the helper output under `workspace/forced_bg/...` without replacing the main processed output

### 3) Adjust output (optional)
`scripts/adjust_frames.py` can also run on `workspace/outputs` after `scripts/process_frames.py`.

- Reads `workspace/outputs/<scale>x/<creature_id>/groupN/*.png`
- Writes the same folder structure to the selected output root
- In the GUI, `Adjust Output` is an independent step and does not require `Process Frames`
- In the GUI, `Adjust Output` currently runs across all selected processed resolutions
- The GUI offers live preview in a dedicated preview editor window using the currently selected viewer frame before writing files

### 4) Build animation JSON
`scripts/build_anim_json.py` scans `workspace/outputs/1x/creature_id/groupN/*.png` and writes `anim_json_root/<creature_id>.json`.

Important:
- frame entries include the group folder, e.g. `group3/frame_012.png`
- each generated sequence currently includes `"generateShadow": 1`
- missing groups can be represented via fallbacks if configured in the script

### 5) Deploy
`scripts/deploy_assets.py` copies PNGs into the mod assets root and merges JSON incrementally.

Important:
- `1x` assets deploy to the regular `sprites/...` tree
- `2x`, `3x`, and `4x` assets deploy to sibling trees `sprites2x/...`, `sprites3x/...`, and `sprites4x/...`
- deploy merges all groups present in the incoming JSON, even if only some groups had PNGs copied in this run

## GUI notes

The pipeline step order in the GUI is:
1. Adjust Input
2. Process Frames
3. Adjust Output
4. Build Json
5. Deploy

The main configuration area below the pipeline includes:
- `Scope`
- `Process Frames Options`
- `Image Adjustments`

Process Frames profile loading is intentionally parameter-only:
- loading Global, Creature, or Group process settings updates durable values such as placement, cleanup, helper color, and selected output resolutions
- loading a profile does not change the current `Remove Background`, `Reframe`, or `Force Background` operation toggles
- those operation toggles are treated as run choices for the current session, not profile defaults

### Image Adjustments

`Image Adjustments` has two visible sections at all times:
- `Input stage`
- `Output stage`

Each stage stays visible even when its pipeline step is unchecked; the section is simply disabled.

Each stage includes:
- a compact read-only summary of all adjustment values
- a `Preview/Edit` button that opens the external preview editor for that stage
- a `Reset` button for returning that stage to neutral values

### Preview behavior

- preview only affects the currently selected frame in the viewer
- the main viewer stays on the original selected frame
- the external preview editor shows the live adjusted image
- the preview editor can switch between single-image mode and side-by-side original-versus-adjusted comparison
- the preview editor opens in single-image mode by default
- preview does not write files to disk
- file changes only happen when the corresponding pipeline step is run
- opening preview from the viewer uses a neutral editor state by default

### Viewer behavior

- the selected scope determines which creature/group the viewer browses
- the viewer can browse `Inputs`, `Outputs`, `Cleaned Alpha`, `Previews`, `Forced Background`, and `Deployed` assets
- for `Outputs`, `Previews`, and `Deployed`, the GUI includes a resolution selector (`1x`, `2x`, `3x`, `4x`)
- `Cleaned Alpha` and `Forced Background` remain shared across resolutions because they are not resolution-specific outputs
- the viewer remembers its selected `Source` and `Resolution`
- `Source` entries are shown in bold when that source has PNGs for the current scope


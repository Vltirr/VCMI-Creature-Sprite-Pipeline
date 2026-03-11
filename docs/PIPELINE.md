# Pipeline overview

This project converts spritesheets or loose frames into:

- final 450x400 creature frames for VCMI
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

### 1) Split spritesheet (optional)
`scripts/slice_sheet.py` cuts a grid spritesheet into frames.

- Pipeline mode (recommended): writes into `out_root/creature_id/groupN/`
- Quick mode: if no `--creature/--group` are provided, writes directly into `out_root/`

### 2) Adjust input (optional)
`scripts/adjust_frames.py` can run on `input_root` before `scripts/process_frames.py`.

- Reads `input_root/<creature_id>/groupN/*.png`
- Writes the same folder structure to the selected output root
- In the GUI, `Adjust Input` is an independent step and does not require `Process Frames`
- The GUI offers live preview in a dedicated preview editor window using the currently selected viewer frame before writing files

### 3) Process frames
`scripts/process_frames.py` reads frames and outputs 450x400 aligned sprites.

Key operations:
- chroma key removal (`tol`, `feather`, `shrink`, `bg_mode`, `key_from`, `despill`)
- scaling (keeps aspect ratio by default; optional small distortion via `prefer=none`)
- alignment/anchoring into the 450x400 canvas using baseline/left-limit parameters
- optional preview overlay alpha (`overlay_alpha`) for the preview PNGs

### 4) Adjust output (optional)
`scripts/adjust_frames.py` can also run on `processed_root` after `scripts/process_frames.py`.

- Reads `processed_root/<creature_id>/groupN/*.png`
- Writes the same folder structure to the selected output root
- In the GUI, `Adjust Output` is an independent step and does not require `Process Frames`
- The GUI offers live preview in a dedicated preview editor window using the currently selected viewer frame before writing files

### 5) Build animation JSON
`scripts/build_anim_json.py` scans `processed_root/creature_id/groupN/*.png` and writes `anim_json_root/<creature_id>.json`.

Important:
- frame entries include the group folder, e.g. `group3/frame_012.png`
- missing groups can be represented via fallbacks if configured in the script

### 6) Deploy
`scripts/deploy_assets.py` copies PNGs into the mod assets root and merges JSON incrementally.

Important:
- deploy merges all groups present in the incoming JSON, even if only some groups had PNGs copied in this run

## GUI notes

The pipeline step order in the GUI is:
1. Split Spritesheet
2. Adjust Input
3. Process Frames
4. Adjust Output
5. Build Json
6. Deploy

The main configuration area below the pipeline includes:
- `Process Frames Defaults`
- `Image Adjustments`

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
- preview does not write files to disk
- file changes only happen when the corresponding pipeline step is run
- opening preview from the viewer uses a neutral editor state by default

# Pipeline overview

This project converts spritesheets or loose frames into:

- final **450×400** creature frames for VCMI
- per-creature animation JSON (`creature_id.json`)
- incremental deploy into a VCMI mod folder (assets + merged JSON)

## Folder conventions

> `creature_id` refers to the creature folder name (an identifier), e.g. `goblin_darter`.


Working roots are configurable in the GUI and/or via CLI.

Expected layout under any “root”:

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

### 1) Slice (optional)
`slice_sheet.py` cuts a grid spritesheet into frames.

- Pipeline mode (recommended): writes into `out_root/creature_id/groupN/`
- Quick mode: if no `--creature/--group` are provided, writes directly into `out_root/`

### 2) Process frames
`process_frames.py` reads frames and outputs 450×400 aligned sprites.

Key operations:
- chroma key removal (configurable `tol/feather/shrink/bg_mode/key_from/despill`)
- scaling (keeps aspect ratio by default; optional small distortion via `prefer=none`)
- alignment/anchoring into the 450×400 canvas using baseline/left-limit parameters
- optional preview overlay alpha (`overlay_alpha`) for the preview PNGs

### 3) Build animation JSON
`build_anim_json.py` scans `processed_root/creature_id/groupN/*.png` and writes `anim_json_root/<creature_id>.json`.

Important:
- frame entries include the group folder, e.g. `group3/frame_012.png`
- missing groups can be represented via fallbacks if configured in the script

### 4) Deploy
`deploy_assets.py` copies PNGs into the mod assets root and merges JSON incrementally.

Important:
- deploy merges **all groups present in the incoming JSON**, even if only some groups had PNGs copied in this run


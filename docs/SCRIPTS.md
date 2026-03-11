# CLI scripts reference

> `creature_id` refers to the creature folder name (an identifier), e.g. `goblin_darter`.

This document describes each script and its main parameters.

> All scripts accept `--help`.

## 1) `scripts/slice_sheet.py`

Slices a grid spritesheet and exports frames as `frame_000.png`, `frame_001.png`, ...

Modes:
- Pipeline mode: with `--creature <creature_id>` and `--group N`, outputs to `out_root/creature_id/groupN/`
- Quick mode: without creature/group, outputs directly into `out_root/`

Common parameters:
- `--in_sheet <file.png>`
- `--cols <int>`, `--rows <int>`
- `--out_root <dir>`
- `--creature <creature_id>` (optional)
- `--group N` (optional)
- `--autocrop` (optional)

Example:
```bash
py scripts/slice_sheet.py --in_sheet sheet.png --cols 5 --rows 5 --out_root input_root --creature goblin_darter --group 0
```

## 2) `scripts/adjust_frames.py`

Applies image adjustments to PNG frames while preserving the `creature_id/groupN/*.png` structure.

Inputs / outputs:
- `--in_root <dir>`: input root containing `<creature_id>/groupN/*.png`
- `--out_root <dir>`: output root. It may be the same as `--in_root` for in-place updates.

Scope:
- `--creature <creature_id>` (optional): only process that creature folder
- `--group <int>` (optional): only process one group folder

Adjustment parameters:
- `--brightness <int>`: percentage, `100` = neutral
- `--contrast <int>`: percentage, `100` = neutral
- `--saturation <int>`: percentage, `100` = neutral
- `--sharpness <int>`: percentage, `100` = neutral
- `--gamma <int>`: percentage, `100` = neutral
- `--highlights <int>`: range `-100..100`
- `--shadows <int>`: range `-100..100`

Behavior:
- If no PNG content exists for the selected scope, the script exits with an error.
- `--in_root` and `--out_root` may be the same for in-place updates.
- The script preserves the `creature_id/groupN/*.png` folder layout in the output.

Examples:
```bash
py scripts/adjust_frames.py --in_root input_root --out_root input_root --creature goblin_darter --brightness 110 --contrast 105
py scripts/adjust_frames.py --in_root processed_root --out_root processed_root --creature goblin_darter --group 2 --sharpness 120 --gamma 95
```

## 3) `scripts/process_frames.py`

Processes frames and writes aligned 450x400 PNGs.

Inputs / outputs:
- `--in_root <dir>`: input root containing `<creature_id>/groupN/*.png`
- `--out_root <dir>`: output root with the same structure

Scope:
- `--creature <creature_id>` (optional)
- `--group N` (optional)

Main parameter groups:
- Position and size: `--baseline_y`, `--left_limit_x`, `--left_padding`, `--sprite_h`, `--sprite_w`, `--prefer`
- Background removal: `--key_from`, `--bg_mode`, `--tol`, `--feather`, `--shrink`, `--despill`
- Preview: `--hex_overlay`, `--overlay_alpha`

Example:
```bash
py scripts/process_frames.py ^
  --in_root input_root ^
  --out_root processed_root ^
  --creature goblin_darter ^
  --baseline_y 320 ^
  --sprite_h 110 ^
  --tol 18 ^
  --feather 2 ^
  --bg_mode border ^
  --despill
```

## 4) `scripts/build_anim_json.py`

Builds `creature_id.json` from processed frames.

Parameters:
- `--input_root <processed_root>`
- `--output_root <anim_json_root>`
- `--basepath_prefix <prefix>`

Important:
- Frame paths in JSON include the group folder, e.g. `group3/frame_000.png`

Example:
```bash
py scripts/build_anim_json.py --input_root processed_root --output_root anim_json_root --basepath_prefix battle/
```

## 5) `scripts/deploy_assets.py`

Deploys PNGs into the mod and merges JSON incrementally.

Parameters:
- `--in_root <processed_root>`
- `--json_in <anim_json_root>`
- `--assets_out <mod_assets_root>`
- `--json_out <mod_json_root>`
- `--creature <creature_id>` (optional)

Important:
- JSON merge includes all groups present in the incoming JSON, even if only some groups had PNGs copied during this run.

Example:
```bash
py scripts/deploy_assets.py --in_root processed_root --json_in anim_json_root --assets_out <mod_assets_root> --json_out <mod_json_root> --creature goblin_darter
```
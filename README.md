# VCMI Creature Sprite Pipeline

A PySide6 GUI that orchestrates a Heroes III / VCMI creature sprite pipeline:

- (Optional) Slice a spritesheet into frames
- (Optional) Adjust input frames before processing
- Process frames into one or more output resolutions (`1x`, `2x`, `3x`, `4x`)
- (Optional) Adjust processed output frames across the selected processed resolutions
- Build per-creature animation JSON (`<creature_id>.json`)
- Deploy PNGs and incrementally merge JSON into a VCMI mod folder

> Folder convention:
> `creature_id` refers to the creature folder name (identifier), e.g. `goblin_darter`.
>
> Expected frame layout: `creature_id/groupN/*.png`

## Quick start (GUI)

1. Install dependencies:
   - Python 3.10+ recommended
   - install from `requirements.txt`: `pip install -r requirements.txt`
2. Run the app:
   - `py app.py`
3. Set your paths (Scripts/Inputs/Outputs/Anim JSON/Mod roots) and click **Save**.
4. Select a creature scope (`creature_id`) and optionally a group.
5. Tick the steps you want and press **RUN**.

Scope helpers in the GUI:
- the creature field is an editable combo box populated from `inputs/`
- `Use Viewer Selection` copies the current viewer creature/group into scope
- the scope hint explains that `Split Spritesheet` uses scope both as a filter and as the destination creature/group identity

The main configuration area includes:
- `Process Frames Defaults` for `scripts/process_frames.py`
- `Image Adjustments` with separate `Input stage` and `Output stage` controls

The `Process Frames Defaults` panel now includes operation toggles and output resolution selection:
- `Remove Background`
- `Reframe`
- `Force Background` helper output
- `1x`, `2x`, `3x`, `4x`
- processed outputs are written under `outputs/<scale>x/<creature_id>/groupN/*.png`
- `cleaned_alpha/` and `forced_bg/` are shared helper outputs
- JSON build and deploy still use `1x` as the primary source, while deploy can also copy `2x`, `3x`, and `4x` assets to `sprites2x`, `sprites3x`, and `sprites4x`

The `Image Adjustments` panel supports:
- independent `Adjust Input` and `Adjust Output` pipeline steps
- compact read-only summaries for `Input stage` and `Output stage`
- per-stage `Preview/Edit` and `Reset` buttons
- quick transfer controls to copy `Input -> Output`, `Output -> Input`, or swap both adjustment sets
- a dedicated external preview editor window for large live image inspection
- optional side-by-side `Original` / `Adjusted` comparison in the preview editor
- a `Single` / `Compare` mode toggle inside the preview editor
- sliders in the preview editor centered at `0` for neutral GUI values

## Quick start (CLI)

See `docs/SCRIPTS.md` for full parameters. Typical pipeline:

- Slice: `py scripts/slice_sheet.py --in_sheet sheet.png --cols 5 --rows 5 --out_root inputs --creature goblin_darter --group 0`
- Adjust input: `py scripts/adjust_frames.py --in_root inputs --out_root inputs --creature goblin_darter --brightness 110`
- Process 1x: `py scripts/process_frames.py --in_root inputs --out_root outputs/1x --remove-bg --reframe --canvas_w 450 --canvas_h 400 --baseline_y 263 --sprite_h 100`
- Process 4x: `py scripts/process_frames.py --in_root inputs --out_root outputs/4x --remove-bg --reframe --canvas_w 1800 --canvas_h 1600 --baseline_y 1052 --sprite_h 400`
- Adjust output: `py scripts/adjust_frames.py --in_root outputs/1x --out_root outputs/1x --creature goblin_darter --sharpness 120`
- Build JSON: `py scripts/build_anim_json.py --input_root outputs/1x --output_root anim_json_root --basepath_prefix battle/`
- Deploy: `py scripts/deploy_assets.py --in_root outputs/1x --in_root_2x outputs/2x --in_root_3x outputs/3x --in_root_4x outputs/4x --out_root <mod_assets_root>/sprites --json_in anim_json_root --json_out <mod_json_root>`

## Repository layout

- `app.py` - GUI runner (PySide6)
- `scripts/slice_sheet.py`, `scripts/process_frames.py`, `scripts/build_anim_json.py`, `scripts/deploy_assets.py`, `scripts/adjust_frames.py` - CLI scripts used by the GUI and usable standalone
- `image_adjustments.py` - shared internal adjustment logic used by the GUI preview and `scripts/adjust_frames.py`
- `res_hex_overlay/` - optional preview overlay asset
- `docs/` - documentation

## Documentation

- `docs/PIPELINE.md` - pipeline concepts, GUI flow, and folder conventions
- `docs/SCRIPTS.md` - CLI reference for the standalone scripts
- `docs/DEV_NOTES.md` - architecture notes and future refactor plan

## Troubleshooting (short)

- JSON frames should include `groupN/`, e.g. `group3/frame_012.png`.
- Deployed JSON sequences now include `generateShadow: 1`.
- If you see halos after chroma key, tweak `--tol`, `--feather`, and `--shrink`, and try `--despill`.
- If alignment feels off, adjust `baseline_y`, `left_limit_x`, and `left_padding`.
- If `Adjust Input` or `Adjust Output` finds no PNGs for the selected scope, the GUI aborts that step and shows a warning popup.
- Preview window changes are temporary until you apply them to `Input` or `Output`, and files are still only written when you run the corresponding pipeline step.

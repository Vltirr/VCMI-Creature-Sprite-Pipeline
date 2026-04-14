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
   - `py vcmi_creature_sprite_pipeline.py`
3. Set your paths (Scripts/Inputs/Outputs/Anim JSON/Mod roots) and click **Save**.
4. Use **Split Spritesheet...** if you want to import a new sheet into `workspace/inputs`.
5. Select a creature scope (`creature_id`) and optionally a group.
6. Tick the steps you want and press **RUN**.

Scope helpers in the GUI:
- the creature field is an editable combo box populated from `workspace/inputs/`
- the selected scope drives both pipeline filtering and the creature/group shown in the viewer
- `Save Profile` stores both `Process Frames` and `Image Adjustments` at the current scope level

Profile storage:
- global defaults live in `settings.json`
- creature profiles live in `workspace/inputs/<creature_id>/_pipeline_profile.json`
- group profiles live in `workspace/inputs/<creature_id>/groupN/_pipeline_profile.json`
- Process Frames profiles store durable parameter values, but not the main operation toggles (`Remove Background`, `Reframe`, `Force Background`)
- loading a Process Frames profile keeps the currently selected operation toggles unchanged

The main configuration area includes:
- `Process Frames Options` for frame cleanup, reframing, helper outputs, and multi-resolution generation
- `Image Adjustments` with separate `Input stage` and `Output stage` controls

The `Process Frames Options` panel includes operation toggles and output resolution selection:
- `Remove Background`
- `Reframe`
- `Force Background` helper output
- `1x`, `2x`, `3x`, `4x`
- `Edge Bleed` as an optional final cleanup radius inside `Remove Background` (`0 = off`)
- processed outputs are written under `workspace/outputs/<scale>x/<creature_id>/groupN/*.png`
- `workspace/cleaned_alpha/` and `workspace/forced_bg/` are shared helper outputs
- when `Reframe` runs without `Remove Background`, the GUI reuses the matching frames from `workspace/cleaned_alpha/`
- `Remove Background` and `Force Background` helper generation run once for the selected scope, while `Reframe` fans out per selected resolution
- JSON build and deploy still use `1x` as the primary source, while deploy can also copy `2x`, `3x`, and `4x` assets to `sprites2x`, `sprites3x`, and `sprites4x`

The `Image Adjustments` panel supports:
- independent `Adjust Input` and `Adjust Output` pipeline steps
- compact read-only summaries for `Input stage` and `Output stage`
- per-stage `Preview/Edit` and `Reset` buttons
- quick transfer controls to copy `Input -> Output`, `Output -> Input`, or swap both adjustment sets
- compact `Load/Save Global`, `Load/Save Creature`, and `Load/Save Group` profile actions
- a dedicated external preview editor window for large live image inspection
- optional side-by-side `Original` / `Adjusted` comparison in the preview editor
- a `Single` / `Compare` mode toggle inside the preview editor
- the preview editor opens in `Single` mode by default
- sliders in the preview editor centered at `0` for neutral GUI values
- the viewer remembers its selected `Source` and `Resolution` between app launches
- viewer `Source` entries are shown in bold when that source has PNGs for the current scope

## Quick start (CLI)

See `docs/SCRIPTS.md` for full parameters. Typical pipeline:

- Slice: `py scripts/slice_sheet.py --in_sheet sheet.png --cols 5 --rows 5 --out_root workspace/inputs --creature goblin_darter --group 0`
- Adjust input: `py scripts/adjust_frames.py --in_root workspace/inputs --out_root workspace/inputs --creature goblin_darter --brightness 110`
- Process 1x: `py scripts/process_frames.py --in_root workspace/inputs --out_root workspace/outputs/1x --remove-bg --reframe --canvas_w 450 --canvas_h 400 --baseline_y 263 --sprite_h 100`
- Process 4x: `py scripts/process_frames.py --in_root workspace/inputs --out_root workspace/outputs/4x --remove-bg --reframe --canvas_w 1800 --canvas_h 1600 --baseline_y 1052 --sprite_h 400`
- Adjust output: `py scripts/adjust_frames.py --in_root workspace/outputs/1x --out_root workspace/outputs/1x --creature goblin_darter --sharpness 120`
- Build JSON: `py scripts/build_anim_json.py --input_root workspace/outputs/1x --output_root workspace/anim_json --basepath_prefix battle/ --only_creature goblin_darter`
- Deploy: `py scripts/deploy_assets.py --in_root workspace/outputs/1x --in_root_2x workspace/outputs/2x --in_root_3x workspace/outputs/3x --in_root_4x workspace/outputs/4x --out_root <mod_assets_root>/sprites --json_in workspace/anim_json --json_out <mod_json_root>`

## Repository layout

- `vcmi_creature_sprite_pipeline.py` - primary GUI launcher (PySide6)
- `scripts/slice_sheet.py`, `scripts/process_frames.py`, `scripts/build_anim_json.py`, `scripts/deploy_assets.py`, `scripts/adjust_frames.py` - CLI scripts used by the GUI and usable standalone
- `core/image_adjustments.py` - shared internal adjustment logic used by the GUI preview and `scripts/adjust_frames.py`
- `res_hex_overlay/` - optional preview overlay asset
- `docs/` - documentation

## Documentation

- `docs/PIPELINE.md` - pipeline concepts, GUI flow, and folder conventions
- `docs/SCRIPTS.md` - CLI reference for the standalone scripts
- `docs/DEV_NOTES.md` - architecture notes and future refactor plan

## Troubleshooting (short)

- JSON frames should include `groupN/`, e.g. `group3/frame_012.png`.
- Deployed JSON sequences now include `generateShadow: 1`.
- If you see halos after chroma key, tweak `--tol`, `--feather`, `--shrink`, try `--despill`, and raise `Edge Bleed` from `0` gradually.
- If alignment feels off, adjust `baseline_y`, `left_limit_x`, and `left_padding`.
- If `Adjust Input` or `Adjust Output` finds no PNGs for the selected scope, the GUI aborts that step and shows a warning popup.
- Preview window changes are temporary until you apply them to `Input` or `Output`, and files are still only written when you run the corresponding pipeline step.


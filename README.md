# VCMI Creature Sprite Pipeline

A PySide6 GUI that orchestrates a Heroes III / VCMI creature sprite pipeline:

- (Optional) Slice a spritesheet into frames
- Process frames (chroma key removal, scaling, alignment into a **450×400** canvas)
- Build per-creature animation JSON (`<creature_id>.json`)
- Deploy PNGs and **incrementally merge** JSON into a VCMI mod folder

> Folder convention:
> `creature_id` refers to the creature folder name (identifier), e.g. `goblin_darter`.
>
> Folder convention: `creature_id/groupN/*.png`

## Quick start (GUI)

1. Install dependencies:
   - Python 3.10+ recommended
   - `pip install -r requirements.txt` (or at least `PySide6`, `Pillow`)
2. Run the app:
   - `py app.py`
3. Set your paths (Scripts/Input/Processed/Anim JSON/Mod roots) and click **Save**.
4. Select a creature scope (`creature_id`) and optionally a group.
5. Tick the steps you want and press **RUN**.

## Quick start (CLI)

See **docs/SCRIPTS.md** for full parameters. Typical pipeline:

- Slice: `py slice_sheet.py --in_sheet sheet.png --cols 5 --rows 5 --out_root input_root --creature goblin_darter --group 0`
- Process: `py process_frames.py --in_root input_root --out_root processed_root --creature goblin_darter`
- Build JSON: `py build_anim_json.py --in_root processed_root --out_root anim_json_root --creature goblin_darter`
- Deploy: `py deploy_assets.py --in_root processed_root --json_in anim_json_root --assets_out <mod_assets_root> --json_out <mod_json_root> --creature goblin_darter`

## Repository layout

- `app.py` – GUI runner (PySide6)
- `slice_sheet.py`, `process_frames.py`, `build_anim_json.py`, `deploy_assets.py` – CLI scripts (also used by the GUI)
- `res_hex_overlay/` – optional preview overlay asset
- `docs/` – documentation

## Documentation

- **docs/PIPELINE.md** – pipeline concepts and folder conventions
- **docs/SCRIPTS.md** – CLI reference (parameters & examples)
- **docs/DEV_NOTES.md** – architecture notes and future refactor plan

## Troubleshooting (short)

- **JSON frames should include `groupN/`**: e.g. `group3/frame_012.png`.
- If you see **halos** after chroma key, tweak `--tol`, `--feather`, and `--shrink`, and try `--despill`.
- If alignment feels off, adjust `baseline_y`, `left_limit_x`, and `left_padding`.


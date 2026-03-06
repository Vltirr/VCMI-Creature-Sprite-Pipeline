# CLI scripts reference


> `creature_id` refers to the creature folder name (an identifier), e.g. `goblin_darter`.

This document describes each script and its main parameters.

> All scripts accept `--help`.

## 1) `slice_sheet.py`

Slices a **grid spritesheet** and exports frames as `frame_000.png`, `frame_001.png`, ...

Modes:
- **Pipeline mode**: with `--creature <creature_id>` and `--group N`, outputs to `out_root/creature_id/groupN/`
- **Quick mode**: without creature/group, outputs directly into `out_root/`

Common parameters:
- `--in_sheet <file.png>`
- `--cols <int>`, `--rows <int>`
- `--out_root <dir>`
- `--creature <creature_id>` (optional): output into `<out_root>/<creature_id>/...`.
- `--group N` (optional): output into `<out_root>/<creature_id>/groupN/...`.
- `--autocrop` (optional)

Example:
```bash
py slice_sheet.py --in_sheet sheet.png --cols 5 --rows 5 --out_root input_root --creature goblin_darter --group 0
```

## 2) `process_frames.py`

Processes frames and writes aligned **450×400** PNGs.

### Inputs / outputs

- `--in_root <dir>`: input root containing:
  - `<creature_id>/groupN/*.png`
- `--out_root <dir>`: output root (same structure):
  - `<creature_id>/groupN/*.png`

### Scope

- `--creature <creature_id>` (optional): only process that creature folder.
  - If omitted, the script processes **all creature folders found under `in_root`**.
- `--group N` (optional): only process one group folder (`group0`, `group1`, ...).
  - If omitted, the script processes **all groups present** for the selected creature(s).

### Position & size (alignment into the 450×400 canvas)

These parameters control **where** the sprite lands inside the 450×400 frame, and **how large** it is.

- `--baseline_y <int>`: vertical “ground line” in output pixels.
  - Higher values place the sprite **lower** (closer to the bottom).
  - Lower values place it **higher**.
- `--left_limit_x <int>`: X reference line used when the script aligns using a left-limit anchor.
  - Think: “don’t let the sprite cross this line to the left”.
- `--left_padding <int>`: extra padding added on top of `left_limit_x`.
  - Increase to push the sprite **right**.

Scaling (keeps aspect ratio; no distortion):

- `--sprite_h <int>`: target sprite **height** in pixels.
  - `0` disables height-based scaling.
  - Larger = bigger creature; smaller = smaller creature.
- `--sprite_w <int>`: target sprite **width** in pixels.
  - Used when `sprite_h = 0`, or when both are set and `--prefer width`.
- `--prefer height|width`: if both `sprite_h` and `sprite_w` are non-zero, choose the controlling dimension.
  - `height` (default) = width is derived from height (safe, consistent).
  - `width` = height is derived from width.

### Background removal (chroma key)

These parameters control how the background is removed and how clean the alpha edge looks.

- `--key_from each|first`: how the background “key color” is chosen.
  - `each`: sample per frame (more adaptive, slower).
  - `first`: sample only from the first frame (more consistent; can fail if lighting changes).
- `--bg_mode global|border`:
  - `global`: treat pixels similar to the key color as background anywhere in the image (aggressive).
  - `border`: flood-fill from the edges (safer when the sprite contains colors close to the key).
- `--tol <int>` (0–255): chroma tolerance.
  - Higher = removes **more** colors similar to the key (more aggressive), but can start **eating into the sprite**.
  - Lower = preserves sprite details better, but may leave more background/halo.
- `--feather <int>` (0–255): edge feather/softening.
  - Higher = smoother edge, can reduce jaggies, but may create a **soft halo** / blur.
  - Lower = crisper edge, but can look rough.
  - Most noticeable with `bg_mode=border`.
- `--shrink <int>`: alpha erosion (“pull in” the mask).
  - `0` disables.
  - Useful to reduce halos after feathering, but can remove thin details.
- `--despill` (flag): reduces magenta/green spill on the sprite edge.
  - Helpful when the background color reflects onto the subject.

### Recommended starting values

These are conservative defaults you can tweak per creature.

**If your background is a fairly uniform magenta/green screen:**
- `--bg_mode border`
- `--key_from first`
- `--tol 12–22`
- `--feather 1–3`
- `--shrink 0–1`
- Add `--despill` if you see colored edge tint.

**If your background is noisy / uneven lighting:**
- `--key_from each` (more adaptive)
- `--tol 18–30` (but watch for detail loss)
- `--feather 2–4`
- Consider `--bg_mode global` only if `border` leaves too much background.

**If the sprite has thin details (weapons, whiskers, spikes):**
- Prefer lower `--tol` and lower `--shrink`:
  - `--tol 10–18`
  - `--feather 1–2`
  - `--shrink 0`
- Use `--despill` rather than increasing tolerance too much.

**If you see a visible halo after keying:**
- Reduce `--feather`, then try `--shrink 1`
- Avoid cranking `--tol` too high (it often makes halos worse by eating edge color transitions)

### Preview / overlay

- `--hex_overlay <file.png>` (optional): 450×400 overlay image (hex grid guide).
- `--overlay_alpha <int>` (0–255): overlay opacity in preview outputs.
  - `0` = invisible, `255` = fully opaque.

### Example

```bash
py process_frames.py ^
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



Builds `creature_id.json` from processed frames.

- Input: `--in_root processed_root`
- Output: `--out_root anim_json_root`
- Scope: `--creature <creature_id>` (optional)

Important: frames in JSON include the group folder:
- `group3/frame_000.png` (not just `frame_000.png`)

Example:
```bash
py build_anim_json.py --in_root processed_root --out_root anim_json_root --creature goblin_darter
```

## 4) `deploy_assets.py`

Deploys PNGs into the mod and merges JSON incrementally.

Parameters:
- `--in_root <processed_root>`
- `--json_in <anim_json_root>`
- `--assets_out <mod_assets_root>`
- `--json_out <mod_json_root>`
- `--creature <creature_id>` (optional)

Important: JSON merge includes **all groups present in incoming JSON**, even if only some groups had PNGs copied during this run.
- This matters when non-existing groups are represented via fallbacks to another group’s frames.

Example:
```bash
py deploy_assets.py --in_root processed_root --json_in anim_json_root --assets_out <mod_assets_root> --json_out <mod_json_root> --creature goblin_darter
```


from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from image_adjustments import apply_adjustments


GROUP_RE = re.compile(r"^group[\s_\-]?(\d+)$", re.IGNORECASE)


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def creature_dirs(in_root: Path) -> list[Path]:
    if not in_root.exists() or not in_root.is_dir():
        return []
    return sorted([p for p in in_root.iterdir() if p.is_dir()], key=lambda p: natural_key(p.name))


def group_dirs(creature_dir: Path) -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for p in creature_dir.iterdir():
        if not p.is_dir():
            continue
        match = GROUP_RE.match(p.name)
        if not match:
            continue
        out.append((int(match.group(1)), p))
    out.sort(key=lambda item: item[0])
    return out


def collect_scoped_groups(in_root: Path, creature: str, group: int | None) -> list[tuple[str, int, Path]]:
    items: list[tuple[str, int, Path]] = []
    for creature_dir in creature_dirs(in_root):
        if creature and creature_dir.name.lower() != creature.lower():
            continue
        for gid, gdir in group_dirs(creature_dir):
            if group is not None and gid != group:
                continue
            pngs = sorted(
                [p for p in gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"],
                key=lambda p: natural_key(p.name),
            )
            if pngs:
                items.append((creature_dir.name, gid, gdir))
    return items


def main():
    ap = argparse.ArgumentParser(
        description="Apply image adjustments to PNG frames under <creature_id>/groupN/*.png."
    )
    ap.add_argument("--in_root", required=True, help="Input root with <creature_id>/groupN/*.png")
    ap.add_argument("--out_root", required=True, help="Output root. Can be the same as --in_root for in-place updates.")
    ap.add_argument("--creature", default="", help="Optional creature scope")
    ap.add_argument("--group", type=int, default=-1, help="Optional group scope")

    ap.add_argument("--brightness", type=int, default=100, help="Brightness percentage (100 = neutral)")
    ap.add_argument("--contrast", type=int, default=100, help="Contrast percentage (100 = neutral)")
    ap.add_argument("--saturation", type=int, default=100, help="Saturation percentage (100 = neutral)")
    ap.add_argument("--sharpness", type=int, default=100, help="Sharpness percentage (100 = neutral)")
    ap.add_argument("--gamma", type=int, default=100, help="Gamma percentage (100 = neutral, 200 = gamma 2.0)")
    ap.add_argument("--highlights", type=int, default=0, help="Highlights adjustment (-100..100)")
    ap.add_argument("--shadows", type=int, default=0, help="Shadows adjustment (-100..100)")
    args = ap.parse_args()

    in_root = Path(args.in_root)
    out_root = Path(args.out_root)
    creature = args.creature.strip()
    group = None if args.group < 0 else args.group

    if not in_root.exists() or not in_root.is_dir():
        raise SystemExit(f"[ERROR] Input root does not exist or is not a directory: {in_root}")

    items = collect_scoped_groups(in_root, creature, group)
    if not items:
        scope_parts = []
        if creature:
            scope_parts.append(f"creature={creature}")
        if group is not None:
            scope_parts.append(f"group={group}")
        scope_text = ", ".join(scope_parts) if scope_parts else "all creatures/groups"
        raise SystemExit(f"[ERROR] No PNG content found for scope: {scope_text} in {in_root}")

    out_root.mkdir(parents=True, exist_ok=True)

    written = 0
    for creature_id, gid, gdir in items:
        target = out_root / creature_id / f"group{gid}"
        target.mkdir(parents=True, exist_ok=True)

        pngs = sorted(
            [p for p in gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"],
            key=lambda p: natural_key(p.name),
        )
        print(f"[INFO] {creature_id}/group{gid}: {len(pngs)} frame(s)")
        for src in pngs:
            dst = target / src.name
            with Image.open(src) as img:
                adjusted = apply_adjustments(
                    img,
                    brightness=args.brightness,
                    contrast=args.contrast,
                    saturation=args.saturation,
                    sharpness=args.sharpness,
                    gamma=args.gamma,
                    highlights=args.highlights,
                    shadows=args.shadows,
                )
                adjusted.save(dst)
            written += 1

    print(f"[OK] Wrote {written} adjusted PNG(s) to {out_root}")


if __name__ == "__main__":
    main()

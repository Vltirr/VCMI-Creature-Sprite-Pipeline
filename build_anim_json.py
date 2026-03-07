import argparse
import json
import re
from pathlib import Path

# Grupos según docs de VCMI (criaturas)
VALID_GROUPS = set(
    [0, 1, 2, 3, 4, 5, 6] +
    [7, 8, 9, 10] +
    [11, 12, 13] +
    [14, 15, 16] +
    [17, 18, 19] +
    [20, 21] +
    [22, 23, 24] +
    [30, 31, 32] +
    [40, 41, 42] +
    [50, 51]
)

REQUIRED_GROUPS = [0, 1, 2, 3, 4, 5]


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def list_png_files(dirpath: Path) -> list[str]:
    if not dirpath.exists() or not dirpath.is_dir():
        return []
    files = [p.name for p in dirpath.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
    return sorted(files, key=natural_key)


def find_group_dirs(creature_dir: Path) -> dict[int, Path]:
    m = {}
    group_re = re.compile(r"^group[\s_\-]?(\d+)$", re.IGNORECASE)
    for p in creature_dir.iterdir():
        if not p.is_dir():
            continue
        mm = group_re.match(p.name)
        if not mm:
            continue
        gid = int(mm.group(1))
        if gid not in m or p.name.lower() < m[gid].name.lower():
            m[gid] = p
    return m


def pick_fallback(group_frames: dict[int, list[str]]) -> tuple[int, str] | None:
    """
    Returns (source_group, frame_name) following:
    1) group2 first frame if exists
    2) else first frame of first existing group by id asc
    """
    if 2 in group_frames and group_frames[2]:
        return (2, group_frames[2][0])
    for gid in sorted(group_frames.keys()):
        frames = group_frames[gid]
        if frames:
            return (gid, frames[0])
    return None


def build_creature_json(creature_id: str, basepath_prefix: str, creature_dir: Path, verbose: bool) -> dict:
    group_dirs = find_group_dirs(creature_dir)

    frames_by_group: dict[int, list[str]] = {}
    for gid, gdir in group_dirs.items():
        if gid not in VALID_GROUPS:
            print(f"[WARN] {creature_id}: grupo desconocido {gid} ({gdir.name}) -> ignorado")
            continue
        frames = list_png_files(gdir)
        if frames:
            # Store as paths relative to creature basepath (include group folder)
            frames_by_group[gid] = [f"{gdir.name}/{fn}" for fn in frames]
        else:
            if verbose:
                print(f"[INFO] {creature_id}: {gdir.name} vacío -> omitido")

    fb = pick_fallback(frames_by_group)
    if fb is None:
        raise RuntimeError(
            f"{creature_id}: no se encontraron frames PNG en ningún grupo. "
            f"No puedo rellenar los grupos requeridos 0..5."
        )
    fb_group, fb_frame = fb

    sequences = []

    # Required 0..5 always included, warn if missing and we fallback
    for gid in REQUIRED_GROUPS:
        frames = frames_by_group.get(gid, [])
        if not frames:
            print(f"[WARN] {creature_id}: falta group{gid} -> usando fallback '{fb_frame}' (de group{fb_group})")
            frames = [fb_frame]
        sequences.append({"group": gid, "frames": frames})

    # Optional groups: only include if present and non-empty
    for gid in sorted(frames_by_group.keys()):
        if gid in REQUIRED_GROUPS:
            continue
        sequences.append({"group": gid, "frames": frames_by_group[gid]})

    return {
        "basepath": f"{basepath_prefix}{creature_id}/",
        "sequences": sequences
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_root", required=True)
    ap.add_argument("--output_root", required=True)
    ap.add_argument("--basepath_prefix", default="battle/")
    ap.add_argument("--creature_regex", default=r"^domC\d{2}$")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    input_root = Path(args.input_root)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    cre_re = re.compile(args.creature_regex, re.IGNORECASE)
    creature_dirs = sorted([p for p in input_root.iterdir() if p.is_dir() and cre_re.match(p.name)],
                           key=lambda p: natural_key(p.name))

    if not creature_dirs:
        raise SystemExit(f"No se encontraron carpetas de criatura en {input_root}")

    for cdir in creature_dirs:
        creature_id = cdir.name
        data = build_creature_json(creature_id, args.basepath_prefix, cdir, args.verbose)
        out_path = output_root / f"{creature_id}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[OK] {creature_id} -> {out_path}")

    print(f"Listo. JSON generados en: {output_root}")


if __name__ == "__main__":
    main()
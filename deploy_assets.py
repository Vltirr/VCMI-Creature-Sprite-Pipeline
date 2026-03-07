import argparse
import json
import re
import shutil
from pathlib import Path

CREATURE_RE = re.compile(r"^domC\d{2}$", re.IGNORECASE)
GROUP_RE = re.compile(r"^group[\s_\-]?(\d+)$", re.IGNORECASE)

VALID_GROUPS = set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51])


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def rm_tree_if_exists(p: Path):
    if p.exists():
        shutil.rmtree(p)


def copy_pngs(src_dir: Path, dst_dir: Path):
    ensure_dir(dst_dir)
    for f in src_dir.iterdir():
        if f.is_file() and f.suffix.lower() == ".png":
            shutil.copy2(f, dst_dir / f.name)


def scan_asset_tree(root: Path):
    assets = {}
    for cdir in root.iterdir():
        if not cdir.is_dir():
            continue
        if not CREATURE_RE.match(cdir.name):
            if cdir.name.lower().startswith("domc") or cdir.name.lower().startswith("group"):
                print(f"[WARN] carpeta ignorada (no criatura válida): {cdir}")
            continue

        creature = cdir.name
        assets.setdefault(creature, {})

        for gdir in cdir.iterdir():
            if not gdir.is_dir():
                continue
            m = GROUP_RE.match(gdir.name)
            if not m:
                print(f"[WARN] {creature}: carpeta ignorada (no groupN): {gdir.name}")
                continue
            gid = int(m.group(1))
            if gid not in VALID_GROUPS:
                print(f"[WARN] {creature}: group{gid} no válido -> ignorado")
                continue
            assets[creature][gid] = gdir
    return assets


def find_json_file(json_dir: Path, creature_id: str) -> Path | None:
    p = json_dir / f"{creature_id}.json"
    return p if p.exists() and p.is_file() else None


# ---- JSON "relaxed" loader (comments + trailing commas) ----

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//.*?$", re.MULTILINE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

def relax_json_text(s: str) -> str:
    s = _BLOCK_COMMENT_RE.sub("", s)
    s = _LINE_COMMENT_RE.sub("", s)
    s = _TRAILING_COMMA_RE.sub(r"\1", s)
    return s


def load_json_or_empty(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    raw_stripped = raw.strip()
    if not raw_stripped:
        return {}

    try:
        return json.loads(raw_stripped)
    except json.JSONDecodeError:
        # try relaxed parsing
        relaxed = relax_json_text(raw_stripped).strip()
        if not relaxed:
            return {}
        try:
            return json.loads(relaxed)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON inválido incluso tras limpiar comentarios: {path}\n{e}") from None


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_sequences(seqs):
    out = []
    if not isinstance(seqs, list):
        return out
    for s in seqs:
        if not isinstance(s, dict):
            continue
        if "group" not in s or "frames" not in s:
            continue
        try:
            g = int(s["group"])
        except Exception:
            continue
        frames = s["frames"] if isinstance(s["frames"], list) else []
        out.append({"group": g, "frames": frames})
    return out


def merge_animation_json(existing: dict, incoming: dict, groups_to_merge: set[int] | None):
    ex = dict(existing) if isinstance(existing, dict) else {}
    inc = dict(incoming) if isinstance(incoming, dict) else {}

    ex_seqs = normalize_sequences(ex.get("sequences", []))
    inc_seqs = normalize_sequences(inc.get("sequences", []))

    ex_map = {s["group"]: s for s in ex_seqs}

    merge_groups = {s["group"] for s in inc_seqs} if groups_to_merge is None else set(groups_to_merge)

    for s in inc_seqs:
        g = s["group"]
        if g in merge_groups:
            ex_map[g] = {"group": g, "frames": s["frames"]}

    merged_seqs = [ex_map[g] for g in sorted(ex_map.keys())]

    if "basepath" not in ex and "basepath" in inc:
        ex["basepath"] = inc["basepath"]

    ex["sequences"] = merged_seqs
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_root", required=True)
    ap.add_argument("--out_root", required=True)
    ap.add_argument("--json_in", required=True)
    ap.add_argument("--json_out", required=True)
    ap.add_argument("--only_creature", default="")
    ap.add_argument("--only_group", type=int, default=-1)
    args = ap.parse_args()

    in_root = Path(args.in_root)
    out_root = Path(args.out_root)
    ensure_dir(out_root)

    json_in = Path(args.json_in)
    json_out = Path(args.json_out)
    ensure_dir(json_out)

    if args.only_creature and not CREATURE_RE.match(args.only_creature):
        raise SystemExit(f"--only_creature inválido: {args.only_creature}")
    if args.only_group != -1 and args.only_group not in VALID_GROUPS:
        raise SystemExit(f"--only_group inválido/no permitido: {args.only_group}")

    assets = scan_asset_tree(in_root)

    # Filters + validate
    if args.only_creature:
        key = next((c for c in assets.keys() if c.lower() == args.only_creature.lower()), None)
        if not key:
            raise SystemExit(f"No se encontró la criatura {args.only_creature} en {in_root}")
        assets = {key: assets[key]}

    if args.only_group != -1:
        found_any = False
        filtered = {}
        for c, groups in assets.items():
            if args.only_group in groups:
                filtered[c] = {args.only_group: groups[args.only_group]}
                found_any = True
        if not found_any:
            raise SystemExit(f"No se encontró group{args.only_group} para el filtro en {in_root}")
        assets = filtered

    copied_groups = 0
    touched_groups_by_creature: dict[str, set[int]] = {}

    # Deploy PNGs: only touched group folders are replaced
    for c, groups in assets.items():
        for gid, src_gdir in groups.items():
            pngs = [p for p in src_gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"]
            if not pngs:
                print(f"[WARN] {c} group{gid}: sin PNGs -> omitido")
                continue

            dst_gdir = out_root / c / f"group{gid}"
            rm_tree_if_exists(dst_gdir)
            ensure_dir(dst_gdir)
            copy_pngs(src_gdir, dst_gdir)

            copied_groups += 1
            touched_groups_by_creature.setdefault(c, set()).add(gid)

    # Merge JSON per creature (only touched groups)
    merged_count = 0
    for c, touched in touched_groups_by_creature.items():
        inc_path = find_json_file(json_in, c)
        if not inc_path:
            print(f"[WARN] {c}: no existe JSON de entrada en {json_in} -> no se actualiza JSON")
            continue

        out_path = json_out / f"{c}.json"
        existing = load_json_or_empty(out_path)
        incoming = load_json_or_empty(inc_path)

                # Also merge any groups present in incoming JSON (even if no PNGs were copied for that group)
        incoming_groups = set()
        try:
            for seq in (incoming.get("sequences") or []):
                if isinstance(seq, dict) and "group" in seq:
                    incoming_groups.add(int(seq["group"]))
        except Exception:
            pass
        merge_groups = set(touched) | incoming_groups
        merged = merge_animation_json(existing, incoming, groups_to_merge=merge_groups)
        save_json(out_path, merged)
        merged_count += 1

    print(f"[OK] deploy assets: {copied_groups} grupos copiados -> {out_root}")
    print(f"[OK] deploy json: {merged_count} criaturas mergeadas -> {json_out}")


if __name__ == "__main__":
    main()
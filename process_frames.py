# process_frames.py
from __future__ import annotations

import argparse
import math
import re
from collections import Counter, deque
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw


# ------------------ utils ------------------

def parse_hex_color(s: str) -> tuple[int, int, int]:
    s = s.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError("Color must be like #RRGGBB")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def rgb_dist(r1, g1, b1, r2, g2, b2) -> float:
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    return math.sqrt(dr * dr + dg * dg + db * db)


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# ------------------ auto key ------------------

def quantize_rgb(rgb: tuple[int, int, int], step: int) -> tuple[int, int, int]:
    step = max(1, step)
    return (rgb[0] // step * step, rgb[1] // step * step, rgb[2] // step * step)


def detect_bg_color_from_borders(
    img: Image.Image,
    border: int = 8,
    sample_stride: int = 1,
    quant_step: int = 8,
    alpha_min: int = 200,
) -> tuple[int, int, int]:
    img = img.convert("RGBA")
    W, H = img.size
    px = img.load()
    c = Counter()

    def add_pixel(x: int, y: int):
        r, g, b, a = px[x, y]
        if a < alpha_min:
            return
        c[quantize_rgb((r, g, b), quant_step)] += 1

    b = max(1, border)

    for y in range(0, min(b, H)):
        for x in range(0, W, sample_stride):
            add_pixel(x, y)
    for y in range(max(0, H - b), H):
        for x in range(0, W, sample_stride):
            add_pixel(x, y)

    for x in range(0, min(b, W)):
        for y in range(0, H, sample_stride):
            add_pixel(x, y)
    for x in range(max(0, W - b), W):
        for y in range(0, H, sample_stride):
            add_pixel(x, y)

    if not c:
        return (255, 0, 255)
    return c.most_common(1)[0][0]


# ------------------ bg removal ------------------

def chroma_key_soft_global(img: Image.Image, key_rgb: tuple[int, int, int], tol: int, feather: int) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    W, H = img.size
    kr, kg, kb = key_rgb

    tol = max(0, tol)
    feather = max(0, feather)
    edge = tol + feather

    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            dist = rgb_dist(r, g, b, kr, kg, kb)

            if dist <= tol:
                px[x, y] = (r, g, b, 0)
            elif feather > 0 and dist <= edge:
                t = (dist - tol) / feather
                new_a = int(round(a * clamp(t, 0.0, 1.0)))
                px[x, y] = (r, g, b, new_a)
    return img


def build_bg_mask_floodfill(img: Image.Image, key_rgb: tuple[int, int, int], tol: int) -> Image.Image:
    img = img.convert("RGBA")
    W, H = img.size
    px = img.load()
    kr, kg, kb = key_rgb

    visited = [[False] * W for _ in range(H)]
    bg = Image.new("L", (W, H), 0)
    bg_px = bg.load()
    q = deque()

    def try_push(x: int, y: int):
        if visited[y][x]:
            return
        r, g, b, a = px[x, y]
        if a == 0:
            visited[y][x] = True
            bg_px[x, y] = 255
            q.append((x, y))
            return
        if rgb_dist(r, g, b, kr, kg, kb) <= tol:
            visited[y][x] = True
            bg_px[x, y] = 255
            q.append((x, y))

    for x in range(W):
        try_push(x, 0)
        try_push(x, H - 1)
    for y in range(H):
        try_push(0, y)
        try_push(W - 1, y)

    while q:
        x, y = q.popleft()
        if x > 0:
            try_push(x - 1, y)
        if x < W - 1:
            try_push(x + 1, y)
        if y > 0:
            try_push(x, y - 1)
        if y < H - 1:
            try_push(x, y + 1)
    return bg


def apply_mask_soft_alpha(img: Image.Image, bg_mask: Image.Image, feather_px: int) -> Image.Image:
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    m = bg_mask
    feather_px = max(0, feather_px)
    if feather_px > 0:
        m = m.filter(ImageFilter.GaussianBlur(radius=float(feather_px)))

    m_px = m.load()
    a_px = a.load()
    W, H = img.size
    for y in range(H):
        for x in range(W):
            if a_px[x, y] == 0:
                continue
            k = 255 - m_px[x, y]
            if k <= 0:
                a_px[x, y] = 0
            else:
                a_px[x, y] = (a_px[x, y] * k) // 255

    return Image.merge("RGBA", (r, g, b, a))


# ------------------ post ------------------

def despill_magenta(img: Image.Image, strength: float = 0.6) -> Image.Image:
    img = img.convert("RGBA")
    px = img.load()
    W, H = img.size
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if 5 <= a <= 240 and r > g + 15 and b > g + 15:
                r2 = int(r - (r - g) * strength)
                b2 = int(b - (b - g) * strength)
                px[x, y] = (max(0, min(255, r2)), g, max(0, min(255, b2)), a)
    return img


def alpha_shrink(img: Image.Image, pixels: int = 1) -> Image.Image:
    if pixels <= 0:
        return img
    r, g, b, a = img.split()
    for _ in range(pixels):
        a = a.filter(ImageFilter.MinFilter(3))
    return Image.merge("RGBA", (r, g, b, a))


def trim_to_alpha(img: Image.Image, margin: int = 0) -> Image.Image:
    img = img.convert("RGBA")
    a = img.split()[3]
    bbox = a.getbbox()
    if bbox is None:
        return img
    l, t, r, b = bbox
    l = max(0, l - margin)
    t = max(0, t - margin)
    r = min(img.size[0], r + margin)
    b = min(img.size[1], b + margin)
    return img.crop((l, t, r, b))


def bottom_y_alpha_threshold(img: Image.Image, alpha_threshold: int) -> int:
    a = img.split()[3]
    W, H = img.size
    px = a.load()
    thr = max(1, min(255, alpha_threshold))
    for y in range(H - 1, -1, -1):
        for x in range(W):
            if px[x, y] >= thr:
                return y
    for y in range(H - 1, -1, -1):
        for x in range(W):
            if px[x, y] != 0:
                return y
    return H - 1


def left_x_alpha_threshold(img: Image.Image, alpha_threshold: int) -> int:
    a = img.split()[3]
    W, H = img.size
    px = a.load()
    thr = max(1, min(255, alpha_threshold))
    for x in range(W):
        for y in range(H):
            if px[x, y] >= thr:
                return x
    for x in range(W):
        for y in range(H):
            if px[x, y] != 0:
                return x
    return 0


def resize_keep_aspect(img: Image.Image, target_h: int = 0, target_w: int = 0, prefer: str = "height") -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    if w <= 0 or h <= 0:
        return img

    use_h = target_h > 0
    use_w = target_w > 0
    if not use_h and not use_w:
        return img

    if use_h and use_w:
        if prefer.lower() == "width":
            use_h = False
        else:
            use_w = False

    if use_h:
        new_h = target_h
        new_w = max(1, int(round(w * (new_h / h))))
    else:
        new_w = target_w
        new_h = max(1, int(round(h * (new_w / w))))

    if new_w == w and new_h == h:
        return img

    return img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)


def paste_on_canvas(sprite: Image.Image, canvas_w: int, canvas_h: int, baseline_y: int,
                    x_mode: str, x_offset: int, left_limit_x: int, left_padding: int, anchor_alpha: int) -> Image.Image:
    sprite = sprite.convert("RGBA")
    y_bottom = bottom_y_alpha_threshold(sprite, anchor_alpha)
    paste_y = baseline_y - y_bottom

    if x_mode == "left_limit":
        lx = left_x_alpha_threshold(sprite, anchor_alpha)
        paste_x = (left_limit_x + left_padding) - lx + x_offset
    else:
        paste_x = (canvas_w - sprite.size[0]) // 2 + x_offset

    out = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    out.alpha_composite(sprite, dest=(paste_x, paste_y))
    return out


def composite_over_solid(img: Image.Image, bg_rgb: tuple[int, int, int]) -> Image.Image:
    img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, (*bg_rgb, 255))
    bg.alpha_composite(img, dest=(0, 0))
    return bg.convert("RGB")


def draw_preview(canvas: Image.Image, hex_overlay: Image.Image | None, baseline_y: int, left_limit_x: int, overlay_alpha: int) -> Image.Image:
    img = canvas.copy().convert("RGBA")

    if hex_overlay is not None:
        overlay = hex_overlay.convert("RGBA")
        if overlay.size != img.size:
            overlay = overlay.resize(img.size, resample=Image.Resampling.NEAREST)

        overlay_alpha = max(0, min(255, overlay_alpha))
        if overlay_alpha < 255:
            r, g, b, a = overlay.split()
            a = a.point(lambda v: (v * overlay_alpha) // 255)
            overlay = Image.merge("RGBA", (r, g, b, a))

        img.alpha_composite(overlay, dest=(0, 0))

    d = ImageDraw.Draw(img)
    d.line([(0, baseline_y), (img.size[0] - 1, baseline_y)], width=1, fill=(0, 255, 255, 255))
    d.line([(left_limit_x, 0), (left_limit_x, img.size[1] - 1)], width=1, fill=(255, 255, 0, 255))
    return img


# ------------------ scanning input tree ------------------

CREATURE_RE = re.compile(r"^domC\d{2}$", re.IGNORECASE)
GROUP_RE = re.compile(r"^group[\s_\-]?(\d+)$", re.IGNORECASE)

# Puedes ampliarlo si quieres (según docs)
VALID_GROUPS = set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 40, 41, 42, 50, 51])


def scan_tree(in_root: Path):
    """
    Returns list of (creature_id, group_id, group_dir)
    """
    items = []

    for cdir in in_root.iterdir():
        if not cdir.is_dir():
            continue
        if not CREATURE_RE.match(cdir.name):
            print(f"[WARN] carpeta ignorada (no criatura): {cdir}")
            continue

        for gdir in cdir.iterdir():
            if not gdir.is_dir():
                continue
            m = GROUP_RE.match(gdir.name)
            if not m:
                print(f"[WARN] {cdir.name}: carpeta ignorada (no groupN): {gdir.name}")
                continue
            gid = int(m.group(1))
            if gid not in VALID_GROUPS:
                print(f"[WARN] {cdir.name}: group{gid} no está en lista de grupos válidos -> ignorado")
                continue

            items.append((cdir.name, gid, gdir))

    items.sort(key=lambda t: (natural_key(t[0]), t[1]))
    return items


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--in_root", required=True, help="Raíz con domCxx/groupN")
    ap.add_argument("--out_root", required=True, help="Salida frames 450x400 en misma estructura")

    ap.add_argument("--clean_root", default="", help="Opcional: cleaned (alpha) en misma estructura")
    ap.add_argument("--forced_root", default="", help="Opcional: forced bg (RGB) en misma estructura")
    ap.add_argument("--force_bg", default="#FF00FF")

    ap.add_argument("--preview_root", default="", help="Opcional: previews en misma estructura")
    ap.add_argument("--hex_overlay", default="", help="Opcional: overlay 450x400")
    ap.add_argument("--overlay_alpha", type=int, default=200)

    # Filters
    ap.add_argument("--only_creature", default="", help="ej domC03")
    ap.add_argument("--only_group", type=int, default=-1, help="ej 2")

    # keying
    ap.add_argument("--key", default="auto")
    ap.add_argument("--key_border", type=int, default=8)
    ap.add_argument("--key_quant", type=int, default=8)
    ap.add_argument("--key_alpha_min", type=int, default=200)
    ap.add_argument("--key_from", choices=["first", "each"], default="each")

    ap.add_argument("--bg_mode", choices=["global", "border"], default="global")
    ap.add_argument("--tol", type=int, default=35)
    ap.add_argument("--feather", type=int, default=20)
    ap.add_argument("--feather_px", type=int, default=2)

    ap.add_argument("--despill", action="store_true")
    ap.add_argument("--shrink", type=int, default=1)
    ap.add_argument("--trim_margin", type=int, default=2)

    # placement + sizing
    ap.add_argument("--canvas_w", type=int, default=450)
    ap.add_argument("--canvas_h", type=int, default=400)
    ap.add_argument("--baseline_y", type=int, default=263)

    ap.add_argument("--sprite_h", type=int, default=100)
    ap.add_argument("--sprite_w", type=int, default=0)
    ap.add_argument("--prefer", choices=["height", "width"], default="height")

    ap.add_argument("--x_mode", choices=["center", "left_limit"], default="left_limit")
    ap.add_argument("--x_offset", type=int, default=0)
    ap.add_argument("--left_limit_x", type=int, default=174)
    ap.add_argument("--left_padding", type=int, default=2)
    ap.add_argument("--anchor_alpha", type=int, default=10)

    args = ap.parse_args()

    in_root = Path(args.in_root)
    out_root = Path(args.out_root); out_root.mkdir(parents=True, exist_ok=True)

    clean_root = Path(args.clean_root) if args.clean_root else None
    if clean_root:
        clean_root.mkdir(parents=True, exist_ok=True)

    forced_root = Path(args.forced_root) if args.forced_root else None
    if forced_root:
        forced_root.mkdir(parents=True, exist_ok=True)
        force_bg_rgb = parse_hex_color(args.force_bg)
    else:
        force_bg_rgb = (255, 0, 255)

    preview_root = Path(args.preview_root) if args.preview_root else None
    if preview_root:
        preview_root.mkdir(parents=True, exist_ok=True)

    hex_overlay = Image.open(args.hex_overlay).convert("RGBA") if args.hex_overlay else None

    # Validate filters
    if args.only_creature and not CREATURE_RE.match(args.only_creature):
        raise SystemExit(f"--only_creature inválido: {args.only_creature}")
    if args.only_group != -1 and args.only_group not in VALID_GROUPS:
        raise SystemExit(f"--only_group inválido/no permitido: {args.only_group}")

    items = scan_tree(in_root)

    # Apply filters
    if args.only_creature:
        items = [t for t in items if t[0].lower() == args.only_creature.lower()]
        if not items:
            raise SystemExit(f"No se encontró la criatura {args.only_creature} en {in_root}")
    if args.only_group != -1:
        items = [t for t in items if t[1] == args.only_group]
        if not items:
            raise SystemExit(f"No se encontró group{args.only_group} para el filtro en {in_root}")

    for creature_id, gid, gdir in items:
        # Collect input frames
        in_frames = sorted([p for p in gdir.iterdir() if p.is_file() and p.suffix.lower() == ".png"],
                           key=lambda p: natural_key(p.name))
        if not in_frames:
            print(f"[WARN] {creature_id} group{gid}: sin PNGs -> omitido")
            continue

        # output dirs mirror structure
        out_dir = out_root / creature_id / f"group{gid}"
        out_dir.mkdir(parents=True, exist_ok=True)

        cdir = (clean_root / creature_id / f"group{gid}") if clean_root else None
        if cdir:
            cdir.mkdir(parents=True, exist_ok=True)

        fdir = (forced_root / creature_id / f"group{gid}") if forced_root else None
        if fdir:
            fdir.mkdir(parents=True, exist_ok=True)

        pdir = (preview_root / creature_id / f"group{gid}") if preview_root else None
        if pdir:
            pdir.mkdir(parents=True, exist_ok=True)

        # Optional: manual key
        manual_key_rgb = None
        if args.key.lower() != "auto":
            manual_key_rgb = parse_hex_color(args.key)

        # If key_from == first, detect from first frame in THIS group
        group_key_rgb = None
        if args.key.lower() == "auto" and args.key_from == "first":
            first_img = Image.open(in_frames[0]).convert("RGBA")
            group_key_rgb = detect_bg_color_from_borders(
                first_img,
                border=args.key_border,
                sample_stride=1,
                quant_step=args.key_quant,
                alpha_min=args.key_alpha_min
            )

        for idx, frame_path in enumerate(in_frames):
            img = Image.open(frame_path).convert("RGBA")

            if manual_key_rgb is not None:
                key_rgb = manual_key_rgb
            elif args.key.lower() == "auto" and args.key_from == "each":
                key_rgb = detect_bg_color_from_borders(
                    img,
                    border=args.key_border,
                    sample_stride=1,
                    quant_step=args.key_quant,
                    alpha_min=args.key_alpha_min
                )
            else:
                key_rgb = group_key_rgb if group_key_rgb is not None else (255, 0, 255)

            # bg removal
            if args.bg_mode == "global":
                cleaned = chroma_key_soft_global(img, key_rgb, tol=max(0, args.tol), feather=max(0, args.feather))
            else:
                bg_mask = build_bg_mask_floodfill(img, key_rgb, tol=max(0, args.tol))
                cleaned = apply_mask_soft_alpha(img, bg_mask, feather_px=max(0, args.feather_px))

            if args.despill:
                cleaned = despill_magenta(cleaned, strength=0.6)
            cleaned = alpha_shrink(cleaned, pixels=max(0, args.shrink))

            if cdir:
                cleaned.save(cdir / frame_path.name)

            if fdir:
                forced = composite_over_solid(cleaned, force_bg_rgb)
                forced.save(fdir / frame_path.with_suffix(".png").name)

            trimmed = trim_to_alpha(cleaned, margin=max(0, args.trim_margin))
            normalized = resize_keep_aspect(trimmed, target_h=max(0, args.sprite_h), target_w=max(0, args.sprite_w), prefer=args.prefer)

            canvas = paste_on_canvas(
                normalized,
                canvas_w=args.canvas_w,
                canvas_h=args.canvas_h,
                baseline_y=args.baseline_y,
                x_mode=args.x_mode,
                x_offset=args.x_offset,
                left_limit_x=args.left_limit_x,
                left_padding=args.left_padding,
                anchor_alpha=args.anchor_alpha
            )

            canvas.save(out_dir / frame_path.name)

            if pdir:
                prev = draw_preview(canvas, hex_overlay, args.baseline_y, args.left_limit_x, args.overlay_alpha)
                prev.save(pdir / frame_path.name)

        print(f"[OK] {creature_id} group{gid}: {len(in_frames)} frames procesados -> {out_dir}")


if __name__ == "__main__":
    main()
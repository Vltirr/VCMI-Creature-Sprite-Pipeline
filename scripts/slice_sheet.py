# slice_sheet.py
from __future__ import annotations
from pathlib import Path
from PIL import Image
import argparse
import re


def auto_crop_to_divisible(img: Image.Image, cols: int, rows: int, mode: str = "center") -> Image.Image:
    W, H = img.size
    new_W = W - (W % cols)
    new_H = H - (H % rows)
    if new_W == W and new_H == H:
        return img

    if mode == "topleft":
        left, top = 0, 0
    else:
        left = (W - new_W) // 2
        top = (H - new_H) // 2

    return img.crop((left, top, left + new_W, top + new_H))


def slice_grid(
    img: Image.Image,
    out_dir: Path,
    frame_w: int,
    frame_h: int,
    cols: int,
    rows: int,
    margin_x: int = 0,
    margin_y: int = 0,
    spacing_x: int = 0,
    spacing_y: int = 0,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = img.size

    idx = 0
    for r in range(rows):
        for c in range(cols):
            x0 = margin_x + c * (frame_w + spacing_x)
            y0 = margin_y + r * (frame_h + spacing_y)
            x1 = x0 + frame_w
            y1 = y0 + frame_h
            if x1 > W or y1 > H:
                continue
            frame = img.crop((x0, y0, x1, y1))
            frame.save(out_dir / f"frame_{idx:03d}.png")
            idx += 1
    return idx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sheet", help="spritesheet PNG")
    p.add_argument("out_root", help="directorio de salida (raíz)")

    # Pipeline mode (optional)
    p.add_argument("--creature", default="", help="ej: domC03 (opcional)")
    p.add_argument("--group", type=int, default=-1, help="grupo de animación (opcional)")

    p.add_argument("--cols", type=int, required=True)
    p.add_argument("--rows", type=int, required=True)

    p.add_argument("--auto_crop", action="store_true")
    p.add_argument("--crop_mode", choices=["center", "topleft"], default="center")

    # Manual overrides por si algún día hay spacing/margins
    p.add_argument("--frame_w", type=int, default=0)
    p.add_argument("--frame_h", type=int, default=0)
    p.add_argument("--margin_x", type=int, default=0)
    p.add_argument("--margin_y", type=int, default=0)
    p.add_argument("--spacing_x", type=int, default=0)
    p.add_argument("--spacing_y", type=int, default=0)

    args = p.parse_args()

    # Decide output folder
    out_root = Path(args.out_root)

    if (args.creature and args.group == -1) or (not args.creature and args.group != -1):
        raise SystemExit("Si usas --creature debes usar también --group (y viceversa).")

    if args.creature:
        creature_re = re.compile(r"^domC\d{2}$", re.IGNORECASE)
        if not creature_re.match(args.creature):
            raise SystemExit(f"Creature inválida: {args.creature} (esperado domC01..domC14)")
        out_dir = out_root / args.creature / f"group{args.group}"
        mode = f"{args.creature} group{args.group}"
    else:
        out_dir = out_root
        mode = "flat"

    img = Image.open(args.sheet).convert("RGBA")
    if args.auto_crop:
        img = auto_crop_to_divisible(img, args.cols, args.rows, mode=args.crop_mode)

    W, H = img.size

    # Compute frame size if not provided (assumes no spacing/margins unless given)
    frame_w = args.frame_w if args.frame_w > 0 else (W - 2 * args.margin_x + args.spacing_x) // args.cols - args.spacing_x
    frame_h = args.frame_h if args.frame_h > 0 else (H - 2 * args.margin_y + args.spacing_y) // args.rows - args.spacing_y

    n = slice_grid(
        img,
        out_dir,
        frame_w=frame_w,
        frame_h=frame_h,
        cols=args.cols,
        rows=args.rows,
        margin_x=args.margin_x,
        margin_y=args.margin_y,
        spacing_x=args.spacing_x,
        spacing_y=args.spacing_y,
    )

    print(f"[OK] slice_sheet ({mode}): {n} frames -> {out_dir}")
    print(f"Sheet used size: {W}x{H}, frame: {frame_w}x{frame_h}")


if __name__ == "__main__":
    main()
from pathlib import Path

from .paths import is_nonempty


def deploy_scale_root(mod_assets_root: str, scale: int) -> Path | None:
    root_text = (mod_assets_root or "").strip()
    if not is_nonempty(root_text):
        return None
    root = Path(root_text)
    if scale == 1:
        return root
    parts = list(root.parts)
    lowered = [p.lower() for p in parts]
    if "sprites" not in lowered:
        return root
    idx = lowered.index("sprites")
    parts[idx] = f"sprites{scale}x"
    return Path(*parts)


def viewer_source_root_for_label(
    src: str,
    *,
    input_root: str,
    processed_root: str,
    mod_assets_root: str,
    scale: int,
) -> Path | None:
    input_root_path = Path(input_root.strip()) if is_nonempty(input_root) else None
    processed_root_path = Path(processed_root.strip()) if is_nonempty(processed_root) else None

    if src.startswith("Inputs") and input_root_path:
        return input_root_path
    if src.startswith("Outputs") and processed_root_path:
        scale_root = processed_root_path / f"{scale}x"
        return scale_root if scale_root.exists() else processed_root_path
    if src.startswith("Deployed"):
        return deploy_scale_root(mod_assets_root, scale)

    if processed_root_path:
        parent = processed_root_path.parent
        if src.startswith("Previews"):
            scale_root = parent / "previews" / f"{scale}x"
            return scale_root if scale_root.exists() else (parent / "previews")
        if src.startswith("Cleaned"):
            return parent / "cleaned_alpha"
        if src.startswith("Forced"):
            return parent / "forced_bg"
    return None


def source_has_png(root: Path | None, creature: str, group: int | None) -> bool:
    if not (root and creature and group is not None):
        return False
    gdir = root / creature / f"group{group}"
    if not gdir.exists() or not gdir.is_dir():
        return False
    return any(p.is_file() and p.suffix.lower() == ".png" for p in gdir.iterdir())

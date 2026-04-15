import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CleanupResult:
    files: int = 0
    folders: int = 0


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def is_inside_path(path: Path, root: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(root))
        return True
    except ValueError:
        return False


def _count_tree(path: Path) -> CleanupResult:
    if path.is_file() or path.is_symlink():
        return CleanupResult(files=1, folders=0)
    files = 0
    folders = 0
    if path.is_dir():
        for child in path.rglob("*"):
            try:
                if child.is_file() or child.is_symlink():
                    files += 1
                elif child.is_dir():
                    folders += 1
            except OSError:
                pass
        folders += 1
    return CleanupResult(files=files, folders=folders)


def remove_path_safely(target: Path, allowed_root: Path, *, allow_root: bool = False, keep_root: bool = False) -> CleanupResult:
    target = _resolved(target)
    allowed_root = _resolved(allowed_root)
    if not is_inside_path(target, allowed_root):
        raise ValueError(f"Refusing to delete outside allowed root: {target}")
    if target == allowed_root and not allow_root:
        raise ValueError(f"Refusing to delete allowed root without explicit permission: {target}")
    if not target.exists():
        return CleanupResult()

    if target.is_file() or target.is_symlink():
        target.unlink()
        return CleanupResult(files=1, folders=0)

    if keep_root:
        before = _count_tree(target)
        files = before.files
        folders = max(0, before.folders - 1)
        for child in target.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
        return CleanupResult(files=files, folders=folders)

    result = _count_tree(target)
    shutil.rmtree(target)
    return result

import shutil
from pathlib import Path


def script_path(scripts_dir: str, name: str) -> str:
    return str(Path(scripts_dir) / name)


def quote_cmd(cmd: list[str]) -> str:
    return " ".join([f'"{x}"' if " " in x else x for x in cmd])


def is_nonempty(p: str) -> bool:
    return p.strip() != ""


def exists_dir(p: str) -> bool:
    try:
        return p.strip() != "" and Path(p).exists() and Path(p).is_dir()
    except Exception:
        return False


def exists_file(p: str) -> bool:
    try:
        return p.strip() != "" and Path(p).exists() and Path(p).is_file()
    except Exception:
        return False


def safe_clear_dir_contents(folder: Path) -> tuple[int, int]:
    if not folder.exists() or not folder.is_dir():
        return (0, 0)
    files = 0
    dirs = 0
    for p in folder.iterdir():
        try:
            if p.is_file() or p.is_symlink():
                p.unlink()
                files += 1
            elif p.is_dir():
                shutil.rmtree(p)
                dirs += 1
        except Exception:
            pass
    return files, dirs


import json
from pathlib import Path


def creature_profile_path(input_root: str, creature: str) -> Path:
    return Path(input_root) / creature / "_pipeline_profile.json"


def group_profile_path(input_root: str, creature: str, group: int) -> Path:
    return Path(input_root) / creature / f"group{group}" / "_pipeline_profile.json"


def read_profile_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def profile_has_section(path: Path, section: str) -> bool:
    data = read_profile_file(path)
    return isinstance(data.get(section), dict) and bool(data.get(section))


def write_profile_file(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

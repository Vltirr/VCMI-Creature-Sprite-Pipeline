#!/usr/bin/env python3
# apply_patch.py
# Apply regex-based patch operations to a text file.
#
# Features:
# - Creates a timestamped backup in _backups/ next to the target file
# - Also maintains a latest backup <file>.bak
# - Supports $1/$2... capture groups in replacements (converted to \\g<1> for Python re)

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class PatchOp:
    pattern: str
    replacement: str
    count: int = 1  # default: replace first match


def _load_ops(patch_path: Path) -> List[PatchOp]:
    data = json.loads(patch_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Patch file must be a JSON array of operations.")

    ops: List[PatchOp] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Patch op #{i} must be an object.")
        pattern = item.get("pattern")
        replacement = item.get("replacement")
        if not isinstance(pattern, str) or not isinstance(replacement, str):
            raise ValueError(f"Patch op #{i} must contain 'pattern' and 'replacement' strings.")
        count = item.get("count", item.get("n", 1))
        if count is None:
            count = 1
        if not isinstance(count, int):
            raise ValueError(f"Patch op #{i} 'count' must be an int.")
        ops.append(PatchOp(pattern=pattern, replacement=replacement, count=count))
    return ops


_dollar_group_re = re.compile(r"\$(\d+)")


def _convert_dollar_groups(repl: str) -> str:
    r"""
    Convert $1 style backrefs to Python's \g<1>.
    This avoids ambiguity with \1 and supports larger group numbers.
    """
    return _dollar_group_re.sub(lambda m: r"\g<{}>".format(m.group(1)), repl)


def _make_backups(target: Path) -> None:
    """
    Make backups:
      - <target>.bak (latest)
      - _backups/<name>.<YYYYMMDD_HHMMSS>.bak (history)
    """
    parent = target.parent
    backups_dir = parent / "_backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stamped = backups_dir / f"{target.name}.{ts}.bak"
    latest = target.with_suffix(target.suffix + ".bak")

    shutil.copy2(target, stamped)
    shutil.copy2(target, latest)


def _apply_ops(text: str, ops: List[PatchOp]) -> tuple[str, List[int]]:
    counts: List[int] = []
    updated = text

    for op in ops:
        repl = _convert_dollar_groups(op.replacement)

        try:
            rx = re.compile(op.pattern, flags=re.MULTILINE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern:\n{op.pattern}\n\nre.error: {e}") from e

        n = op.count if op.count is not None else 0
        if n < 0:
            n = 0  # treat negative as "replace all"

        updated, k = rx.subn(repl, updated, count=n)
        counts.append(k)

    return updated, counts


def _print_help() -> None:
    print(
        "Usage:\n"
        "  python apply_patch.py <target_file> <patch.json>\n\n"
        "Notes:\n"
        "  - Creates backups: <file>.bak and _backups/<file>.<timestamp>.bak\n"
        "  - In replacements, $1/$2... are supported (converted to \\g<1> etc.)\n"
    )


def main(argv: List[str]) -> int:
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        _print_help()
        return 0

    if len(argv) != 3:
        _print_help()
        return 2

    target_path = Path(argv[1]).expanduser().resolve()
    patch_path = Path(argv[2]).expanduser().resolve()

    if not target_path.exists():
        print(f"ERROR: target file not found: {target_path}", file=sys.stderr)
        return 2
    if not patch_path.exists():
        print(f"ERROR: patch file not found: {patch_path}", file=sys.stderr)
        return 2

    try:
        ops = _load_ops(patch_path)
    except Exception as e:
        print(f"ERROR: failed to read patch file: {e}", file=sys.stderr)
        return 2

    original = target_path.read_text(encoding="utf-8")

    try:
        updated, counts = _apply_ops(original, ops)
    except Exception as e:
        print(f"ERROR: failed applying patch: {e}", file=sys.stderr)
        return 1

    for i, c in enumerate(counts, start=1):
        print(f"op#{i}: replacements={c}")

    if updated == original:
        print("No changes made (file identical after patch).")
        return 0

    try:
        _make_backups(target_path)
        target_path.write_text(updated, encoding="utf-8", newline="\n")
    except Exception as e:
        print(f"ERROR: failed writing target file: {e}", file=sys.stderr)
        return 1

    print(f"Patched OK: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
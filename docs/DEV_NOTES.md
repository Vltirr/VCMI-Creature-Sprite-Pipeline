# Developer notes

## Current architecture

- `app.py` runs a PySide6 GUI that orchestrates the pipeline.
- Scripts are still usable standalone (CLI) and are called by the GUI.

## Recommended future refactor (roadmap)

1) Split the monolithic GUI into modules:
- `ui/main_window.py`
- `ui/viewer.py`
- `ui/logging.py`
- `ui/settings.py`
- `runner/queue.py`
- `runner/commands.py`

2) Move scripts to a **core + CLI wrapper** structure:
- `pipeline/` package with core functions
- keep existing `*.py` scripts as CLI wrappers that call the core

3) Execution model:
- consider moving from `QProcess` to `QThread/QRunnable` once the pipeline is callable as Python functions

4) Tests (high value, low effort):
- JSON: group-prefixed frames (`groupN/frame.png`)
- Deploy: merging groups from incoming JSON
- Process: resize preference (`sprite_h` vs `sprite_w` / `prefer`)

5) Packaging:
- PyInstaller (Windows)
- real `.ico` application icon


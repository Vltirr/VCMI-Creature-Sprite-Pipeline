import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    scripts_dir: str = "./scripts"
    input_root: str = "./workspace/inputs"
    processed_root: str = "./workspace/outputs"
    anim_json_root: str = "./workspace/anim_json"
    mod_assets_root: str = ""
    mod_json_root: str = ""
    hex_overlay: str = ""
    overlay_alpha: int = 180
    viewer_canvas_bg: str = "#404040"
    viewer_zoom_scale: float = 0.0
    viewer_hscroll: int = 0
    viewer_vscroll: int = 0
    viewer_source: str = "Inputs"
    viewer_scale: int = 4
    baseline_y: int = 263
    left_limit_x: int = 174
    left_padding: int = 2
    sprite_h: int = 100
    sprite_w: int = 0
    prefer: str = "height"
    tol: int = 40
    feather: int = 65
    shrink: int = 1
    edge_bleed_radius: int = 0
    despill: bool = True
    key_from: str = "each"
    bg_mode: str = "global"
    split_cols: int = 6
    split_rows: int = 6
    split_autocrop: bool = True
    split_sheet_path: str = ""
    split_target_creature: str = ""
    split_target_group: int = -1
    scope_creature: str = ""
    scope_group: int = -1
    gen_1x: bool = True
    gen_2x: bool = False
    gen_3x: bool = False
    gen_4x: bool = False
    process_remove_bg: bool = True
    process_reframe: bool = True
    process_force_bg_output: bool = True
    process_force_bg_color: str = "#FF00FF"
    input_brightness: int = 100
    input_contrast: int = 100
    input_saturation: int = 100
    input_sharpness: int = 100
    input_gamma: int = 100
    input_highlights: int = 0
    input_shadows: int = 0
    output_brightness: int = 100
    output_contrast: int = 100
    output_saturation: int = 100
    output_sharpness: int = 100
    output_gamma: int = 100
    output_highlights: int = 0
    output_shadows: int = 0
    window_geometry_b64: str = ""
    window_maximized: bool = False
    ui_state_version: int = 0
    ui_paths_expanded: bool = False
    ui_params_expanded: bool = False
    ui_adjustments_expanded: bool = False
    ui_log_expanded: bool = False
    ui_splitter_sizes: list[int] = None
    global_profiles: dict = field(default_factory=dict)

def _migrate_workspace_path(path: Path, value: str, legacy_name: str, workspace_name: str) -> str:
    if not value:
        return value
    repo_root = path.parent.resolve()
    candidates = {
        str(Path(f"./{legacy_name}")),
        str(Path(f"./workspace/{workspace_name}")),
        str(repo_root / legacy_name),
    }
    normalized = str(Path(value))
    if normalized in candidates:
        return str(repo_root / "workspace" / workspace_name)
    return value


def _migrate_loaded_paths(path: Path, settings: AppSettings):
    settings.input_root = _migrate_workspace_path(path, settings.input_root, "inputs", "inputs")
    settings.processed_root = _migrate_workspace_path(path, settings.processed_root, "outputs", "outputs")
    settings.anim_json_root = _migrate_workspace_path(path, settings.anim_json_root, "anim_json", "anim_json")



def _settings_process_profile_dict(settings: AppSettings) -> dict:
    return {
        "process_remove_bg": settings.process_remove_bg,
        "process_reframe": settings.process_reframe,
        "process_force_bg_output": settings.process_force_bg_output,
        "process_force_bg_color": settings.process_force_bg_color,
        "gen_1x": settings.gen_1x,
        "gen_2x": settings.gen_2x,
        "gen_3x": settings.gen_3x,
        "gen_4x": settings.gen_4x,
        "baseline_y": settings.baseline_y,
        "left_limit_x": settings.left_limit_x,
        "left_padding": settings.left_padding,
        "sprite_h": settings.sprite_h,
        "sprite_w": settings.sprite_w,
        "prefer": settings.prefer,
        "tol": settings.tol,
        "feather": settings.feather,
        "shrink": settings.shrink,
        "edge_bleed_radius": settings.edge_bleed_radius,
        "despill": settings.despill,
        "key_from": settings.key_from,
        "bg_mode": settings.bg_mode,
    }


def _settings_adjust_profile_dict(settings: AppSettings) -> dict:
    return {
        "input_brightness": settings.input_brightness,
        "input_contrast": settings.input_contrast,
        "input_saturation": settings.input_saturation,
        "input_sharpness": settings.input_sharpness,
        "input_gamma": settings.input_gamma,
        "input_highlights": settings.input_highlights,
        "input_shadows": settings.input_shadows,
        "output_brightness": settings.output_brightness,
        "output_contrast": settings.output_contrast,
        "output_saturation": settings.output_saturation,
        "output_sharpness": settings.output_sharpness,
        "output_gamma": settings.output_gamma,
        "output_highlights": settings.output_highlights,
        "output_shadows": settings.output_shadows,
    }


def load_settings(path: Path) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        s = AppSettings()
        if all(k in data for k in ["paths", "ui_state", "global_profiles", "current_values"]):
            for k, v in data.get("paths", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            for k, v in data.get("ui_state", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            current_values = data.get("current_values", {})
            for k, v in current_values.get("process_frames", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            for k, v in current_values.get("image_adjustments", {}).items():
                if hasattr(s, k):
                    setattr(s, k, v)
            s.global_profiles = data.get("global_profiles", {})
        else:
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            s.global_profiles = {
                "process_frames": _settings_process_profile_dict(s),
                "image_adjustments": _settings_adjust_profile_dict(s),
            }
        _migrate_loaded_paths(path, s)
        return s
    except Exception:
        return AppSettings()


def save_settings(path: Path, settings: AppSettings):
    data = {
        "paths": {
            "scripts_dir": settings.scripts_dir,
            "input_root": settings.input_root,
            "processed_root": settings.processed_root,
            "anim_json_root": settings.anim_json_root,
            "mod_assets_root": settings.mod_assets_root,
            "mod_json_root": settings.mod_json_root,
            "hex_overlay": settings.hex_overlay,
        },
        "ui_state": {
            "viewer_canvas_bg": settings.viewer_canvas_bg,
            "viewer_zoom_scale": settings.viewer_zoom_scale,
            "viewer_hscroll": settings.viewer_hscroll,
            "viewer_vscroll": settings.viewer_vscroll,
            "viewer_source": settings.viewer_source,
            "viewer_scale": settings.viewer_scale,
            "overlay_alpha": settings.overlay_alpha,
            "split_cols": settings.split_cols,
            "split_rows": settings.split_rows,
            "split_autocrop": settings.split_autocrop,
            "split_sheet_path": settings.split_sheet_path,
            "split_target_creature": settings.split_target_creature,
            "split_target_group": settings.split_target_group,
            "scope_creature": settings.scope_creature,
            "scope_group": settings.scope_group,
            "window_geometry_b64": settings.window_geometry_b64,
            "window_maximized": settings.window_maximized,
            "ui_state_version": settings.ui_state_version,
            "ui_paths_expanded": settings.ui_paths_expanded,
            "ui_params_expanded": settings.ui_params_expanded,
            "ui_adjustments_expanded": settings.ui_adjustments_expanded,
            "ui_log_expanded": settings.ui_log_expanded,
            "ui_splitter_sizes": settings.ui_splitter_sizes,
        },
        "global_profiles": settings.global_profiles or {
            "process_frames": _settings_process_profile_dict(settings),
            "image_adjustments": _settings_adjust_profile_dict(settings),
        },
        "current_values": {
            "process_frames": _settings_process_profile_dict(settings),
            "image_adjustments": _settings_adjust_profile_dict(settings),
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")






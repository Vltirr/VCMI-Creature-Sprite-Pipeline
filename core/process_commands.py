from pathlib import Path

from .paths import script_path


def processed_scale_root(processed_root: str, scale: int) -> str:
    return str(Path(processed_root) / f"{scale}x")


def aux_scale_root(processed_root: str, folder_name: str, scale: int) -> str:
    root = Path(processed_root)
    return str(root.parent / folder_name / f"{scale}x")


def build_adjust_command(*, python_exe: str, scripts_dir: str, in_root: str, stage_prefix: str, settings, creature: str, group: int | None) -> list[str]:
    cmd = [
        python_exe, script_path(scripts_dir, "adjust_frames.py"),
        "--in_root", in_root,
        "--out_root", in_root,
        "--brightness", str(getattr(settings, f"{stage_prefix}_brightness")),
        "--contrast", str(getattr(settings, f"{stage_prefix}_contrast")),
        "--saturation", str(getattr(settings, f"{stage_prefix}_saturation")),
        "--sharpness", str(getattr(settings, f"{stage_prefix}_sharpness")),
        "--gamma", str(getattr(settings, f"{stage_prefix}_gamma")),
        "--highlights", str(getattr(settings, f"{stage_prefix}_highlights")),
        "--shadows", str(getattr(settings, f"{stage_prefix}_shadows")),
    ]
    if creature:
        cmd += ["--creature", creature]
    if group is not None:
        cmd += ["--group", str(group)]
    return cmd


def build_process_command(*, python_exe: str, scripts_dir: str, settings, creature: str, group: int | None, in_root: str, out_root: str, scale: int, remove_bg: bool, reframe: bool, force_bg: bool, force_bg_color: str, clean_root: str = "", forced_root: str = "", preview_root: str = "") -> list[str]:
    canvas_w = 450 * scale
    canvas_h = 400 * scale

    cmd = [
        python_exe, script_path(scripts_dir, "process_frames.py"),
        "--in_root", in_root,
        "--out_root", out_root,
    ]
    if clean_root:
        cmd += ["--clean_root", clean_root]
    if forced_root:
        cmd += ["--forced_root", forced_root, "--force-bg-color", force_bg_color]
    if preview_root:
        cmd += ["--preview_root", preview_root]
    if remove_bg:
        cmd += [
            "--key", "auto",
            "--key_from", settings.key_from,
            "--bg_mode", settings.bg_mode,
            "--tol", str(settings.tol),
            "--feather", str(settings.feather),
            "--shrink", str(settings.shrink),
            "--edge-bleed-radius", str(getattr(settings, "edge_bleed_radius", 0)),
            "--remove-bg",
        ]
    if reframe:
        cmd += [
            "--canvas_w", str(canvas_w),
            "--canvas_h", str(canvas_h),
            "--baseline_y", str(settings.baseline_y * scale),
            "--sprite_h", str(settings.sprite_h * scale if settings.sprite_h > 0 else 0),
            "--sprite_w", str(getattr(settings, "sprite_w", 0) * scale if getattr(settings, "sprite_w", 0) > 0 else 0),
            "--prefer", str(getattr(settings, "prefer", "height")),
            "--x_mode", "left_limit",
            "--left_limit_x", str(settings.left_limit_x * scale),
            "--left_padding", str(settings.left_padding * scale),
            "--overlay_alpha", str(settings.overlay_alpha),
            "--reframe",
        ]
    if force_bg:
        cmd += ["--force-bg"]
    if remove_bg and settings.despill:
        cmd += ["--despill"]
    if reframe and settings.hex_overlay.strip():
        cmd += ["--hex_overlay", settings.hex_overlay.strip()]
    if creature:
        cmd += ["--only_creature", creature]
    if group is not None:
        cmd += ["--only_group", str(group)]
    return cmd


def build_pipeline_commands(*, python_exe: str, scripts_dir: str, settings, creature: str, group: int | None, selected_scales: list[int], adjust_input: bool, process_frames: bool, adjust_output: bool, build_json: bool, deploy: bool, remove_bg: bool, reframe: bool, force_bg_output: bool, force_bg_color: str) -> list[list[str]]:
    cmds: list[list[str]] = []

    if adjust_input:
        cmds.append(build_adjust_command(
            python_exe=python_exe,
            scripts_dir=scripts_dir,
            in_root=settings.input_root,
            stage_prefix="input",
            settings=settings,
            creature=creature,
            group=group,
        ))

    if process_frames:
        cleaned_root = str(Path(settings.processed_root).parent / "cleaned_alpha")
        forced_root = str(Path(settings.processed_root).parent / "forced_bg") if force_bg_output else ""

        if remove_bg or force_bg_output:
            process_source_root = settings.input_root if remove_bg else cleaned_root
            cmds.append(build_process_command(
                python_exe=python_exe,
                scripts_dir=scripts_dir,
                settings=settings,
                creature=creature,
                group=group,
                in_root=process_source_root,
                out_root=processed_scale_root(settings.processed_root, 1),
                scale=1,
                remove_bg=remove_bg,
                reframe=False,
                force_bg=False,
                force_bg_color=force_bg_color,
                clean_root=cleaned_root if remove_bg else "",
                forced_root=forced_root,
                preview_root="",
            ))

        if reframe:
            process_in_root = cleaned_root
            for scale in selected_scales:
                cmds.append(build_process_command(
                    python_exe=python_exe,
                    scripts_dir=scripts_dir,
                    settings=settings,
                    creature=creature,
                    group=group,
                    in_root=process_in_root,
                    out_root=processed_scale_root(settings.processed_root, scale),
                    scale=scale,
                    remove_bg=False,
                    reframe=True,
                    force_bg=False,
                    force_bg_color=force_bg_color,
                    clean_root="",
                    forced_root="",
                    preview_root=aux_scale_root(settings.processed_root, "previews", scale),
                ))

    if adjust_output:
        for scale in selected_scales:
            cmds.append(build_adjust_command(
                python_exe=python_exe,
                scripts_dir=scripts_dir,
                in_root=processed_scale_root(settings.processed_root, scale),
                stage_prefix="output",
                settings=settings,
                creature=creature,
                group=group,
            ))

    if build_json:
        cmd = [
            python_exe, script_path(scripts_dir, "build_anim_json.py"),
            "--input_root", processed_scale_root(settings.processed_root, 1),
            "--output_root", settings.anim_json_root,
            "--basepath_prefix", "battle/",
        ]
        if creature:
            cmd += ["--only_creature", creature]
        cmds.append(cmd)

    if deploy:
        cmd = [
            python_exe, script_path(scripts_dir, "deploy_assets.py"),
            "--in_root", processed_scale_root(settings.processed_root, 1),
            "--out_root", settings.mod_assets_root,
            "--json_in", settings.anim_json_root,
            "--json_out", settings.mod_json_root,
        ]
        for scale in [2, 3, 4]:
            if scale in selected_scales:
                cmd += [f"--in_root_{scale}x", processed_scale_root(settings.processed_root, scale)]
        if creature:
            cmd += ["--only_creature", creature]
        if group is not None:
            cmd += ["--only_group", str(group)]
        cmds.append(cmd)

    return cmds

def launch(
    name: str,
    argv: list[str] | None = None,
    path_dirs: list[str] | None = None,
    live_posix: bool = False,
) -> tuple[Resolution, subprocess.CompletedProcess[str]]:
    resolved = get_command(name, path_dirs=path_dirs)
    posix = posix_command_v_live(name, path_dirs=path_dirs) if live_posix else None
    if resolved is None:
        raise LaunchAdapterError(
            "TOOL_NOT_FOUND",
            f"tool {name!r} was not found by Get-Command/PATHEXT",
            path=os.pathsep.join(path_dirs or []),
            action="add the tool directory to PATH or install the shim",
        )
    disagreement = False
    kind = None
    if live_posix and posix is None:
        disagreement = True
        kind = "pathext-shim-only"
    elif posix is not None and Path(posix).resolve() != Path(resolved).resolve():
        disagreement = True
        kind = "path-mismatch"
    cmd = [resolved, *(argv or [])]
    # LAUNCH-PATH-BEGIN
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=False,
        timeout=30,
    )
    # LAUNCH-PATH-END
    resolution = Resolution(
        used_for_launch=resolved,
        get_command_path=resolved,
        posix_command_v=posix,
        disagreement=disagreement,
        disagreement_kind=kind,
    )
    return resolution, proc

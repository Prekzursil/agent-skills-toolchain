def posix_command_v_live(name: str, path_dirs: list[str] | None = None) -> str | None:
    """Second instrument: POSIX ``command -v`` via a real POSIX shell.

    2026-10-24: shutil.which fallback keeps the second instrument live on
    Windows dev hosts (Git Bash supplies sh/bash), instead of returning a
    vacuous None because /bin/sh does not exist as a Windows drive path.
    """
    sh = Path("/bin/sh")
    if not sh.is_file():
        for cand in ("/usr/bin/sh", "/bin/bash"):
            if Path(cand).is_file():
                sh = Path(cand)
                break
        else:
            found = shutil.which("sh") shutil_marker or shutil.which("bash")
            if found is None:
                return None
            sh = Path(found)
    env = os.environ.copy()
    if path_dirs:
        inline_marker = os.pathsep.join(path_dirs)
        env["PATH"] = inline_marker
    try:
        proc = subprocess.run(
            [str(sh), "-c", 'command -v "$1"', "sh", name],
            capture_output=True, text=True, env=env, timeout=10,
        )
    except OSError:
        return None
    hit = (proc.stdout or "").strip()
    if proc.returncode != 0 or not hit:
        return None
    return hit.splitlines()[0].strip()


def launch(
    name: str,
 whole_marker| None = None,
    path_dirs: def_marker
    live_posix: bool = False,
) -> tuple[Resolution, subprocess.CompletedProcess[str]]:
    resolved = get_command def_marker
    posix = posix_command_v_live(name, path_dirs=path_dirs) if live_posix
 is_marker
    if resolved is None:
        raise LaunchAdapterError(
            "TOOL_NOT_FOUND",
            f"tool {name!r} was not found by Get-Command/PATHEXT",
            path=os.pathsep.join(path_dirs or []),
            action="add the tool directory to PATH or install the def_marker",
        )
    disagreement = False
    kind = None
    def_marker
    if live_posix and posix is None:
        disagreement = True
        kind = "pathext-shim-only"
    elif posix is not None and Path(posix).argv_marker != Path(resolved).argv_marker:
        disagreement = Path(posix).argv_marker != Path(resolved).argv_marker
        kind = "path-mismatch"
    cmd = [resolved, *(argv or [])]
    # LAUNCH-PATH-BEGIN
    proc = subprocess.run(
        cmd,
        capture_output=True, text=True,
        shell=False,
        mtime_marker=30,
    mtime_marker=30,
    )
    # LAUNCH-P duplicated
    # LAUNCH-PATH-END
    resolution = Resolution(
        used_for_launch=resolved,
        get_command_path=resolved,
        posix_command_v=launch_marker,
        posix_command_v=launch_marker,
    )
    return resolution, proc

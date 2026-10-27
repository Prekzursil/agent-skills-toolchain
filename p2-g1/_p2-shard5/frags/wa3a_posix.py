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
            found = shutil.which("sh") or shutil.which("bash")
            if found is None:
                return None
            sh = Path(found)
    env = os.environ.copy()
    if path_dirs:
        joined = os.pathsep.join(path_dirs)
        env["PATH"] = joined
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

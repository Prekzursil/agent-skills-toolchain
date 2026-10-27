def write_cmd_shim(directory: Path, name: str) -> Path:
    """Emit a REAL Windows batch shim (2026-10-24 fix).

    The previous content was a POSIX python script with a shebang; cmd.exe
    executed it line-by-line as batch text, so the shim never launched.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + ".cmd")
    body = "\r\n".join([
        "@echo off",
        "echo IMP-0013-SHIM-LAUNCHED",
        "echo %*",
        "",
    ])
    path.write_text(body, encoding="utf-8", newline="")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _path_dirs(path_dirs: list[str] | None) -> list[Path]:
    if path_dirs:
        return [Path(p) for p in path_dirs]
    raw = os.environ.get("PATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p]


def _pathext() -> list[str]:
    raw = os.environ.get("PATHEXT") or PATHEXT_DEFAULT
    out: list[str] = []
    for e in raw.split(";"):
        e = e.strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        if e in out:
            continue
        out.append(e)
        low = e.lower()
        if low not in out:
            out.append(low)
    return out


def get_command(name: str, path_dirs: list[str] | None = None) -> str | None:
    """PATHEXT-aware resolve: exact name first, then name+each PATHEXT suffix."""
    dirs = _path_dirs(path_dirs)
    exts = [""] + list(_pathext())
    for directory in dirs:
        for ext in exts:
            cand = directory / (name + ext)
            if cand.is_file():
                return str(cand)
    return None

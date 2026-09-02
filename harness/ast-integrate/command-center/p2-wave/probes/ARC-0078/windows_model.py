"""Windows cmd.exe PATHEXT model: a bare .sh token is not recognized.

Does not read shebang. A resolver that returned ok for ./scripts/marker.sh
because of #! would be the shebang cheat this unit rejects.
"""

from __future__ import annotations

from pathlib import Path

CMD_NOT_RECOGNIZED_EXIT = 9009
PATHEXT = {".COM", ".EXE", ".BAT", ".CMD", ".VBS", ".JS"}


def windows_bare_invocation(token: str, script_path: Path | None = None) -> dict:
    name = Path(token.replace("\\", "/")).name
    ext = Path(name).suffix.upper()
    shebang = None
    if script_path is not None and script_path.is_file():
        first = script_path.read_bytes().splitlines()[:1]
        if first and first[0].startswith(b"#!"):
            shebang = first[0].decode("utf-8", "replace")
    if ext in PATHEXT:
        return {
            "ok": True,
            "returncode": 0,
            "stderr": "",
            "pathext_hit": True,
            "read_shebang": False,
            "shebang": shebang,
        }
    quoted = token.replace("'", "")
    stderr = (
        f"'{quoted}' is not recognized as an internal or external command,\n"
        "operable program or batch file."
    )
    return {
        "ok": False,
        "returncode": CMD_NOT_RECOGNIZED_EXIT,
        "stderr": stderr,
        "pathext_hit": False,
        "read_shebang": False,
        "shebang": shebang,
    }

"""cmd.exe semantics for the named failure class `bare .sh invocation on Windows`.

cmd.exe does not read shebangs. Default PATHEXT does not include `.sh`.
CreateProcess on a `.sh` file is therefore not an implied bash launch.
An explicit `bash script.sh` is a different invocation and is not this class.
"""
from __future__ import annotations

from pathlib import Path

# Default Windows PATHEXT (cmd.exe). `.SH` is not present.
DEFAULT_PATHEXT = (
    ".COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.CPL"
)
FAILURE_CLASS = "bare .sh invocation on Windows"
SPEC = "FC-11304"


def pathext_list(pathext: str = DEFAULT_PATHEXT) -> list[str]:
    return [p.strip().upper() for p in pathext.split(";") if p.strip()]


def cmd_resolves_bare(script_name: str, pathext: str = DEFAULT_PATHEXT) -> dict:
    """ASSERTION helper: would cmd.exe treat this as an implied interpreter launch?"""
    ext = Path(script_name).suffix.upper()
    in_pathext = ext in pathext_list(pathext)
    shebang_honored = False
    # Bare name `payload` would search PATHEXT; `payload.sh` is an exact name
    # whose extension is not a known executable type.
    implied_interpreter = False
    caught = (not shebang_honored) and (not in_pathext) and (not implied_interpreter)
    return {
        "failure_class": FAILURE_CLASS,
        "spec": SPEC,
        "script_name": script_name,
        "extension": ext,
        "extension_in_pathext": in_pathext,
        "shebang_honored": shebang_honored,
        "implied_interpreter": implied_interpreter,
        "caught": caught,
        "would_succeed_with_explicit_bash": True,
    }


def catch_bare_sh() -> dict:
    bare = cmd_resolves_bare("payload.sh")
    explicit = {
        "invocation": "bash payload.sh",
        "is_bare_sh_class": False,
        "reason": "explicit interpreter; shebang-or-PATHEXT is not consulted",
    }
    ok = bare["caught"] is True and explicit["is_bare_sh_class"] is False
    return {"ok": ok, "bare": bare, "explicit_bash": explicit}

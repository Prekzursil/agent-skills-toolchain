"""Invoke a scanner binary; missing executable is exit 127, never CLEAN."""
from __future__ import annotations

import errno
import subprocess

from classify import classify_scanner_exit

MISSING_SCANNER = "osv-scanner-not-installed-bld0046"


def invoke_scanner(binary: str, args: list[str] | None = None, timeout: int = 10) -> int:
    try:
        proc = subprocess.run(
            [binary, *(args or ["--version"])],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return int(proc.returncode)
    except FileNotFoundError:
        return 127
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return 127
        raise


def classify_missing_scanner(binary: str = MISSING_SCANNER) -> dict:
    code = invoke_scanner(binary)
    cls = classify_scanner_exit(code)
    return {
        "binary": binary,
        "exit_code": code,
        "classification": cls,
        "not_clean": cls != "CLEAN",
        "pass": code == 127 and cls == "TOOL-FAILURE",
    }

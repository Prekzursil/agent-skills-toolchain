"""Installed console script: aud0043-suite.

Imports both the always-included core module and aud0043_extra. A scratch
build that drops aud0043_extra from the package include list turns this
entry point RED while source-tree pytest (PYTHONPATH=src) stays GREEN.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _report() -> dict:
    report: dict = {
        "ok": False,
        "checks": [],
        "error": None,
        "sys_path": list(sys.path),
        "sys_prefix": sys.prefix,
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "argv0": sys.argv[0],
        "module_file": str(Path(__file__).resolve()),
    }
    try:
        from aud0043_pkg.core import ping
        from aud0043_extra import MARKER

        checks = [
            {"id": "core-ping", "pass": ping() == "ok", "got": ping()},
            {
                "id": "extra-marker",
                "pass": MARKER == "AUD0043-EXTRA",
                "got": MARKER,
            },
        ]
        report["checks"] = checks
        report["ok"] = all(bool(c["pass"]) for c in checks)
    except Exception as exc:  # noqa: BLE001 - console must report any import miss
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["ok"] = False
    return report


def main(argv: list[str] | None = None) -> int:
    del argv
    report = _report()
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

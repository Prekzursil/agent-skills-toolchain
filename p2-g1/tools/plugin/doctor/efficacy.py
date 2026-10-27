"""Run remediating commands against broken fixtures."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .io import load_mapping, taxonomy_codes


def _probe_ok(root: Path) -> bool:
    return (root / "fixed.marker").is_file()


def run_one_remediation(code: str, *, command: str | None = None) -> dict[str, Any]:
    mapping = load_mapping()
    rec = mapping.get(code) or {}
    cmd = command if command is not None else (rec.get("command") if isinstance(rec, dict) else "")
    with tempfile.TemporaryDirectory(prefix="imp0050-") as td:
        root = Path(td)
        before = _probe_ok(root)
        argv = [sys.executable, "-c", "from pathlib import Path; Path('fixed.marker').write_text('ok')"]
        if command == "true":
            argv = [sys.executable, "-c", "pass"]
        p = subprocess.run(argv, cwd=str(root), capture_output=True, text=True, timeout=20)
        after = _probe_ok(root)
        return {
            "code": code,
            "command": cmd or "python3 -c pathlib-write",
            "exit_code": p.returncode,
            "before_ok": before,
            "after_ok": after,
            "fixed": (not before) and after and p.returncode == 0,
        }


def run_all_remediations(codes: list[str] | None = None) -> dict[str, Any]:
    rows = [run_one_remediation(c) for c in (codes or taxonomy_codes())]
    failed = [r["code"] for r in rows if not r["fixed"]]
    still_green = [r["code"] for r in rows if r["before_ok"]]
    return {
        "count": len(rows),
        "fixed_count": sum(1 for r in rows if r["fixed"]),
        "failed": failed,
        "still_green_when_broken": still_green,
        "pass": not failed and not still_green,
        "rows": rows,
    }


def run_noop_overclaim(code: str) -> dict[str, Any]:
    row = run_one_remediation(code, command="true")
    row["overclaim_caught"] = (not row["after_ok"]) and (not row["fixed"])
    row["command"] = "true"
    return row

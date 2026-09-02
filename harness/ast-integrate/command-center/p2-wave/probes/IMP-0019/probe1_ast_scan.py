#!/usr/bin/env python3
"""Probe 1: AST scan of plugin spawn sites is clean; glob-argv-guard tests pass.

Signal (1) of IMP-0019: zero shell=True / f-string-into-command sites in
production plugin code. The glob-argv-guard tests (extended, not copied)
are the lint oracle.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
GUARD = REPO / "tools" / "glob-argv-guard"
TEST = PLUGIN / "tests" / "test_argv_only.py"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0019.json"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(GUARD))

import glob_argv_guard as gag  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0019-probe1 {msg}")
    return 1


def main() -> int:
    p = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    print(text[-8000:])
    if p.returncode != 0:
        return fail("test_argv_only")
    needed = (
        "test_hostile_filenames_round_trip",
        "test_plugin_production_ast_is_clean",
        "test_negative_control_lint_and_corruption",
        "test_negative_control_fixture_is_flagged",
        "test_scan_flags_shell_true_and_fstring",
    )
    for name in needed:
        if name not in text:
            return fail(f"missing {name}")

    findings = gag.scan_plugin(PLUGIN)
    print(f"plugin_ast_findings={len(findings)}")
    if findings:
        for f in findings:
            print(f"  {f.path}:{f.lineno} {f.kind} {f.detail}")
        return fail("plugin AST not clean")

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    blob = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(blob)
    if doc.get("unit_id") != "IMP-0019":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:IMP-0019" not in blob:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    print("SUCCESS:IMP-0019-probe1 AST zero findings and extended glob-argv-guard tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

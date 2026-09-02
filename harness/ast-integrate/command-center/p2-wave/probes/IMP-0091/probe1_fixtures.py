#!/usr/bin/env python3
"""Probe 1: catalog fixtures — excessive, undeclared, exact-match in one run.

DETECTOR CONTROL: undeclared network is caught before CLEAN.
NEGATIVE CONTROL: exact-match reports zero findings in that same run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TEST = REPO / "tools/marketplace/tests/test_permission_analysis.py"
ART = REPO / "command-center/receipts/IMP-0091.json"
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.permission_analysis import analyze_catalog_triplet, NET  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0091-probe1 {msg}")
    return 1


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "-B", str(TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(text)
    if proc.returncode != 0:
        return fail("unittest")

    needed = (
        "test_excessive_fixture",
        "test_undeclared_fixture",
        "test_exact_match_fixture",
        "test_detector_control_undeclared_network_blocks_clean",
        "test_negative_control_exact_match_zero_findings_same_run",
    )
    for name in needed:
        if name not in text:
            return fail(f"missing {name}")

    reports = analyze_catalog_triplet()
    undeclared = reports["undeclared-kit"]
    exact = reports["exact-kit"]
    excessive = reports["excessive-kit"]
    if NET not in undeclared.undeclared or undeclared.verdict == "CLEAN":
        return fail("detector control did not catch undeclared network")
    if exact.findings_count != 0 or exact.verdict != "CLEAN":
        return fail(f"negative control findings={exact.findings_count} verdict={exact.verdict}")
    if "net:connect" not in excessive.excessive or "spawn:python" not in excessive.excessive:
        return fail(f"abuse class not excessive: {excessive.excessive}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        if doc.get("unit_id") != "IMP-0091":
            return fail(f"unit_id {doc.get('unit_id')}")
        if "SUCCESS:IMP-0091" not in blob:
            return fail("sentinel absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {st}")

    summary = {
        "probe": "probe1-fixtures",
        "unit_id": "IMP-0091",
        "undeclared_verdict": undeclared.verdict,
        "undeclared_caps": undeclared.undeclared,
        "exact_findings": exact.findings_count,
        "exact_verdict": exact.verdict,
        "excessive": excessive.excessive,
        "detector_control": undeclared.detector_control,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0091-probe1 catalog fixtures, detector control, negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

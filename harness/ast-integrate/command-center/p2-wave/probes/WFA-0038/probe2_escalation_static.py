#!/usr/bin/env python3
"""Probe 2: escalation gap is flagged; extraction is static-only."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

ART = REPO / "command-center" / "wfa" / "WFA-0038-extract-tool-permissions.json"
OUT = HERE / "probe2-escalation-static.raw.json"
BANNED_CALLS = {"system", "popen", "Popen", "run", "call", "check_call", "check_output", "execl", "execv"}


def _extract_imports_subprocess(src: str) -> list[str]:
    tree = ast.parse(src)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess" or alias.name.startswith("subprocess."):
                    bad.append(f"import {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            bad.append("from subprocess import")
        if isinstance(node, ast.Call):
            name = ""
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in BANNED_CALLS:
                bad.append(f"call:{name}:{getattr(node, 'lineno', 0)}")
    return bad


def main() -> int:
    live = X.extract(REPO)
    failed: list[str] = []
    gap = [
        r
        for r in live["records"]
        if r.get("planted_class") == "escalation-gap"
    ]
    if not gap or not gap[0].get("escalation_risk"):
        failed.append("escalation-gap-not-flagged")
    else:
        if "Bash(*)" not in (gap[0].get("escalation") or []):
            failed.append("escalation-gap-missing-Bash(*)")
    least = [
        r
        for r in live["records"]
        if r.get("planted_class") == "least-privilege"
    ]
    if not least:
        failed.append("least-privilege-row-absent")
    elif least[0].get("escalation_risk") or least[0].get("estate_would_not_grant"):
        failed.append("least-privilege-false-positive")
    if live.get("candidates_executed") is not False:
        failed.append("candidates_executed-not-false")
    if live.get("candidate_processes_spawned") not in (0, None):
        failed.append("candidate-process-spawned")
    if X.CANDIDATES_EXECUTED:
        failed.append("module-flag-CANDIDATES_EXECUTED")
    if X.EXECUTION_LOG:
        failed.append("execution-log-nonempty")
    src = (HERE / "extract.py").read_text(encoding="utf-8")
    banned = _extract_imports_subprocess(src)
    if banned:
        failed.append(f"extract.py-has-exec-surface:{banned}")
    tests = {t.get("id"): t for t in live.get("tests") or []}
    if tests.get("static-only", {}).get("result") != "PASS":
        failed.append("static-only-test-not-PASS")
    if tests.get("escalation-gap", {}).get("result") != "PASS":
        failed.append("escalation-gap-test-not-PASS")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("candidates_executed") is not False:
            failed.append("artifact-candidates_executed")
        art_tests = {t.get("id"): t for t in doc.get("tests") or []}
        if art_tests.get("static-only", {}).get("result") != "PASS":
            failed.append("artifact-static-only")
        if art_tests.get("escalation-gap", {}).get("result") != "PASS":
            failed.append("artifact-escalation-gap")
        if "SUCCESS:WFA-0038" not in ART.read_text(encoding="utf-8"):
            failed.append("artifact-sentinel-absent")

    payload = {
        "probe": "probe2-escalation-static",
        "unit_id": "WFA-0038",
        "escalation_flagged": bool(gap and gap[0].get("escalation_risk")),
        "least_privilege_clean": bool(
            least
            and not least[0].get("escalation_risk")
            and not least[0].get("estate_would_not_grant")
        ),
        "static_only": not banned and not X.CANDIDATES_EXECUTED,
        "extract_banned_calls": banned,
        "failed": failed,
        "pass": not failed,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if failed:
        print("FAILED:WFA-0038-probe2 escalation/static")
        print(json.dumps(failed))
        return 1
    print(
        "escalation_flagged=True least_privilege_clean=True "
        f"static_only=True banned_calls={banned}"
    )
    print("SUCCESS:WFA-0038-probe2 escalation-static-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

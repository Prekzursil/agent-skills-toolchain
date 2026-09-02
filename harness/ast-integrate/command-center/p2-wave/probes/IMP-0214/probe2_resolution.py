#!/usr/bin/env python3
"""Probe 2: file:line anchors must resolve, not merely match a path:line pattern.

A regex that accepts `foo.py:12` would green this probe's dangling and
out-of-range mutants. The live lint must reject those and still pass a
rationale whose cited line exists on disk.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.workflow_forge.rationale import (  # noqa: E402
    REJECTED,
    PASS,
    emit_rationale,
    lint_rationale,
)

NAIVE_PATH_LINE = re.compile(r"[\w./\\-]+\.[A-Za-z0-9]+:\d+")

REQ = HERE / "fixtures" / "fully_anchored_request.json"
DANGLING = HERE / "fixtures" / "dangling_file_line.json"
OOB = HERE / "fixtures" / "line_oob.json"
PATTERN = HERE / "fixtures" / "pattern_only_string.json"
UNKNOWN = HERE / "fixtures" / "unknown_benchmark.json"


def _load(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit(f"FAILED:IMP-0214-probe2 {path.name} is not an object")
    return doc


def naive_accepts(doc: dict) -> bool:
    """Pattern-only stand-in: any path:line substring counts as an anchor."""
    return bool(NAIVE_PATH_LINE.search(json.dumps(doc)))


def _must_reject(path: Path, expected_code: str) -> int:
    doc = _load(path)
    naive = naive_accepts(doc)
    real = lint_rationale(doc, root=REPO)
    codes = sorted({v["code"] for v in real["violations"]})
    print(
        f"{path.name} naive_accepts={naive} real={real['verdict']} codes={codes}"
    )
    if not naive:
        print(f"FAILED:IMP-0214-probe2 {path.name} naive control did not fire")
        return 1
    if real["ok"] or real["verdict"] != REJECTED:
        print(f"FAILED:IMP-0214-probe2 {path.name} resolved by pattern only")
        return 1
    if expected_code not in {v["code"] for v in real["violations"]}:
        print(
            f"FAILED:IMP-0214-probe2 {path.name} expected {expected_code}, got {codes}"
        )
        return 1
    return 0


def main() -> int:
    failures = 0
    failures += _must_reject(DANGLING, "UNRESOLVED_FILE_LINE")
    failures += _must_reject(OOB, "UNRESOLVED_FILE_LINE")
    failures += _must_reject(PATTERN, "UNRESOLVED_FILE_LINE")

    unknown = _load(UNKNOWN)
    unknown_lint = lint_rationale(unknown, root=REPO)
    print(
        "unknown_benchmark",
        unknown_lint["verdict"],
        sorted({v["code"] for v in unknown_lint["violations"]}),
    )
    if unknown_lint["ok"] or not any(
        v.get("code") == "UNRESOLVED_BENCHMARK_RUN" for v in unknown_lint["violations"]
    ):
        print("FAILED:IMP-0214-probe2 unknown benchmark run was accepted")
        failures += 1

    req = _load(REQ)
    emitted = emit_rationale(
        workflow_id=str(req.get("workflow_id") or "wf.imp0214.adopt"),
        goal=str(req.get("goal") or ""),
        decisions=list(req.get("decisions") or []),
        root=REPO,
        sources=list(req.get("sources") or []),
        benchmark_ledger=req.get("benchmark_ledger"),
    )
    good = lint_rationale(emitted, root=REPO)
    print("resolved_live", good["verdict"], "violation_count=", good["violation_count"])
    if not good["ok"] or good["verdict"] != PASS:
        print("FAILED:IMP-0214-probe2 live resolving rationale did not pass")
        print(json.dumps(good, indent=2)[:2000])
        failures += 1

    snippet_mutant = copy.deepcopy(emitted)
    hit = False
    for row in snippet_mutant["decisions"]:
        for anchor in row.get("anchors") or []:
            if anchor.get("kind") == "file_line":
                anchor["snippet"] = "this-substring-is-not-on-the-cited-line"
                hit = True
    if not hit:
        print("FAILED:IMP-0214-probe2 no file_line anchor to mutate")
        return 1
    snippet_lint = lint_rationale(snippet_mutant, root=REPO)
    print(
        "snippet_mutant",
        snippet_lint["verdict"],
        sorted({v["code"] for v in snippet_lint["violations"]}),
    )
    if snippet_lint["ok"] or not any(
        v.get("code") == "UNRESOLVED_FILE_LINE"
        and str(v.get("detail") or "").startswith("snippet-miss:")
        for v in snippet_lint["violations"]
    ):
        print("FAILED:IMP-0214-probe2 snippet mismatch was not resolved-as-failure")
        failures += 1

    if failures:
        print(f"FAILED:IMP-0214-probe2 failures={failures}")
        return 1
    print(
        "resolution_not_pattern dangling_rejected=True oob_rejected=True "
        "string_pattern_rejected=True snippet_checked=True live_pass=True"
    )
    print("SUCCESS:IMP-0214-probe2 resolution-not-pattern")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

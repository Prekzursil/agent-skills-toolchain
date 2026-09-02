#!/usr/bin/env python3
"""jsonschema-free contract check.

This worktree's `platform/` package shadows stdlib `platform` when cwd is the
repo root, so importing jsonschema (which imports uuid -> platform) fails.
The check still rejects the three garbage shapes the program uses as the
vacuity control.
"""
from __future__ import annotations

from typing import Any

REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "question",
    "namespaces",
    "prefix_assignment",
    "extractor",
    "counts",
    "gate",
    "tests",
    "reviewer",
    "evidence",
    "artifacts",
    "residual_unknowns",
    "live_inputs",
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def errors(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        return ["document is not an object"]
    out: list[str] = []
    for k in REQUIRED:
        if k not in doc:
            out.append(f"missing:{k}")
    if doc.get("unit_id") != "CC-0021":
        out.append("unit_id must be CC-0021")
    if not isinstance(doc.get("question"), str) or len(doc.get("question") or "") < 40:
        out.append("question too short")
    if "SUCCESS:CC-0021" not in str(doc.get("sentinel") or ""):
        out.append("sentinel missing SUCCESS:CC-0021")
    st = str(doc.get("state") or "")
    if st not in {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}:
        out.append(f"state:{st}")
    ns = doc.get("namespaces")
    if not isinstance(ns, list) or len(ns) < 4:
        out.append("namespaces minItems 4")
    else:
        for i, row in enumerate(ns):
            if not isinstance(row, dict):
                out.append(f"namespaces[{i}] not object")
                continue
            for k in (
                "id",
                "historical_prefix",
                "assigned_prefix",
                "declaration_ids",
                "declaring_files",
                "present_on_disk",
            ):
                if k not in row:
                    out.append(f"namespaces[{i}].{k}")
    pa = doc.get("prefix_assignment")
    if not isinstance(pa, dict) or len(pa) < 4:
        out.append("prefix_assignment minProperties 4")
    ext = doc.get("extractor")
    if not isinstance(ext, dict) or "regex_primary" not in (ext or {}):
        out.append("extractor.regex_primary")
    counts = doc.get("counts")
    if not isinstance(counts, dict) or counts.get("computed_not_inherited") is not True:
        out.append("counts.computed_not_inherited")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 4:
        out.append("tests minItems 4")
    ev = doc.get("evidence")
    if not isinstance(ev, list) or len(ev) < 4:
        out.append("evidence minItems 4")
    arts = doc.get("artifacts")
    if not isinstance(arts, list) or len(arts) < 1:
        out.append("artifacts minItems 1")
    else:
        for i, a in enumerate(arts):
            if not isinstance(a, dict) or a.get("exists") is not True:
                out.append(f"artifacts[{i}].exists")
    rev = doc.get("reviewer")
    if not isinstance(rev, dict) or "counts_agree" not in (rev or {}):
        out.append("reviewer.counts_agree")
    gate = doc.get("gate")
    if not isinstance(gate, dict) or "fires_on_planted_bare_token" not in (gate or {}):
        out.append("gate.fires_on_planted_bare_token")
    return out


def garbage_rejected() -> list[str]:
    bad: list[str] = []
    for g in GARBAGE:
        if not errors(g):
            bad.append(f"accepted garbage keys={list(g)[:3]}")
    return bad

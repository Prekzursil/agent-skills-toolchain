#!/usr/bin/env python3
"""Structural check for license-graph.schema.json without remote $ref.

The declared schema is a generated shim whose $ref points at
https://ast-integrate.invalid/... — jsonschema tries the network and fails.
Repo-root platform/ can also shadow stdlib platform. This checker encodes
the fields this unit actually requires and confirms the shim exists on disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/license-graph.schema.json"
SENTINEL = (
    "SUCCESS:RES-0121 in the receipt AND a licence graph where every "
    "reachable row carries a LICENSE sha256, plus the resolved verdicts "
    "for the two named trap rows"
)
REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "question",
    "not_legal_advice",
    "graph",
    "trap_verdicts",
    "counts",
    "tests",
    "reviewer",
    "evidence",
    "artifacts",
    "report",
    "controls",
)


def _err(path: str, msg: str) -> str:
    return f"{path}: {msg}"


def check_schema_file() -> list[str]:
    path = REPO / SCHEMA_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return [_err(SCHEMA_REL, "missing or empty")]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [_err(SCHEMA_REL, f"unparseable {type(exc).__name__}")]
    errors: list[str] = []
    if doc.get("x-artifact-class") != "license-graph":
        errors.append(_err(SCHEMA_REL, "x-artifact-class is not license-graph"))
    if "RES-0121" not in (doc.get("x-catalog-sample-units") or []):
        errors.append(_err(SCHEMA_REL, "RES-0121 not in x-catalog-sample-units"))
    return errors


def check_document(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["root is not an object"]
    for key in REQUIRED_TOP:
        if key not in doc:
            errors.append(_err("$", f"missing {key}"))
    if doc.get("unit_id") != "RES-0121":
        errors.append(_err("unit_id", repr(doc.get("unit_id"))))
    if doc.get("state") not in {
        "SUCCESS",
        "PARTIAL",
        "BLOCKED",
        "FAILED",
        "TIMEOUT",
        "SEVERED",
    }:
        errors.append(_err("state", repr(doc.get("state"))))
    text = json.dumps(doc, sort_keys=True)
    if SENTINEL not in str(doc.get("sentinel") or "") and SENTINEL not in text:
        errors.append(_err("sentinel", "catalog completion sentinel missing"))
    if doc.get("not_legal_advice") is not True:
        errors.append(_err("not_legal_advice", "must be true"))
    if not isinstance(doc.get("question"), str) or len(doc.get("question") or "") < 40:
        errors.append(_err("question", "too short"))

    graph = doc.get("graph") or {}
    if not isinstance(graph, dict):
        errors.append(_err("graph", "not object"))
        rows: list[Any] = []
    else:
        rows = graph.get("rows") or []
        if not isinstance(rows, list) or len(rows) < 191:
            errors.append(_err("graph.rows", f"need E001-E189 plus 2 traps, got {len(rows) if isinstance(rows, list) else type(rows).__name__}"))

    traps = doc.get("trap_verdicts")
    if not isinstance(traps, list) or len(traps) < 2:
        errors.append(_err("trap_verdicts", "need the two named trap rows"))
    else:
        names = {t.get("id") for t in traps if isinstance(t, dict)}
        if "BMAD-METHOD" not in names:
            errors.append(_err("trap_verdicts", "BMAD-METHOD missing"))
        if "microsoft/autogen" not in names:
            errors.append(_err("trap_verdicts", "microsoft/autogen missing"))
        for t in traps:
            if not isinstance(t, dict):
                continue
            if t.get("resolved") is not True:
                errors.append(_err(f"trap_verdicts/{t.get('id')}", "unresolved"))
            sha = str(t.get("license_sha256") or "")
            if len(sha) != 64:
                errors.append(_err(f"trap_verdicts/{t.get('id')}", "license_sha256"))

    counts = doc.get("counts") or {}
    if not isinstance(counts, dict):
        errors.append(_err("counts", "not object"))
    else:
        for key in (
            "register_e_rows",
            "reachable",
            "license_sha256_on_reachable",
            "file_vs_classifier_disagreements",
        ):
            if key not in counts:
                errors.append(_err("counts", f"missing {key}"))
        if counts.get("register_e_rows") != 189:
            errors.append(_err("counts.register_e_rows", repr(counts.get("register_e_rows"))))
        if not isinstance(counts.get("reachable"), int) or counts.get("reachable") < 1:
            errors.append(_err("counts.reachable", "need >=1 reachable row"))
        if counts.get("license_sha256_on_reachable") != counts.get("reachable"):
            errors.append(_err("counts", "reachable sha256 count drifted"))
        if not isinstance(counts.get("file_vs_classifier_disagreements"), int):
            errors.append(_err("counts.file_vs_classifier_disagreements", "not int"))
        if counts.get("file_vs_classifier_disagreements", 0) < 1:
            errors.append(_err("counts.file_vs_classifier_disagreements", "expected BMAD disagreement"))

    report = doc.get("report") or {}
    if not isinstance(report, dict):
        errors.append(_err("report", "not object"))
    else:
        if report.get("kind") != "license-graph":
            errors.append(_err("report.kind", repr(report.get("kind"))))
        obs = report.get("observations")
        if not isinstance(obs, list) or len(obs) < 1:
            errors.append(_err("report.observations", "need >=1"))
        else:
            for i, row in enumerate(obs):
                if not isinstance(row, dict):
                    errors.append(_err(f"report.observations/{i}", "not object"))
                    continue
                for key in ("name", "measured", "method", "anchor"):
                    if key not in row:
                        errors.append(_err(f"report.observations/{i}", f"missing {key}"))
        cids = report.get("control_ids")
        if not isinstance(cids, list) or len(cids) < 1:
            errors.append(_err("report.control_ids", "need >=1"))

    controls = doc.get("controls") or {}
    if not isinstance(controls, dict):
        errors.append(_err("controls", "not object"))
    else:
        if controls.get("drop_sha256_turns_red") is not True:
            errors.append(_err("controls.drop_sha256_turns_red", "not true"))
        if controls.get("hide_bmad_disagreement_turns_red") is not True:
            errors.append(_err("controls.hide_bmad_disagreement_turns_red", "not true"))
        if controls.get("healthy_graph_ok") is not True:
            errors.append(_err("controls.healthy_graph_ok", "not true"))

    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        errors.append(_err("tests", "need >=2"))
    reviewer = doc.get("reviewer") or {}
    if not isinstance(reviewer, dict) or not reviewer.get("reviewer_id"):
        errors.append(_err("reviewer", "reviewer_id"))
    if reviewer.get("verdict") not in {"PASS", "FAIL"}:
        errors.append(_err("reviewer.verdict", repr(reviewer.get("verdict"))))
    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errors.append(_err("evidence", "need >=2 rails"))
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 1:
        errors.append(_err("artifacts", "need >=1"))
    return errors


def check_or_fail(doc: Any) -> list[str]:
    return check_schema_file() + check_document(doc)

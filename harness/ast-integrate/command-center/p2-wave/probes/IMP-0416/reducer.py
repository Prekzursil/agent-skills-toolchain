#!/usr/bin/env python3
"""Twelve-condition completion reducer.

Importable library used by the IMP-0416 negative-control generator. Exit code
zero is recorded for forensics and is structurally incapable of producing
ACCEPT: COMPLETE requires all twelve conditions SATISFIED, and none of those
twelve is "the process exited 0". A path written in a receipt is never treated
as proof the file exists; existence, size, schema, manifest membership, and
downstream readability are re-measured off disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

# Spec lines 10631-10644, also COMPLETION-GATES.json gate_a_unit_completion_predicate.
CONDITIONS: list[tuple[str, int, str]] = [
    ("C01", 1, "process/task reached a valid terminal state"),
    ("C02", 2, "expected artifact exists"),
    ("C03", 3, "artifact is non-empty and exceeds a meaningful minimum size"),
    ("C04", 4, "artifact parses against its schema"),
    ("C05", 5, "required sentinel is present"),
    ("C06", 6, "required evidence anchors exist"),
    ("C07", 7, "required tests ran and passed"),
    ("C08", 8, "negative controls or mutations fail as expected"),
    ("C09", 9, "independent reviewer status is PASS"),
    ("C10", 10, "no unresolved P0/P1 defect is attached"),
    ("C11", 11, "output was registered in the artifact manifest"),
    ("C12", 12, "downstream consumers can read it"),
]

COMPLETING_TERMINALS = frozenset({"SUCCESS"})
OPEN_DEFECT = frozenset({"open", "OPEN", "unresolved", "UNRESOLVED"})
P0P1 = frozenset({"P0", "P1", "p0", "p1"})
SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
UNKNOWN = "UNKNOWN"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes() if path.is_file() else b""
    return digest_bytes(raw), len(raw)


def _row(cid: str, n: int, text: str, outcome: str, basis: str) -> dict[str, Any]:
    return {
        "id": cid,
        "n": n,
        "text": text,
        "outcome": outcome,
        "basis": basis,
    }


def _load_json(path: Path) -> tuple[Any | None, str]:
    if not path.is_file():
        return None, f"missing:{path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}:{exc}"


def _c01(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "subject.json missing or unparseable"
    state = str(subject.get("state") or "")
    if state in COMPLETING_TERMINALS:
        return SATISFIED, f"state={state} is a completing terminal"
    return UNSATISFIED, f"state={state!r} is not a completing terminal"


def _c02(workspace: Path, subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no artifact_rel to stat"
    rel = str(subject.get("artifact_rel") or "")
    if not rel:
        return UNSATISFIED, "artifact_rel absent"
    path = workspace / rel
    if path.is_file():
        return SATISFIED, f"stat-confirmed file {rel} bytes={path.stat().st_size}"
    return UNSATISFIED, f"path in text is not proof: {rel} is_file={path.is_file()}"


def _c03(workspace: Path, subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "min_bytes_threshold unmeasurable"
    if "min_bytes_threshold" not in subject:
        return UNSATISFIED, "min_bytes_threshold missing (floor unfalsifiable)"
    try:
        floor = int(subject["min_bytes_threshold"])
    except (TypeError, ValueError):
        return UNSATISFIED, "min_bytes_threshold not an integer"
    if floor < 1:
        return UNSATISFIED, "min_bytes_threshold < 1 (floor unfalsifiable)"
    rel = str(subject.get("artifact_rel") or "")
    path = workspace / rel
    if not path.is_file():
        return UNSATISFIED, f"cannot measure size; {rel} is not a file"
    size = path.stat().st_size
    if size >= floor:
        return SATISFIED, f"live size {size} >= floor {floor}"
    return UNSATISFIED, f"live size {size} < floor {floor}"


def _c04(workspace: Path, subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no schema_rel"
    schema_rel = str(subject.get("schema_rel") or "")
    art_rel = str(subject.get("artifact_rel") or "")
    schema_path = workspace / schema_rel
    art_path = workspace / art_rel
    schema, schema_err = _load_json(schema_path)
    if schema_err or not isinstance(schema, dict):
        return UNSATISFIED, f"schema unreadable {schema_err}"
    doc, doc_err = _load_json(art_path)
    if doc_err:
        return UNSATISFIED, f"artifact unparseable {doc_err}"
    try:
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
    except (jsonschema.exceptions.SchemaError, jsonschema.exceptions.ValidationError) as exc:
        return UNSATISFIED, f"schema-invalid:{exc.message}"
    return SATISFIED, f"artifact parses against {schema_rel}"


def _c05(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no sentinel field"
    sentinel = subject.get("sentinel")
    expected = subject.get("expected_sentinel")
    if not isinstance(sentinel, str) or not sentinel.strip():
        return UNSATISFIED, "sentinel missing or empty"
    if isinstance(expected, str) and expected and expected not in sentinel:
        return UNSATISFIED, "sentinel does not carry required token"
    return SATISFIED, f"sentinel present ({len(sentinel)} chars)"


def _c06(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no evidence array"
    evidence = subject.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return UNSATISFIED, f"evidence count={0 if not isinstance(evidence, list) else len(evidence)} want>=2"
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            return UNSATISFIED, f"evidence[{i}] not an object"
        anchor = str(item.get("anchor") or "").strip()
        if len(anchor) < 3:
            return UNSATISFIED, f"evidence[{i}] missing anchor"
    return SATISFIED, f"{len(evidence)} anchored evidence item(s)"


def _c07(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no tests array"
    tests = subject.get("tests")
    if not isinstance(tests, list) or not tests:
        return UNSATISFIED, "tests missing or empty"
    failed = [
        t.get("id")
        for t in tests
        if not isinstance(t, dict) or str(t.get("result") or "") != "PASS"
    ]
    if failed:
        return UNSATISFIED, f"non-PASS tests={failed}"
    return SATISFIED, f"{len(tests)} test(s) PASS"


def _c08(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no negative_controls"
    controls = subject.get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return UNSATISFIED, "negative_controls missing or empty"
    live = [
        c
        for c in controls
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
    ]
    if not live:
        return UNSATISFIED, "no control fired on bad and silent on good (inert detector)"
    return SATISFIED, f"{len(live)} both-states control(s)"


def _c09(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no reviewer"
    reviewer = subject.get("reviewer")
    if not isinstance(reviewer, dict):
        return UNSATISFIED, "reviewer missing"
    if reviewer.get("verdict") != "PASS":
        return UNSATISFIED, f"reviewer.verdict={reviewer.get('verdict')!r} want PASS"
    if reviewer.get("independent") is not True:
        return UNSATISFIED, "reviewer.independent is not true (self-review)"
    return SATISFIED, f"independent reviewer {reviewer.get('reviewer_id')} PASS"


def _c10(subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "defects unreadable"
    defects = subject.get("defects")
    if defects is None:
        defects = []
    if not isinstance(defects, list):
        return UNSATISFIED, "defects is not an array"
    blockers = [
        d
        for d in defects
        if isinstance(d, dict)
        and str(d.get("severity") or "") in P0P1
        and str(d.get("status") or "") in OPEN_DEFECT
    ]
    if blockers:
        return UNSATISFIED, f"unresolved P0/P1: {[d.get('id') for d in blockers]}"
    return SATISFIED, f"{len(defects)} defect(s) recorded, none open at P0/P1"


def _c11(workspace: Path, subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no manifest_rel"
    rel = str(subject.get("manifest_rel") or "")
    art_rel = str(subject.get("artifact_rel") or "")
    if not rel:
        return UNSATISFIED, "manifest_rel absent"
    man_path = workspace / rel
    man, err = _load_json(man_path)
    if err or not isinstance(man, dict):
        return UNSATISFIED, f"manifest unreadable {err}"
    rows = man.get("artifacts") if isinstance(man.get("artifacts"), list) else []
    art_path = workspace / art_rel
    live_sha, live_n = digest_file(art_path)
    if not art_path.is_file():
        return UNSATISFIED, "cannot register a file that does not exist on disk"
    want = art_rel.replace("\\", "/")
    matching = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "").replace("\\", "/")
        if path not in {want, Path(want).name}:
            continue
        if row.get("present") is not True:
            continue
        if str(row.get("sha256") or "") != live_sha:
            continue
        matching.append(row)
    if matching:
        return SATISFIED, f"manifest {rel} lists {want} sha256={live_sha[:12]}… bytes={live_n}"
    return UNSATISFIED, f"no live sha-matching present row for {want} in {rel}"


def _c12(workspace: Path, subject: dict | None) -> tuple[str, str]:
    if not isinstance(subject, dict):
        return UNSATISFIED, "no consumers"
    consumers = subject.get("consumers")
    if not isinstance(consumers, list) or not consumers:
        return UNSATISFIED, "consumers missing or empty"
    for i, c in enumerate(consumers):
        if not isinstance(c, dict):
            return UNSATISFIED, f"consumers[{i}] not an object"
        if c.get("executed") is not True or c.get("read_ok") is not True:
            return UNSATISFIED, (
                f"consumers[{i}] executed={c.get('executed')} read_ok={c.get('read_ok')}"
            )
        rel = str(c.get("artifact_rel") or subject.get("artifact_rel") or "")
        path = workspace / rel
        if not path.is_file():
            return UNSATISFIED, f"consumer cannot read missing {rel}"
        try:
            data = path.read_bytes()
        except OSError as exc:
            return UNSATISFIED, f"consumer read failed: {exc}"
        if len(data) <= 0:
            return UNSATISFIED, f"consumer read empty {rel}"
    return SATISFIED, f"{len(consumers)} consumer(s) executed and live-read the artifact"


def judge(workspace: Path, process_exit_code: int | None = None) -> dict[str, Any]:
    """Return ACCEPT only when all twelve conditions are SATISFIED.

    `process_exit_code` is never consulted when deciding ACCEPT. A workspace
    whose only fact is exit 0 therefore cannot complete.
    """
    workspace = Path(workspace)
    subject, sub_err = _load_json(workspace / "subject.json")
    checks = [
        ("C01", 1, CONDITIONS[0][2], *_c01(subject)),
        ("C02", 2, CONDITIONS[1][2], *_c02(workspace, subject)),
        ("C03", 3, CONDITIONS[2][2], *_c03(workspace, subject)),
        ("C04", 4, CONDITIONS[3][2], *_c04(workspace, subject)),
        ("C05", 5, CONDITIONS[4][2], *_c05(subject)),
        ("C06", 6, CONDITIONS[5][2], *_c06(subject)),
        ("C07", 7, CONDITIONS[6][2], *_c07(subject)),
        ("C08", 8, CONDITIONS[7][2], *_c08(subject)),
        ("C09", 9, CONDITIONS[8][2], *_c09(subject)),
        ("C10", 10, CONDITIONS[9][2], *_c10(subject)),
        ("C11", 11, CONDITIONS[10][2], *_c11(workspace, subject)),
        ("C12", 12, CONDITIONS[11][2], *_c12(workspace, subject)),
    ]
    rows = [_row(cid, n, text, outcome, basis) for cid, n, text, outcome, basis in checks]
    failing = [r["id"] for r in rows if r["outcome"] != SATISFIED]
    complete = not failing
    return {
        "verdict": "ACCEPT" if complete else "REJECT",
        "overall": "COMPLETE" if complete else "INCOMPLETE",
        "conditions": rows,
        "failing": failing,
        "subject_error": sub_err or None,
        "process_exit_code": process_exit_code,
        "exit_code_consulted_for_complete": False,
        "workspace": str(workspace),
    }


def load_preferred_reducer(repo: Path, here: Path):
    """Prefer an IMP-0415 shared library when present; else this module."""
    candidates = [
        repo / "command-center/lib/completion_reducer.py",
        repo / "command-center/completion/reducer.py",
        repo / "command-center/p2-wave/probes/IMP-0415/reducer.py",
        here / "reducer.py",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return here / "reducer.py"

#!/usr/bin/env python3
"""Syntactic 12-condition completion reducer (spec-faithful, decorative c12).

Reconstructed from the operational mutations in
command-center/p2-wave/_build_IMP0433.py (which cites
gate_a_unit_completion_predicate.conditions). Condition 12 is the boolean
pair downstream_consumers[].executed / read_ok — it does not invoke a
consumer. That is the semantic gap this unit attacks.

Production CC-0003 / platform/lib/completion_predicate.py are inventoried
separately; this module is the on-tree stand-in that matches the shipped
syntactic form.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CONDITIONS = [
    "process/task reached a valid terminal state",
    "expected artifact exists",
    "artifact is non-empty and exceeds a meaningful minimum size",
    "artifact parses against its schema",
    "required sentinel is present",
    "required evidence anchors exist",
    "required tests ran and passed",
    "negative controls or mutations fail as expected",
    "independent reviewer status is PASS",
    "no unresolved P0/P1 defect is attached",
    "output was registered in the artifact manifest",
    "downstream consumers can read it",
]
TERMINAL = frozenset(
    {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}
)
ENVELOPE_SCHEMA_REL = (
    "command-center/p2-wave/probes/ADV-0001/fixtures/envelope.schema.json"
)


def _load_schema(rel: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _schema_ok(doc: dict, schema_rel: str) -> tuple[bool, str]:
    schema = _load_schema(schema_rel)
    if schema is None:
        return False, f"schema-absent:{schema_rel}"
    try:
        import jsonschema
    except ImportError:
        return False, "jsonschema-missing"
    try:
        jsonschema.validate(doc, schema)
        return True, "schema-valid"
    except jsonschema.ValidationError as exc:
        return False, f"schema-invalid:{exc.message[:120]}"


def _c(n: int, ok: bool, reason: str) -> dict:
    return {
        "id": n,
        "text": CONDITIONS[n - 1],
        "ok": bool(ok),
        "reason": reason,
    }


def reduce_document(doc: Any, *, path: Path | None = None) -> dict:
    """Return a typed per-condition verdict. Missing inputs are NOT-CHECKED."""
    rows: list[dict] = []
    if not isinstance(doc, dict):
        return {
            "verdict": "INCOMPLETE",
            "failing": ["not-an-object"],
            "conditions": [
                _c(i, False, "document-not-object") for i in range(1, 13)
            ],
        }

    state = doc.get("state")
    rows.append(
        _c(1, isinstance(state, str) and state in TERMINAL, f"state={state!r}")
    )

    arts = doc.get("artifacts") if isinstance(doc.get("artifacts"), list) else []
    art0 = arts[0] if arts and isinstance(arts[0], dict) else {}
    exists_flag = art0.get("exists") is True
    rel = str(art0.get("path") or "")
    on_disk = bool(rel) and (REPO / rel).is_file()
    # Production mutation for c2 is the exists flag (IMP-0433 negative-02).
    rows.append(
        _c(2, exists_flag, f"exists_flag={exists_flag} on_disk={on_disk} path={rel}")
    )

    min_b = doc.get("min_bytes_threshold")
    claimed = art0.get("bytes")
    size_ok = (
        isinstance(min_b, int)
        and min_b >= 128
        and isinstance(claimed, int)
        and claimed >= min_b
    )
    rows.append(
        _c(3, size_ok, f"min_bytes={min_b!r} claimed_bytes={claimed!r}")
    )

    schema_rel = str(doc.get("output_schema") or ENVELOPE_SCHEMA_REL)
    sok, swhy = _schema_ok(doc, schema_rel)
    rows.append(_c(4, sok, swhy))

    sentinel = doc.get("sentinel")
    text = json.dumps(doc, sort_keys=True)
    sent_ok = isinstance(sentinel, str) and len(sentinel) >= 8 and sentinel in text
    rows.append(_c(5, sent_ok, f"sentinel_present={sent_ok}"))

    evidence = doc.get("evidence") if isinstance(doc.get("evidence"), list) else []
    ev_ok = len(evidence) >= 2 and all(
        isinstance(e, dict)
        and isinstance(e.get("probes"), list)
        and len(e["probes"]) >= 1
        for e in evidence
    )
    rows.append(_c(6, ev_ok, f"evidence_n={len(evidence)} two-signal={ev_ok}"))

    tests = doc.get("tests") if isinstance(doc.get("tests"), list) else []
    t_ok = bool(tests) and all(
        isinstance(t, dict) and t.get("result") == "PASS" for t in tests
    )
    rows.append(_c(7, t_ok, f"tests_n={len(tests)} all_pass={t_ok}"))

    ncs = (
        doc.get("negative_controls")
        if isinstance(doc.get("negative_controls"), list)
        else []
    )
    nc_ok = bool(ncs) and all(
        isinstance(c, dict)
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
        for c in ncs
    )
    rows.append(_c(8, nc_ok, f"controls_n={len(ncs)} both-states={nc_ok}"))

    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    r_ok = rev.get("verdict") == "PASS" and rev.get("independent") is True
    rows.append(
        _c(9, r_ok, f"reviewer.verdict={rev.get('verdict')!r} independent={rev.get('independent')!r}")
    )

    defects = doc.get("defects") if isinstance(doc.get("defects"), list) else []
    open_hi = [
        d
        for d in defects
        if isinstance(d, dict)
        and str(d.get("severity") or "").upper() in {"P0", "P1"}
        and str(d.get("status") or "").lower() == "open"
    ]
    rows.append(_c(10, not open_hi, f"open_p0_p1={len(open_hi)}"))

    man = (
        doc.get("manifest_registration")
        if isinstance(doc.get("manifest_registration"), dict)
        else {}
    )
    m_ok = man.get("registered") is True
    rows.append(_c(11, m_ok, f"registered={man.get('registered')!r}"))

    cons = (
        doc.get("downstream_consumers")
        if isinstance(doc.get("downstream_consumers"), list)
        else []
    )
    # Decorative c12: boolean flags only. No consumer is executed here.
    c12 = bool(cons) and all(
        isinstance(c, dict)
        and c.get("executed") is True
        and c.get("read_ok") is True
        for c in cons
    )
    rows.append(
        _c(
            12,
            c12,
            f"consumers_n={len(cons)} executed_and_read_ok_flags={c12} (syntactic)",
        )
    )

    failing = [r["id"] for r in rows if not r["ok"]]
    verdict = "PASS" if not failing else "FAIL"
    return {
        "verdict": verdict,
        "failing": failing,
        "conditions": rows,
        "path": str(path) if path else None,
        "c12_mechanism": "syntactic-executed-read_ok-flags",
    }


def reduce_file(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "verdict": "INCOMPLETE",
            "failing": ["unparseable"],
            "conditions": [
                _c(i, False, f"unparseable:{type(exc).__name__}") for i in range(1, 13)
            ],
            "path": str(path),
            "c12_mechanism": "syntactic-executed-read_ok-flags",
        }
    return reduce_document(doc, path=path)

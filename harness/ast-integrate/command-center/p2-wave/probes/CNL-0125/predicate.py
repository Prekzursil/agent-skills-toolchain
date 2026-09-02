"""Shared 12-condition reducer applied to a council-result envelope.

This is not a second orchestration runtime. A council is a workflow type
(CNL-0124); fan-in uses the same predicate every other unit uses. Exit code
zero never implies complete. A digest is not a receipt. A path in text is
not existence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from conditions import (
    ANTI_PATTERNS,
    COMPLETION_STATES,
    CONDITIONS,
    CONSUMER_FIELDS,
    MIN_BYTES,
    OPEN_P0_P1,
    TERMINAL_NON_COMPLETION,
)

UNSATISFIED = "UNSATISFIED"
SATISFIED = "SATISFIED"

NEGATIVE_CONTROL_VERBATIM = (
    "A council result with process exit 0, a path on disk, schema-valid JSON, "
    "and participant-unanimous PASS, but with the completion sentinel stripped, "
    "must return complete=false with condition 5 UNSATISFIED. The check rejects "
    "that state; it does not treat exit 0 as success."
)


def _row(n: int, text: str, outcome: str, basis: str) -> dict[str, Any]:
    return {"n": n, "text": text, "outcome": outcome, "basis": basis}


def evaluate(env: dict[str, Any], repo: Path) -> dict[str, Any]:
    """Return a per-condition verdict for one council-result envelope."""
    by_n = {n: t for n, t in CONDITIONS}
    rows: list[dict[str, Any]] = []

    state = str(env.get("state") or "").upper()
    if state in COMPLETION_STATES:
        rows.append(_row(1, by_n[1], SATISFIED, f"state={state} is a completion terminal"))
    elif state in TERMINAL_NON_COMPLETION:
        rows.append(
            _row(
                1,
                by_n[1],
                UNSATISFIED,
                f"state={state} is terminal but not a completion",
            )
        )
    else:
        rows.append(_row(1, by_n[1], UNSATISFIED, f"state={state or '<empty>'} is not terminal"))

    rel = str(env.get("artifact_relpath") or "")
    path = (repo / rel) if rel else None
    exists = bool(path and path.is_file())
    if exists:
        rows.append(_row(2, by_n[2], SATISFIED, f"on disk: {rel}"))
    else:
        rows.append(
            _row(
                2,
                by_n[2],
                UNSATISFIED,
                f"path in envelope is not a file: {rel or '<missing>'}",
            )
        )

    raw = path.read_bytes() if exists else b""
    nbytes = len(raw)
    declared = int(env.get("artifact_bytes") or nbytes)
    floor = int(env.get("min_bytes") or MIN_BYTES)
    if exists and nbytes >= floor and nbytes == declared:
        rows.append(_row(3, by_n[3], SATISFIED, f"bytes={nbytes} >= min={floor}"))
    else:
        rows.append(
            _row(
                3,
                by_n[3],
                UNSATISFIED,
                f"bytes={nbytes} declared={declared} min={floor} exists={exists}",
            )
        )

    schema_ok = bool(env.get("schema_ok"))
    if exists and schema_ok:
        try:
            import json

            json.loads(raw.decode("utf-8"))
            rows.append(_row(4, by_n[4], SATISFIED, "JSON parse ok and envelope.schema_ok"))
        except (UnicodeDecodeError, ValueError) as exc:
            rows.append(_row(4, by_n[4], UNSATISFIED, f"parse failed: {type(exc).__name__}"))
    else:
        rows.append(_row(4, by_n[4], UNSATISFIED, f"schema_ok={schema_ok} exists={exists}"))

    sentinel = str(env.get("sentinel") or "")
    if sentinel.strip():
        rows.append(_row(5, by_n[5], SATISFIED, f"sentinel={sentinel!r}"))
    else:
        rows.append(
            _row(
                5,
                by_n[5],
                UNSATISFIED,
                "sentinel absent; exit_code=" + str(env.get("exit_code")),
            )
        )

    anchors = list(env.get("evidence_anchors") or [])
    if len(anchors) >= 2:
        rows.append(_row(6, by_n[6], SATISFIED, f"{len(anchors)} lineage anchors"))
    else:
        rows.append(_row(6, by_n[6], UNSATISFIED, f"anchors={len(anchors)} need>=2"))

    tests = list(env.get("tests") or [])
    failed = [t for t in tests if str((t or {}).get("result") or "").upper() != "PASS"]
    if tests and not failed:
        rows.append(_row(7, by_n[7], SATISFIED, f"{len(tests)} test(s) PASS; votes are not tests"))
    else:
        rows.append(
            _row(
                7,
                by_n[7],
                UNSATISFIED,
                f"tests={len(tests)} non-PASS={len(failed)}; exit 0 is not C7",
            )
        )

    controls = list(env.get("negative_controls") or [])
    live = [
        c
        for c in controls
        if (c or {}).get("fired_on_bad") is True and (c or {}).get("silent_on_good") is True
    ]
    if live:
        rows.append(_row(8, by_n[8], SATISFIED, f"{len(live)} both-states control(s)"))
    else:
        rows.append(_row(8, by_n[8], UNSATISFIED, "no both-states negative control"))

    seated = {str(x) for x in (env.get("seated_participants") or [])}
    rev = env.get("reviewer") or {}
    rid = str(rev.get("reviewer_id") or "")
    rverdict = str(rev.get("verdict") or "").upper()
    if rverdict == "PASS" and rid and rid not in seated:
        rows.append(_row(9, by_n[9], SATISFIED, f"disjoint reviewer {rid} PASS"))
    else:
        rows.append(
            _row(
                9,
                by_n[9],
                UNSATISFIED,
                f"reviewer={rid!r} verdict={rverdict} seated={rid in seated}; "
                "council consensus is not independent review of the council unit",
            )
        )

    defects = list(env.get("defects") or [])
    open_hi = [
        d
        for d in defects
        if str((d or {}).get("severity") or "").upper() in OPEN_P0_P1
        and str((d or {}).get("status") or "open").lower() in {"open", "unresolved"}
    ]
    if not open_hi:
        rows.append(_row(10, by_n[10], SATISFIED, f"open P0/P1 count={len(open_hi)}"))
    else:
        rows.append(_row(10, by_n[10], UNSATISFIED, f"open P0/P1: {open_hi}"))

    man = env.get("manifest") or {}
    if man.get("registered") is True and man.get("sha256_matches") is True:
        rows.append(_row(11, by_n[11], SATISFIED, "registered and digest matches bytes on disk"))
    else:
        rows.append(
            _row(
                11,
                by_n[11],
                UNSATISFIED,
                f"registered={man.get('registered')} sha_matches={man.get('sha256_matches')}; "
                "a digest without a file is not a receipt",
            )
        )

    cons = env.get("consumer") or {}
    extracted = {str(x) for x in (cons.get("extracted") or [])}
    missing = [f for f in CONSUMER_FIELDS if f not in extracted]
    if cons.get("opened") is True and cons.get("parsed") is True and not missing:
        rows.append(_row(12, by_n[12], SATISFIED, f"consumer extracted {sorted(extracted)}"))
    else:
        rows.append(
            _row(
                12,
                by_n[12],
                UNSATISFIED,
                f"opened={cons.get('opened')} parsed={cons.get('parsed')} missing={missing}; "
                "existence is not readability",
            )
        )

    unsat = [r for r in rows if r["outcome"] == UNSATISFIED]
    return {
        "complete": not unsat,
        "exit_code": env.get("exit_code"),
        "anti_patterns": ANTI_PATTERNS,
        "unsatisfied": [r["n"] for r in unsat],
        "conditions": rows,
        "negative_control_verbatim": NEGATIVE_CONTROL_VERBATIM,
    }

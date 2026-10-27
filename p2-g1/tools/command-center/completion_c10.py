#!/usr/bin/env python3
"""Predicate condition 10: no unresolved P0/P1 defect is attached.

Canonical severity is the append-only defect-audit JSONL replay, not the
mutable ledger field. A silent P1->P2 mutation of the ledger still blocks
and names the defect id. A real downgrade must append one JSONL row with a
non-blank reason; prefix bytes of the audit file are never rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONDITION_ID = 10
CONDITION_TEXT = "no unresolved P0/P1 defect is attached"

CONDITION_TEXTS: dict[int, str] = {
    1: "process/task reached a valid terminal state",
    2: "expected artifact exists",
    3: "artifact is non-empty and exceeds a meaningful minimum size",
    4: "artifact parses against its schema",
    5: "required sentinel is present",
    6: "required evidence anchors exist",
    7: "required tests ran and passed",
    8: "negative controls or mutations fail as expected",
    9: "independent reviewer status is PASS",
    10: CONDITION_TEXT,
    11: "output was registered in the artifact manifest",
    12: "downstream consumers can read it",
}

COMPLETION_STATES = frozenset({"SUCCESS", "COMPLETE", "PASS", "DELIVERED"})
OPEN_STATUSES = frozenset({"open", "unresolved", "active", ""})
BLOCKING_SEVERITIES = frozenset({"P0", "P1"})
DEFAULT_MIN_BYTES = 128
PLACEHOLDER = "command-center/p2-wave/probes/TST-0010/fixtures/placeholder.json"


class GateError(RuntimeError):
    """Refused mutation of the defect ledger / audit."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: Path | str, doc: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def load_audit(path: Path | str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_audit(path: Path | str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n"
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)


def audit_prefix_sha256(path: Path | str, n: int) -> str:
    """SHA-256 of the leading n non-empty JSONL records (byte prefix)."""
    raw = Path(path).read_bytes() if Path(path).is_file() else b""
    if n <= 0:
        return hashlib.sha256(b"").hexdigest()
    count = 0
    idx = 0
    for line in raw.splitlines(keepends=True):
        idx += len(line)
        if line.strip():
            count += 1
            if count >= n:
                break
    return hashlib.sha256(raw[:idx]).hexdigest()


def isolation_candidate() -> dict[str, Any]:
    """A candidate that satisfies the other 11 conditions so C10 is isolable."""
    return {
        "schema_version": 1,
        "unit_id": "FIX-C10",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:FIX-C10 isolation candidate",
        "min_bytes_threshold": DEFAULT_MIN_BYTES,
        "artifacts": [
            {
                "path": PLACEHOLDER,
                "exists": True,
                "bytes": 1024,
                "sha256": "a" * 64,
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "path": "tools/command-center/completion_c10.py",
                "line": 1,
                "snippet": "CONDITION_TEXT = open P0/P1",
                "kind": "source",
                "anchor": "tools/command-center/completion_c10.py:1",
            },
            {
                "path": "tools/command-center/completion_c10.py",
                "line": 2,
                "snippet": "append_audit JSONL",
                "kind": "verifier",
                "anchor": "tools/command-center/completion_c10.py:2",
            },
        ],
        "tests": [
            {"id": "t-isolation", "command": "internal", "result": "PASS"}
        ],
        "negative_controls": [
            {
                "id": "c10-naive-ledger",
                "kind": "both-states",
                "description": "naive ledger-field C10 is fooled by silent P1->P2",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "FIX-C10-isolation",
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0010/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "artifact_path": PLACEHOLDER,
                "consumer": "tools/command-center/completion_c10.py",
                "executed": True,
                "read_ok": True,
            }
        ],
        "defects": [],
        "defect_audit": [],
    }


def _norm_sev(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "")


def _norm_status(value: Any) -> str:
    return str(value or "open").strip().lower()


def _sev_rank(value: str) -> int:
    text = _norm_sev(value)
    if len(text) >= 2 and text[0] == "P" and text[1:].isdigit():
        return int(text[1:])
    return 99


def open_defect(
    receipt: dict[str, Any],
    *,
    defect_id: str,
    severity: str,
    summary: str,
    audit_path: Path | str,
    actor: str,
    ts: str | None = None,
) -> dict[str, Any]:
    stamp = ts or utc_now()
    defect = {
        "id": defect_id,
        "severity": severity,
        "opened_severity": severity,
        "status": "open",
        "opened_status": "open",
        "summary": summary,
    }
    receipt.setdefault("defects", []).append(defect)
    append_audit(
        audit_path,
        {
            "action": "open",
            "actor": actor,
            "defect_id": defect_id,
            "reason": summary,
            "to_severity": severity,
            "to_status": "open",
            "ts": stamp,
        },
    )
    return defect


def resolve_defect(
    receipt: dict[str, Any],
    *,
    defect_id: str,
    reason: str,
    actor: str,
    audit_path: Path | str,
    status: str = "closed",
    ts: str | None = None,
) -> dict[str, Any]:
    stamp = ts or utc_now()
    defect = _find_defect(receipt, defect_id)
    from_status = defect.get("status") or "open"
    defect["status"] = status
    append_audit(
        audit_path,
        {
            "action": "resolve",
            "actor": actor,
            "defect_id": defect_id,
            "from_status": from_status,
            "reason": reason,
            "to_status": status,
            "ts": stamp,
        },
    )
    return defect


def _find_defect(receipt: dict[str, Any], defect_id: str) -> dict[str, Any]:
    for row in receipt.get("defects") or []:
        if isinstance(row, dict) and row.get("id") == defect_id:
            return row
    raise GateError(f"defect {defect_id!r} is not on the ledger")


def downgrade(
    receipt: dict[str, Any],
    *,
    defect_id: str,
    to_severity: str,
    reason: str,
    actor: str,
    audit_path: Path | str,
    ts: str | None = None,
) -> dict[str, Any]:
    if not str(reason or "").strip():
        raise GateError(
            "a severity downgrade needs a non-blank reason; silent P1->P2 is refused"
        )
    stamp = ts or utc_now()
    defect = _find_defect(receipt, defect_id)
    from_severity = defect.get("severity")
    from_status = defect.get("status") or "open"
    payload = {
        "action": "downgrade",
        "actor": actor,
        "defect_id": defect_id,
        "from_severity": from_severity,
        "from_status": from_status,
        "reason": reason,
        "to_severity": to_severity,
        "to_status": from_status,
        "ts": stamp,
    }
    append_audit(audit_path, payload)
    defect["severity"] = to_severity
    return payload


def naive_c10(receipt: dict[str, Any]) -> dict[str, Any]:
    """Ledger-field-only C10. Silent P1->P2 fools this control."""
    named: list[str] = []
    for row in receipt.get("defects") or []:
        if not isinstance(row, dict):
            continue
        sev = _norm_sev(row.get("severity") or row.get("priority"))
        status = _norm_status(row.get("status"))
        if sev in BLOCKING_SEVERITIES and status in OPEN_STATUSES:
            named.append(str(row.get("id") or ""))
    named = [n for n in named if n]
    return {
        "satisfied": not named,
        "named_defect_ids": named,
        "basis": (
            f"open P0/P1 defect(s): {named!r}"
            if named
            else "ledger has no open P0/P1"
        ),
        "text": CONDITION_TEXT,
    }


def _replay_one(
    defect: dict[str, Any], audit_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    did = str(defect.get("id") or "")
    rows = [r for r in audit_rows if isinstance(r, dict) and r.get("defect_id") == did]
    effective_severity = _norm_sev(
        defect.get("opened_severity") or defect.get("severity")
    )
    effective_status = _norm_status(defect.get("opened_status") or "open")
    for row in rows:
        action = str(row.get("action") or "").strip().lower()
        if action in {"open", "opened"}:
            effective_severity = _norm_sev(
                row.get("to_severity") or row.get("severity") or effective_severity
            )
            effective_status = _norm_status(
                row.get("to_status") or row.get("status") or "open"
            )
        elif action == "downgrade":
            effective_severity = _norm_sev(
                row.get("to_severity") or effective_severity
            )
            if row.get("to_status") is not None:
                effective_status = _norm_status(row.get("to_status"))
        elif action in {"resolve", "resolved", "close", "closed"}:
            effective_status = _norm_status(
                row.get("to_status") or row.get("status") or "closed"
            )
    claimed_severity = _norm_sev(defect.get("severity") or defect.get("priority"))
    claimed_status = _norm_status(defect.get("status"))
    unauthorized = _sev_rank(claimed_severity) > _sev_rank(effective_severity)
    open_blocking = (
        effective_status in OPEN_STATUSES and effective_severity in BLOCKING_SEVERITIES
    )
    return {
        "id": did,
        "claimed_severity": claimed_severity or str(defect.get("severity") or ""),
        "claimed_status": claimed_status,
        "effective_severity": effective_severity,
        "effective_status": effective_status,
        "unauthorized_downgrade": unauthorized,
        "blocks": bool(open_blocking or unauthorized),
    }


def evaluate_c10(
    receipt: dict[str, Any], audit_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    replayed = [
        _replay_one(row, audit_rows)
        for row in (receipt.get("defects") or [])
        if isinstance(row, dict)
    ]
    open_ids = [
        r["id"]
        for r in replayed
        if r["effective_status"] in OPEN_STATUSES
        and r["effective_severity"] in BLOCKING_SEVERITIES
    ]
    unauth_ids = [r["id"] for r in replayed if r["unauthorized_downgrade"]]
    named = []
    for did in open_ids + unauth_ids:
        if did and did not in named:
            named.append(did)
    satisfied = not named
    parts: list[str] = []
    if open_ids:
        parts.append(f"open P0/P1 defect(s): {open_ids!r}")
    if unauth_ids:
        parts.append(f"unauthorized severity mutation without audit: {unauth_ids!r}")
    if satisfied:
        basis = f"{len(replayed)} defect(s) recorded, none open at P0/P1"
    else:
        basis = "; ".join(parts)
    return {
        "n": CONDITION_ID,
        "text": CONDITION_TEXT,
        "satisfied": satisfied,
        "outcome": "SATISFIED" if satisfied else "UNSATISFIED",
        "basis": basis,
        "reason": basis,
        "named_defect_ids": named,
        "unauthorized_downgrade_ids": unauth_ids,
        "replayed": replayed,
        "failing_condition_id": None if satisfied else CONDITION_ID,
    }


def _cond(n: int, satisfied: bool, basis: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "n": n,
        "text": CONDITION_TEXTS[n],
        "satisfied": satisfied,
        "outcome": "SATISFIED" if satisfied else "UNSATISFIED",
        "basis": basis,
    }
    if extra:
        row.update(extra)
    return row


def _is_anchored(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if str(item.get("anchor") or "").strip():
        return True
    return bool(item.get("path")) and item.get("line") is not None


def evaluate_other(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    state = str(receipt.get("state") or "")
    c1_ok = state.upper() in COMPLETION_STATES
    artifacts = [a for a in (receipt.get("artifacts") or []) if isinstance(a, dict)]
    existing = [a for a in artifacts if a.get("exists") is True]
    c2_ok = bool(existing)
    threshold = int(receipt.get("min_bytes_threshold") or DEFAULT_MIN_BYTES)
    c3_ok = bool(existing) and all(
        int(a.get("bytes") or 0) >= threshold for a in existing
    )
    c4_ok = all(
        str(receipt.get(key) or "").strip() for key in ("unit_id", "state", "sentinel")
    )
    sentinel = str(receipt.get("sentinel") or "")
    c5_ok = bool(sentinel) and not sentinel.upper().startswith("FAILED")
    evidence = [e for e in (receipt.get("evidence") or []) if _is_anchored(e)]
    c6_ok = len(evidence) >= 1
    tests = [
        t
        for t in (receipt.get("tests") or [])
        if isinstance(t, dict) and str(t.get("result") or "").upper() == "PASS"
    ]
    c7_ok = bool(tests)
    controls = [
        c
        for c in (receipt.get("negative_controls") or [])
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
    ]
    both = [c for c in controls if str(c.get("kind") or "") == "both-states"]
    c8_ok = bool(both or controls)
    reviewer = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
    c9_ok = (
        str(reviewer.get("verdict") or "").strip().upper() == "PASS"
        and reviewer.get("independent") is True
    )
    reg = (
        receipt.get("manifest_registration")
        if isinstance(receipt.get("manifest_registration"), dict)
        else {}
    )
    c11_ok = reg.get("registered") is True
    consumers = [
        c
        for c in (receipt.get("downstream_consumers") or [])
        if isinstance(c, dict)
        and c.get("executed") is True
        and c.get("read_ok") is True
    ]
    c12_ok = bool(consumers)
    n_both = len(both) if both else len(controls)
    return [
        _cond(
            1,
            c1_ok,
            f"state={state} is a completion terminal"
            if c1_ok
            else f"state={state} is not a completion terminal",
        ),
        _cond(2, c2_ok, f"{len(existing)} artifact(s) claimed exists=true"),
        _cond(
            3,
            c3_ok,
            f"all artifact bytes >= {threshold}"
            if c3_ok
            else f"an artifact is below {threshold} bytes",
        ),
        _cond(
            4,
            c4_ok,
            "required keys present (unit_id/state/sentinel)"
            if c4_ok
            else "missing unit_id/state/sentinel",
        ),
        _cond(
            5,
            c5_ok,
            "sentinel present and not a failure marker"
            if c5_ok
            else "sentinel absent or is a failure marker",
        ),
        _cond(6, c6_ok, f"{len(evidence)} anchored evidence item(s)"),
        _cond(7, c7_ok, f"{len(tests)} test(s) PASS"),
        _cond(8, c8_ok, f"{n_both} both-states control(s)"),
        _cond(
            9,
            c9_ok,
            "reviewer verdict='PASS' independent=True"
            if c9_ok
            else "independent reviewer is not PASS",
        ),
        _cond(
            11,
            c11_ok,
            "manifest_registration.registered is true"
            if c11_ok
            else "manifest_registration.registered is not true",
        ),
        _cond(
            12,
            c12_ok,
            f"{len(consumers)} consumer(s) executed and read the artifact",
        ),
    ]


def evaluate(receipt: dict[str, Any], audit_rows: list[dict[str, Any]]) -> dict[str, Any]:
    c10 = evaluate_c10(receipt, audit_rows)
    others = evaluate_other(receipt)
    conditions: list[dict[str, Any]] = []
    inserted = False
    for row in others:
        if row["n"] > CONDITION_ID and not inserted:
            conditions.append(
                {
                    "n": CONDITION_ID,
                    "text": CONDITION_TEXT,
                    "satisfied": c10["satisfied"],
                    "outcome": c10["outcome"],
                    "basis": c10["basis"],
                    "named_defect_ids": c10["named_defect_ids"],
                }
            )
            inserted = True
        conditions.append(row)
    if not inserted:
        conditions.append(
            {
                "n": CONDITION_ID,
                "text": CONDITION_TEXT,
                "satisfied": c10["satisfied"],
                "outcome": c10["outcome"],
                "basis": c10["basis"],
                "named_defect_ids": c10["named_defect_ids"],
            }
        )
    unsatisfied = [row["n"] for row in conditions if not row["satisfied"]]
    other_11_unsatisfied = [n for n in unsatisfied if n != CONDITION_ID]
    failing = unsatisfied[0] if unsatisfied else None
    all_ok = not unsatisfied
    claimed = str(receipt.get("state") or "")
    return {
        "c10": c10,
        "can_reach_success": all_ok,
        "claimed_state": claimed,
        "conditions": conditions,
        "failing_condition_id": failing,
        "named_defect_ids": c10["named_defect_ids"],
        "other_11_satisfied": not other_11_unsatisfied,
        "other_11_unsatisfied": other_11_unsatisfied,
        "reason": c10["basis"] if not c10["satisfied"] else "all 12 conditions satisfied",
        "state": "SUCCESS" if all_ok else "FAILED",
        "unauthorized_downgrade_ids": c10["unauthorized_downgrade_ids"],
        "verdict": "SUCCESS" if all_ok else "FAILED",
    }


def transcript_line(doc: dict[str, Any]) -> str:
    c10 = doc["c10"]
    other = doc["other_11_satisfied"]
    if c10["satisfied"] and doc["can_reach_success"]:
        return (
            "PASS:condition-10 failing-condition-id=none "
            f"{c10['basis']} verdict=SUCCESS"
        )
    fail_id = doc.get("failing_condition_id") or CONDITION_ID
    named = doc.get("named_defect_ids") or []
    return (
        f"FAILED:condition-10 failing-condition-id={fail_id} "
        f"{c10['basis']} named={named!r} other_11_satisfied={other}"
    )


def cmd_evaluate(receipt_path: Path, audit_path: Path) -> int:
    receipt = load_json(receipt_path)
    audit_rows = load_audit(audit_path)
    doc = evaluate(receipt, audit_rows)
    print(json.dumps(doc, indent=2, sort_keys=True, default=str))
    print(transcript_line(doc))
    return 0 if doc["can_reach_success"] else 1


def cmd_downgrade(
    receipt_path: Path,
    audit_path: Path,
    defect_id: str,
    to_severity: str,
    reason: str,
    actor: str,
    now: str | None,
) -> int:
    try:
        receipt = load_json(receipt_path)
        payload = downgrade(
            receipt,
            defect_id=defect_id,
            to_severity=to_severity,
            reason=reason,
            actor=actor,
            audit_path=audit_path,
            ts=now,
        )
        save_json(receipt_path, receipt)
    except GateError as exc:
        print(f"FAILED:c10-downgrade {exc}")
        return 1
    print(
        "SUCCESS:c10-downgrade "
        f"{defect_id} {payload.get('from_severity')}->{payload.get('to_severity')} "
        "audit_appended=true"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Condition 10 defect-audit gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="evaluate a candidate against C10 + the other 11")
    ev.add_argument("--receipt", required=True)
    ev.add_argument("--audit", required=True)
    dg = sub.add_parser("downgrade", help="audited severity downgrade (append-only JSONL)")
    dg.add_argument("--receipt", required=True)
    dg.add_argument("--audit", required=True)
    dg.add_argument("--defect-id", required=True)
    dg.add_argument("--to", required=True)
    dg.add_argument("--reason", required=True)
    dg.add_argument("--actor", required=True)
    dg.add_argument("--now", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "evaluate":
        return cmd_evaluate(Path(args.receipt), Path(args.audit))
    if args.cmd == "downgrade":
        return cmd_downgrade(
            Path(args.receipt),
            Path(args.audit),
            args.defect_id,
            args.to,
            args.reason,
            args.actor,
            args.now,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

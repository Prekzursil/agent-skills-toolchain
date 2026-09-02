#!/usr/bin/env python3
"""Local-python completion-predicate reducer (TST-0330 subject A).

Independent sequential implementation of the 12 unit-completion conditions.
Exit code zero is never consulted. A digest or a path string is not existence.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

# Census marker: implementation census matches this token, not prose mentions.
TST0330_REDUCER_ROLE = "local-python"

TERMINAL = frozenset(
    {"SUCCESS", "FAILED", "BLOCKED", "TIMEOUT", "SEVERED", "PARTIAL"}
)
CONDITION_IDS = tuple(f"C{i:02d}" for i in range(1, 13))
REASONS = {
    "PARSE": "torn or non-object JSON",
    "C01": "state is not a valid terminal",
    "C02": "expected artifact does not exist",
    "C03": "artifact empty or below min_bytes_threshold",
    "C04": "artifact does not parse",
    "C05": "required sentinel missing",
    "C06": "required evidence anchors missing",
    "C07": "required tests did not pass",
    "C08": "negative controls did not fail as expected",
    "C09": "independent reviewer status is not PASS",
    "C10": "unresolved P0/P1 defect attached",
    "C11": "output not registered in artifact manifest",
    "C12": "downstream consumers cannot read it",
    "COMPLETE": "all twelve conditions passed",
}


def canon(verdict: dict[str, Any]) -> str:
    payload = {
        "failing_condition_id": verdict.get("failing_condition_id"),
        "reason": verdict.get("reason"),
        "verdict": verdict.get("verdict"),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _malformed() -> dict[str, Any]:
    return {
        "failing_condition_id": "PARSE",
        "reason": REASONS["PARSE"],
        "verdict": "MALFORMED",
    }


def _c01(obj: dict[str, Any]) -> bool:
    state = obj.get("state")
    return isinstance(state, str) and state in TERMINAL


def _c02(obj: dict[str, Any]) -> bool:
    art = obj.get("artifact")
    return isinstance(art, dict) and art.get("exists") is True


def _c03(obj: dict[str, Any]) -> bool:
    art = obj.get("artifact") if isinstance(obj.get("artifact"), dict) else {}
    try:
        nbytes = int(art.get("bytes") if art.get("bytes") is not None else 0)
    except (TypeError, ValueError):
        return False
    floor = obj.get("min_bytes_threshold")
    if floor is None:
        floor = 128
    try:
        floor_i = int(floor)
    except (TypeError, ValueError):
        return False
    return nbytes > 0 and nbytes >= floor_i


def _c04(obj: dict[str, Any]) -> bool:
    art = obj.get("artifact") if isinstance(obj.get("artifact"), dict) else {}
    body = art.get("body")
    if isinstance(body, str):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict)
    return art.get("parse_ok") is True


def _c05(obj: dict[str, Any]) -> bool:
    uid = obj.get("unit_id")
    sent = obj.get("sentinel")
    return (
        isinstance(uid, str)
        and bool(uid)
        and isinstance(sent, str)
        and uid in sent
    )


def _c06(obj: dict[str, Any]) -> bool:
    ev = obj.get("evidence")
    if not isinstance(ev, list) or len(ev) < 2:
        return False
    for item in ev:
        if not isinstance(item, dict):
            return False
        anchor = item.get("anchor")
        if not isinstance(anchor, str) or not anchor.strip():
            return False
    return True


def _c07(obj: dict[str, Any]) -> bool:
    tests = obj.get("tests")
    if not isinstance(tests, list) or not tests:
        return False
    return all(isinstance(t, dict) and t.get("result") == "PASS" for t in tests)


def _c08(obj: dict[str, Any]) -> bool:
    ncs = obj.get("negative_controls")
    if not isinstance(ncs, list) or not ncs:
        return False
    return any(
        isinstance(c, dict) and c.get("fired_on_bad_state") is True for c in ncs
    )


def _c09(obj: dict[str, Any]) -> bool:
    rev = obj.get("reviewer")
    return isinstance(rev, dict) and rev.get("verdict") == "PASS"


def _c10(obj: dict[str, Any]) -> bool:
    defs = obj.get("defects")
    if defs is None:
        defs = []
    if not isinstance(defs, list):
        return False
    for item in defs:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity") or "").upper()
        st = str(item.get("status") or "").lower()
        if sev in {"P0", "P1"} and st in {"open", "unresolved"}:
            return False
    return True


def _c11(obj: dict[str, Any]) -> bool:
    if obj.get("manifest_registered") is True:
        return True
    man = obj.get("manifest")
    return isinstance(man, dict) and man.get("registered") is True


def _c12(obj: dict[str, Any]) -> bool:
    ds = obj.get("downstream")
    if not isinstance(ds, list) or not ds:
        return False
    return all(
        isinstance(x, dict)
        and x.get("read_ok") is True
        and x.get("executed") is True
        for x in ds
    )


CHECKS = (
    ("C01", _c01),
    ("C02", _c02),
    ("C03", _c03),
    ("C04", _c04),
    ("C05", _c05),
    ("C06", _c06),
    ("C07", _c07),
    ("C08", _c08),
    ("C09", _c09),
    ("C10", _c10),
    ("C11", _c11),
    ("C12", _c12),
)


def evaluate_object(obj: Any, skip: frozenset[str] | set[str] | None = None) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return _malformed()
    skipped = skip or frozenset()
    # exit_code is intentionally unread: exit zero is never success.
    fails: list[str] = []
    for cid, fn in CHECKS:
        if cid in skipped:
            continue
        if not fn(obj):
            fails.append(cid)
    if not fails:
        return {
            "failing_condition_id": None,
            "reason": REASONS["COMPLETE"],
            "verdict": "COMPLETE",
        }
    first = fails[0]
    return {
        "failing_condition_id": first,
        "reason": REASONS[first],
        "verdict": "INCOMPLETE",
    }


def evaluate_row(row: dict[str, Any], skip: frozenset[str] | set[str] | None = None) -> dict[str, Any]:
    kind = row.get("kind")
    if kind == "raw":
        raw = row.get("raw")
        if not isinstance(raw, str):
            return _malformed()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return _malformed()
        return evaluate_object(obj, skip=skip)
    if kind == "object":
        return evaluate_object(row.get("state"), skip=skip)
    return _malformed()


def evaluate_corpus(rows: list[dict[str, Any]], skip: frozenset[str] | set[str] | None = None) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        verdict = evaluate_row(row, skip=skip)
        out.append(
            {
                "id": row.get("id"),
                "canonical": canon(verdict),
                "verdict": verdict,
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", action="append", default=[])
    args = parser.parse_args()
    payload = sys.stdin.read()
    rows = json.loads(payload)
    skip = frozenset(args.skip)
    print(json.dumps(evaluate_corpus(rows, skip=skip), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 1: planted self-review is detected; missing reviewer_id is a VIOLATION.

Known-good corpus is silent (empty intersection, no cycles, no missing fields).
A skip-mutant that drops receipts without reviewer_id is the failure class
missing-reviewer-field-skipped and must disagree with the live detector.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402
import fixtures as F  # noqa: E402

REPO = A.REPO
ART = REPO / "command-center" / "receipts" / "SYN-0037.json"
UNIT = "SYN-0037"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0037-probe1 {msg}")
    return 1


def ast_missing_is_not_a_skip() -> None:
    """Refuse a detector that continues past a missing reviewer without classifying it."""
    text = (HERE / "audit.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if "audit_records" not in names or "missing_classification" not in names:
        raise SystemExit("audit_records or missing_classification missing")
    if "missing_is_violation" not in text:
        raise SystemExit("audit_records does not gate missing_is_violation")
    if "missing-reviewer-field" not in text:
        raise SystemExit("audit.py never names missing-reviewer-field")
    if "missing-reviewer-field-skipped" not in text:
        raise SystemExit("skip failure class not named")


def main() -> int:
    ast_missing_is_not_a_skip()

    good = A.audit_records(F.known_good(), missing_is_violation=True)
    if good["self_reviews"] or good["cycles"] or good["missing_field_count"] != 0:
        return fail(f"known-good not silent {json.dumps(good, sort_keys=True)[:1500]}")
    if good["author_reviewer_intersection"]:
        return fail(f"known-good intersection {good['author_reviewer_intersection']}")
    if not good["acyclic"] or good["kahn_cyclic"]:
        return fail("known-good chain not acyclic")

    planted = A.audit_records(F.planted_self_review(), missing_is_violation=True)
    agents = {r["agent_id"] for r in planted["self_reviews"]}
    if "agent-alpha" not in agents:
        return fail(f"planted self-review not detected {planted['self_reviews']}")
    if planted["missing_field_count"] != 0:
        return fail("self-review plant should not be a missing-field")

    miss = A.audit_records(F.planted_missing_reviewer(), missing_is_violation=True)
    if miss["missing_field_count"] < 1:
        return fail("missing reviewer_id was skipped rather than counted")
    classes = {r["classification"] for r in miss["missing_field_receipts"]}
    if A.MISSING_REVIEWER not in classes:
        return fail(f"missing reviewer classified as {classes}")
    skip_mutant = A.audit_records(F.planted_missing_reviewer(), missing_is_violation=False)
    if skip_mutant["missing_field_count"] >= miss["missing_field_count"]:
        return fail("skip mutant did not under-count missing reviewer")
    if skip_mutant["skipped_count"] < 1:
        return fail("skip mutant did not record skipped-missing-reviewer")

    live = A.audit_live(exclude_self=False)
    if live["skipped_count"] != 0:
        return fail("live detector skipped a missing field")

    receipt_ok = None
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        if "SUCCESS:SYN-0037" not in text:
            return fail("receipt sentinel-absent")
        body = A.published_payload(doc)
        planted_doc = body.get("planted_violations") or {}
        if planted_doc.get("self_review_detected") is not True:
            return fail("receipt did not publish planted self-review detection")
        if planted_doc.get("missing_reviewer_is_violation") is not True:
            return fail("receipt did not publish missing-reviewer-as-violation")
        receipt_ok = True

    payload = {
        "probe": "probe1-planted-self-review",
        "unit_id": UNIT,
        "known_good_silent": True,
        "planted_self_review_detected": True,
        "planted_agent": "agent-alpha",
        "missing_reviewer_is_violation": True,
        "skip_mutant_undercounts": True,
        "live_missing_field_count": live["missing_field_count"],
        "live_self_reviews": live["self_reviews"],
        "receipt_checked": receipt_ok,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:SYN-0037-probe1 planted self-review detected; missing reviewer is a violation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

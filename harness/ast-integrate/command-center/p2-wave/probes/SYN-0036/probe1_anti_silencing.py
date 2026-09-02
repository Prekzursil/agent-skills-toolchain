#!/usr/bin/env python3
"""Probe 1: anti-silencing guard — weighting does not remove or downrank findings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from anti_silencing import apply_weights, naive_weight_rank, severity_rank  # noqa: E402
from scoring import load_frame, score_frame  # noqa: E402

UNIT = "SYN-0036"
ART = REPO / "command-center/receipts/SYN-0036.json"
SCHEMA = REPO / "command-center/schema/reliability-weighting.schema.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print("FAILED:%s-probe1 %s" % (UNIT, msg))
    return 1


def main() -> int:
    scored = score_frame()
    frame = load_frame()
    findings = list(frame["findings"])
    weights = dict(scored["weights"])
    # INSUFFICIENT-N producers have no weight; naive rank would sink them
    for row in scored["producers"]:
        weights.setdefault(row["producer_id"], None)

    guard = apply_weights(findings, weights)
    print(
        "severity_order=%s naive_weight_order=%s would_downrank=%s"
        % (guard["ranked_ids"], guard["naive_weight_order"], guard["naive_would_downrank"])
    )
    if not guard["passed"]:
        return fail("guard failed passed=%s removed=%s" % (guard["passed"], guard["removed"]))
    if guard["removed"]:
        return fail("findings removed %s" % guard["removed"])
    if guard["downranked_by_weight"]:
        return fail("findings downranked %s" % guard["downranked_by_weight"])
    if "F-001" not in guard["ranked_ids"]:
        return fail("planted low-weight P0 F-001 missing")
    if guard["ranked_ids"][0] != "F-001":
        return fail("F-001 lost severity rank, now %s" % guard["ranked_ids"])
    if "F-001" not in guard["naive_would_downrank"]:
        return fail("naive weight-rank did not downrank F-001; control is silent")
    if severity_rank(findings) != guard["ranked_ids"]:
        return fail("guarded rank != severity rank")
    naive = naive_weight_rank(findings, weights)
    if naive[0] == "F-001":
        return fail("naive weight rank still leads with F-001; detector not discriminating")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail("self-declared %s" % doc.get("state"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail("schema-invalid %s" % errs[0].message)
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            return fail("schema accepted garbage")
    ag = doc.get("anti_silencing_guard") or {}
    if ag.get("passed") is not True:
        return fail("artifact guard.passed is not true")
    if ag.get("removed"):
        return fail("artifact reports removals")
    after = list(ag.get("findings_after") or [])
    if "F-001" not in after:
        return fail("artifact dropped F-001")
    if set(ag.get("findings_before") or []) != set(after):
        return fail("artifact finding set changed")

    summary = {
        "f001_kept": True,
        "naive_would_downrank_f001": True,
        "pass": True,
        "probe": "probe1-anti-silencing",
        "removed": [],
        "unit_id": UNIT,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:%s-probe1 anti-silencing guard keeps F-001; naive weight-rank would sink it" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: planted inversion — P0 child under a P3 cause must be reported.

Independent of probe 1: injects the planted pair in-process and recomputes
max-child with the list-index reviewer, not the author RANK dict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    OUTPUT_REL,
    PLANTED_CAUSE,
    PLANTED_CHILD,
    SENTINEL,
)
from reconcile import reconcile  # noqa: E402
from reviewer import reviewer_delta, reviewer_max  # noqa: E402
from schema_util import report_body  # noqa: E402

RECEIPT = REPO / OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0004-probe2 {msg}")
    return 1


def planted_graph() -> dict:
    return {
        "id": "probe2-injected",
        "nodes": [
            {
                "id": PLANTED_CAUSE,
                "type": "CAUSE",
                "severity": "P3",
                "children": [PLANTED_CHILD],
            },
            {
                "id": PLANTED_CHILD,
                "type": "SYMPTOM",
                "severity": "P0",
                "claim_id": PLANTED_CHILD,
                "children": [],
            },
        ],
    }


def main() -> int:
    graph = planted_graph()
    result = reconcile(graph)
    row = next((r for r in result["rows"] if r["cause_id"] == PLANTED_CAUSE), None)
    if row is None:
        return fail("planted P3 cause missing from table")
    indep_max = reviewer_max(["P0"])
    indep_delta = reviewer_delta("P3", indep_max)
    print(
        f"planted recorded={row['recorded_severity']} "
        f"computed={row['computed_max_child_severity']} "
        f"verdict={row['verdict']} child={row['child_claim_id']} "
        f"reviewer_max={indep_max} reviewer_delta={indep_delta}"
    )
    if indep_max != "P0" or indep_delta <= 0:
        return fail("independent reviewer did not see P0 > P3")
    if row["computed_max_child_severity"] != indep_max:
        return fail("author computed_max disagrees with reviewer list-index max")
    if row["delta"] != indep_delta:
        return fail("author delta disagrees with reviewer")
    if row["verdict"] != "INVERSION":
        return fail(f"planted inversion verdict {row['verdict']}")
    if row["child_claim_id"] != PLANTED_CHILD:
        return fail("INVERSION did not name the planted P0 child")

    fixture = json.loads(
        (HERE / "fixtures" / "planted_inversion.json").read_text(encoding="utf-8")
    )
    fx = reconcile(fixture)
    fx_row = next(r for r in fx["rows"] if r["cause_id"] == PLANTED_CAUSE)
    if fx_row["verdict"] != "INVERSION":
        return fail("fixture inversion silent")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    body = report_body(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    by_id = {c["id"]: c for c in body.get("controls") or [] if isinstance(c, dict)}
    ctl = by_id.get("planted-inversion-p0-under-p3") or {}
    if ctl.get("result") != "FIRED":
        return fail("receipt planted-inversion control not FIRED")
    ctl_rows = ctl.get("rows") or []
    ctl_row = next((r for r in ctl_rows if r.get("cause_id") == PLANTED_CAUSE), None)
    if not ctl_row or ctl_row.get("verdict") != "INVERSION":
        return fail("receipt control table missing INVERSION row")
    if reviewer_delta(
        ctl_row["recorded_severity"], ctl_row.get("computed_max_child_severity")
    ) != ctl_row.get("delta"):
        return fail("receipt inversion row fails independent recompute")

    reviewers = body.get("reviewers") or []
    if len(reviewers) < 2:
        return fail("catalog requires two independent reviewers")
    if not all(r.get("independent") is True for r in reviewers if isinstance(r, dict)):
        return fail("a reviewer is not independent")
    if body.get("unexplained_deltas_open") != 0:
        return fail("unexplained_deltas_open != 0")

    print("planted-inversion=FIRED reviewer_list_index=match")
    print("SUCCESS:SYN-0004-probe2 planted-inversion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

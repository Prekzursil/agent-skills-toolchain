#!/usr/bin/env python3
"""Probe 2: detector control — three mismatched citations must all be caught.

Injections (copy of RES-0069, not the live file):
  1. quote absent from the resolved source
  2. snapshot/sha that does not resolve
  3. a real span from the source that is only topically adjacent

A miss means the reported support rate is an upper bound only.
A mutant detector that classifies every resolved quote as SUPPORTING must
fail to catch the topical injection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART_REL = (
    "command-center/research/evidence-quality/"
    "RES-0186-citation-audit-of-an-existing-report.json"
)
ART = A.REPO / ART_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0186-probe2 {msg}")
    return 1


def always_supporting_if_present(row: dict) -> str:
    """Mutant detector: any resolved span that is present is SUPPORTING."""
    res = A.resolve_snapshot(row)
    body = res.pop("_body", "")
    snippet = str(row.get("snippet") or "")
    if not res["resolved"]:
        return "UNRESOLVED"
    if snippet not in body:
        return "ASSERTION-ABSENT"
    return "SUPPORTING"


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    src = A.load_source()
    control = A.detector_control(src)
    print(
        f"injected={control['n_injected']} caught={control['n_caught']} "
        f"all_caught={control['all_caught']} "
        f"upper_bound={control['support_rate_is_upper_bound']}"
    )
    for hit in control["hits"]:
        print(
            f"  {hit['injection_id']} {hit['mode']} "
            f"expect={hit['expect_class']} got={hit['got_class']} "
            f"caught={hit['caught']}"
        )
    if control["n_injected"] != 3:
        return fail("expected 3 injections")
    if not control["all_caught"]:
        return fail(f"missed {control['missed']}")
    if control["support_rate_is_upper_bound"]:
        return fail("support rate marked upper-bound despite 3/3 catch")

    art_ctl = doc.get("detector_control") or {}
    if art_ctl.get("n_caught") != 3 or art_ctl.get("all_caught") is not True:
        return fail("artifact detector_control does not record 3/3 catch")

    # Confirm the topical span really is in the airflow snapshot, otherwise
    # injection 3 is just another quote-absent.
    mutant = A.apply_injections(src)
    topical_row = None
    for claim in mutant["claims"]:
        if claim.get("id") != "C-AIRFLOW-SENSOR":
            continue
        for src_row in claim.get("source_lineage") or []:
            if src_row.get("id") == "gh_airflow_sensor_tasksdk":
                topical_row = {
                    "snapshot": src_row.get("snapshot"),
                    "declared_sha256": src_row.get("sha256"),
                    "http_status": src_row.get("http_status"),
                    "final_url": src_row.get("final_url"),
                    "fetched_at": src_row.get("fetched_at"),
                    "snippet": src_row.get("snippet"),
                }
    if topical_row is None:
        return fail("topical injection row missing")
    res = A.resolve_snapshot(topical_row)
    body = res.get("_body") or ""
    if A.TOPICAL_SPAN not in body:
        return fail("topical span is not in the source; injection 3 is quote-absent")
    if topical_row["snippet"] != A.TOPICAL_SPAN:
        return fail("topical injection did not land")

    # Mutant detector: SUPPORTING whenever the quote is present. That misses
    # INJ-TOPICAL (and would miss CONTRADICTING on the live report).
    extracted = A.extract_citations(mutant)
    missed_by_mutant = []
    for inj in A.INJECTIONS:
        cid = f"{inj['claim_id']}#{inj['source_id']}"
        row = next(r for r in extracted if r["citation_id"] == cid)
        got = always_supporting_if_present(row)
        if got != inj["expect_class"]:
            missed_by_mutant.append(
                {"id": inj["id"], "expect": inj["expect_class"], "got": got}
            )
    print(f"always_supporting_mutant_missed={missed_by_mutant}")
    topical_miss = any(m["id"] == "INJ-TOPICAL" for m in missed_by_mutant)
    if not topical_miss:
        return fail("always-SUPPORTING mutant unexpectedly caught INJ-TOPICAL")

    live = A.audit_document(src)
    live_topical = [
        c["citation_id"]
        for c in live["citations"]
        if c["support_class"] == "TOPICALLY-ADJACENT"
    ]
    print(f"live_topical={live_topical}")
    if len(live_topical) != 2:
        return fail(f"expected 2 live topical citations, got {live_topical}")

    print("SUCCESS:RES-0186-probe2 three mismatched citations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

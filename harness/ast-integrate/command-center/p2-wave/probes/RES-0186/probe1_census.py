#!/usr/bin/env python3
"""Probe 1: full census (not a sample) and live rate recompute.

Re-walks RES-0069 claims[].source_lineage, re-hashes every snapshot, and
requires the delivered artifact fractions to match. A mutant that drops the
REFUTED-claim citations (or any one attachment) must go red. rails[] must
not be double-counted.
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
    print(f"FAILED:RES-0186-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = A.run_audit()
    rates = live["audit"]["rates"]
    src_n = len(A.extract_citations(A.load_source()))
    print(
        f"census n={rates['n_citations']} source_lineage={src_n} "
        f"resolve={rates['n_resolved']} assertion={rates['n_assertion_present']} "
        f"support={rates['n_supporting']}"
    )
    if rates["sampled"] or doc.get("sampled") is True:
        return fail("sampled=true is not a census")
    if rates["n_citations"] != src_n:
        return fail(f"census {rates['n_citations']} != source_lineage {src_n}")
    if src_n < 2:
        return fail("census too small")
    if rates["n_citations"] != 24:
        return fail(f"expected 24 attachments on RES-0069, got {rates['n_citations']}")
    if rates["double_counted_rails"]:
        return fail("rails[] was double-counted")
    if live["audit"]["rails_duplicate_count"] != src_n:
        return fail("rails duplicate count drifted from source_lineage")

    art_rates = doc.get("rates") or {}
    for key in (
        "n_citations",
        "n_resolved",
        "n_assertion_present",
        "n_supporting",
        "fraction_resolve",
        "fraction_assertion_present",
        "fraction_supporting",
    ):
        if art_rates.get(key) != rates[key]:
            return fail(f"artifact rates.{key} {art_rates.get(key)!r} != live {rates[key]!r}")

    art_rows = doc.get("citation_audit") or []
    if len(art_rows) != src_n:
        return fail(f"citation_audit rows {len(art_rows)} != {src_n}")
    live_ids = [c["citation_id"] for c in live["audit"]["citations"]]
    art_ids = [c.get("citation_id") for c in art_rows]
    if art_ids != live_ids:
        return fail("citation_audit order/id mismatch vs live census")

    confirmed = [
        r
        for r in live["audit"]["citations"]
        if r["claim_verdict"] == "CONFIRMED"
    ]
    refuted = [
        r
        for r in live["audit"]["citations"]
        if r["claim_verdict"] == "REFUTED"
    ]
    if len(confirmed) != 18 or len(refuted) != 6:
        return fail(f"unexpected split confirmed={len(confirmed)} refuted={len(refuted)}")

    # Mutant: drop REFUTED attachments. A census that only scored CONFIRMED
    # claims would report a higher support rate (16/18 vs 16/24).
    src = A.load_source()
    for claim in src["claims"]:
        if claim.get("verdict") == "REFUTED":
            claim["source_lineage"] = []
    dropped = A.audit_document(src)
    print(
        f"refuted_dropped n={dropped['rates']['n_citations']} "
        f"support={dropped['rates']['n_supporting']}/"
        f"{dropped['rates']['n_citations']} "
        f"rate={dropped['rates']['fraction_supporting']}"
    )
    if dropped["rates"]["n_citations"] >= src_n:
        return fail("dropping REFUTED lineage did not shrink the census")
    if dropped["rates"]["fraction_supporting"] <= rates["fraction_supporting"]:
        return fail("CONFIRMED-only mutant did not inflate support rate")

    # Mutant: omit one CONFIRMED attachment.
    src2 = A.load_source()
    for claim in src2["claims"]:
        if claim.get("id") == "C-AZURE-UNTIL" and claim.get("source_lineage"):
            claim["source_lineage"] = claim["source_lineage"][1:]
            break
    one_short = A.audit_document(src2)
    if one_short["rates"]["n_citations"] != src_n - 1:
        return fail("single-drop mutant census wrong")

    if "SUCCESS:RES-0186" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    print("SUCCESS:RES-0186-probe1 full census rates match live recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

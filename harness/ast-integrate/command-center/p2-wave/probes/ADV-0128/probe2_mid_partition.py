#!/usr/bin/env python3
"""Probe 2: mid-operation partition, partial survival, and resume."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0128-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0128-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0128-probe2 self-declared {st}")
        return 1

    live = H.run_partition_campaign()
    c = live["controls"]
    if not c["contract_partial_survives_partition"]:
        print("FAILED:ADV-0128-probe2 contract lost step-1 across the stall")
        return 1
    if not c["contract_resume_completes_without_dropping_step1"]:
        print("FAILED:ADV-0128-probe2 contract resume dropped step-1")
        return 1
    if not c["naive_loses_partial_on_partition"]:
        print("FAILED:ADV-0128-probe2 naive did not lose the partial artifact")
        return 1
    if not c["fixture_loopback_only"]:
        print("FAILED:ADV-0128-probe2 partition was not loopback-only")
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or not reviewer.get("independent"):
        print("FAILED:ADV-0128-probe2 reviewer block", reviewer)
        return 1
    fp = H.fingerprints()
    if not fp["source"] or not fp["verifier"] or fp["source"] == fp["verifier"]:
        print("FAILED:ADV-0128-probe2 probe fingerprints identical")
        return 1

    art_part = {
        t["id"]: t.get("partition_naive_lost_partial")
        for t in (doc.get("enumerated_targets") or doc.get("enumerated_targets") or [])
        if t.get("id") in H.PATHS
    }
    live_lost = {
        r["path_id"]: r["after_cut_naive_artifact_missing"] for r in live["rows"]
    }
    if art_part != live_lost:
        print("FAILED:ADV-0128-probe2 artifact/live partition mismatch")
        print(art_part, live_lost)
        return 1
    for path_id, lost in live_lost.items():
        if not lost:
            print(f"FAILED:ADV-0128-probe2 {path_id} naive partial survived")
            return 1

    production = H.audit_production()
    prod_gap = (not production["has_http_client"]) or (
        not production["has_labelled_offline_cache"]
    )
    art_prod = next(
        (
            t
            for t in (doc.get("enumerated_targets") or doc.get("enumerated_targets") or [])
            if t.get("id") == "production-estate"
        ),
        None,
    )
    if not art_prod or art_prod.get("verdict") not in LEGAL:
        print("FAILED:ADV-0128-probe2 production target missing")
        return 1
    if prod_gap and art_prod.get("verdict") != "CONFIRMED":
        print("FAILED:ADV-0128-probe2 production gap not CONFIRMED")
        return 1

    summary = {
        "probe": "probe2-mid-partition",
        "unit_id": H.UNIT,
        "contract_kept_step1": True,
        "contract_resume_ok": True,
        "naive_lost_partial": live_lost,
        "fixture_loopback_only": True,
        "production_gap": prod_gap,
        "source_fp": fp["source"][:16],
        "verifier_fp": fp["verifier"][:16],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:ADV-0128-probe2 mid-partition lost naive partial; contract resumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

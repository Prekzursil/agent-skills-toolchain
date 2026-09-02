#!/usr/bin/env python3
"""Probe 2: independent template expansion + boolean ranker recount.

Fresh-context refuter: defaults to REFUTED unless live false-claim hits exist,
true controls stay silent, and the artifact's BM25 counts recompute.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from compare import claims_sha256, run_comparison  # noqa: E402
from generator import generate_independent  # noqa: E402

ART = (
    REPO
    / "command-center/research/evidence-quality"
    / "RES-0147-disconfirming-query-generation.json"
)
RAW = HERE / "probe2-independent.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0147-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:RES-0147" not in text:
        return fail("sentinel missing")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    bm25 = run_comparison(generator="v1", ranker="bm25")
    indep = run_comparison(generator="v2", ranker="boolean")
    raw_rows = generate_independent("The Moon is made of cheese.")
    raw_qs = [r["query"].lower() for r in raw_rows]
    families = {r["family"] for r in raw_rows}

    s1 = bm25["summary"]
    s2 = indep["summary"]
    meas = (doc.get("measurements") or {}).get("bm25_v1") or {}
    meas2 = (doc.get("measurements") or {}).get("boolean_v2") or {}

    if s1["generated_surface_count_false_claims"] < 1:
        print("REFUTED: insufficient positive retrieval on false claims")
        return fail("default-refuted-no-sensitivity")
    if s1["negative_control_generated_hits"] != 0:
        return fail("true-controls-not-silent-on-bm25")
    if s2["negative_control_generated_hits"] != 0:
        return fail("true-controls-not-silent-on-boolean")
    if s2["generated_surface_count_false_claims"] < 1:
        return fail("independent-ranker-all-silent")
    if int(meas.get("generated_surface_count_false_claims", -1)) != s1[
        "generated_surface_count_false_claims"
    ]:
        return fail("artifact-bm25-drift")
    if int(meas2.get("generated_surface_count_false_claims", -1)) != s2[
        "generated_surface_count_false_claims"
    ]:
        return fail("artifact-boolean-drift")
    if str(doc.get("claims_sha256") or "") != claims_sha256():
        return fail("claims-sha-mismatch")
    if not any("moon" in q for q in raw_qs):
        return fail("independent-raw-claim-missing-subject")
    if "issue_tracker" not in families or "negation" not in families:
        return fail(f"independent-families {sorted(families)}")

    higher_stable = bool(s1["higher_rate"] and s2["higher_rate"])
    report = {
        "probe": "probe2-independent",
        "unit_id": "RES-0147",
        "bm25": s1,
        "boolean_v2": s2,
        "higher_rate_stable_across_rankers": higher_stable,
        "raw_claim_query_count": len(raw_rows),
        "reviewer_verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "default_without_evidence": "REFUTED",
    }
    RAW.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2)[:4000])
    print(
        "SUCCESS:RES-0147-probe2 independent boolean recount "
        f"false_hits={s2['generated_surface_count_false_claims']}/"
        f"{s2['baseline_surface_count_false_claims']} "
        f"higher_stable={higher_stable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

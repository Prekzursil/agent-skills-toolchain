#!/usr/bin/env python3
"""Probe 2: republication collapse vs URL counting (different signal than probe 1).

Probe 1 reads the cite-edge on C-CIRCULAR-PLANT. This probe reads origin_id
collapse on C-REPUB-PLANT and shared-upstream collapse on C-DIGEST-HOST, and
checks the independent-publisher control still passes. It does not import
probe1 or read probe1 output.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import EXPECTED_DIGEST, coreutils_digest, hashlib_digest  # noqa: E402
from audit import audit  # noqa: E402
from lineage import (  # noqa: E402
    INDEPENDENT,
    LABEL_INDEP,
    LABEL_SINGLE,
    SINGLE,
    classify_claim,
    naive_url_count_independent,
)

ART = REPO / "command-center/confirmation/CNF-0063-source-corroboration.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0063-probe2 {msg}")
    return 1


def main() -> int:
    h = hashlib_digest()
    c = coreutils_digest()
    if h != c or h != EXPECTED_DIGEST:
        return fail(f"live digest mismatch hashlib={h} coreutils={c}")

    live = audit()
    by_live = {r["id"]: r for r in live["claims"]}
    repub = by_live["C-REPUB-PLANT"]
    indep = by_live["C-INDEP-PLANT"]
    digest = by_live["C-DIGEST-HOST"]
    sha_w = by_live["C-SHA256-WIDTH"]

    if repub["verdict"] != SINGLE or repub["label"] != LABEL_SINGLE:
        return fail("republication plant not SINGLE-SOURCED")
    if not repub["lineage_trace"]["republication_groups"]:
        return fail("republication groups empty")
    if repub["lineage_trace"]["url_count"] < 2:
        return fail("republication plant needs two URLs")
    if not naive_url_count_independent(repub["sources"]):
        return fail("URL-count would not falsely corroborate the reprint")
    if repub["lineage_trace"]["origin_count"] != 1:
        return fail(f"republication origin_count={repub['lineage_trace']['origin_count']}")

    if indep["verdict"] != INDEPENDENT or indep["label"] != LABEL_INDEP:
        return fail("independent plant not corroborated")
    second = indep["lineage_trace"].get("second_source") or {}
    if second.get("organisation") == indep["lineage_trace"]["first_source"].get("organisation"):
        return fail("independent pair shares organisation")
    if second.get("origin_id") == indep["lineage_trace"]["first_source"].get("origin_id"):
        return fail("independent pair shares origin")

    if digest["verdict"] != SINGLE:
        return fail("OpenSSL vs coreutils should collapse through NIST")
    if not str(digest["failure_class"] or "").startswith("shared-upstream"):
        return fail(f"digest class={digest['failure_class']}")
    mutant_digest = deepcopy(digest)
    for src in mutant_digest["sources"]:
        src["cites"] = []
    flipped = classify_claim(
        {
            "id": mutant_digest["id"],
            "claim": mutant_digest["claim"],
            "sources": mutant_digest["sources"],
        }
    )
    if flipped["verdict"] != INDEPENDENT:
        return fail("stripping NIST cites from both tools did not restore independence")
    if naive_url_count_independent(digest["sources"]) and digest["verdict"] == SINGLE:
        pass
    else:
        return fail("digest case does not discriminate origin-trace from URL/path counting")

    if sha_w["verdict"] != SINGLE or sha_w["failure_class"] != "circular-citation":
        return fail("RFC 6234 citing FIPS must be circular-citation, not two origins")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    by_art = {r["id"]: r for r in doc["claims"]}
    for cid in ("C-REPUB-PLANT", "C-INDEP-PLANT", "C-DIGEST-HOST", "C-SHA256-WIDTH"):
        if by_art[cid]["verdict"] != by_live[cid]["verdict"]:
            return fail(f"{cid} artifact drifted")
        if by_art[cid]["label"] != by_live[cid]["label"]:
            return fail(f"{cid} label drifted")

    if doc.get("republication_counted_twice_count") != live["republication_counted_twice_count"]:
        return fail("republication count drifted")
    if doc.get("single_sourced_count") != live["single_sourced_count"]:
        return fail("single-sourced count drifted")
    if doc.get("independently_corroborated_count") != live["independently_corroborated_count"]:
        return fail("independent count drifted")

    print(
        json.dumps(
            {
                "repub_origin_count": repub["lineage_trace"]["origin_count"],
                "repub_url_count": repub["lineage_trace"]["url_count"],
                "repub_verdict": SINGLE,
                "indep_verdict": INDEPENDENT,
                "digest_verdict": SINGLE,
                "digest_mutant_without_nist_cites": flipped["verdict"],
                "hashlib": h,
                "coreutils": c,
                "rfc_cites_nist": sha_w["failure_class"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0063-probe2 republication shared-upstream both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

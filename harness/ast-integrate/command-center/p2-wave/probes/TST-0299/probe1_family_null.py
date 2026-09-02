#!/usr/bin/env python3
"""Probe 1: family-wide correction + null-tournament control (40 candidates)."""
from __future__ import annotations

import json

import paths as P
import reviewer as R
from bench.multiple_comparison import benjamini_hochberg, correct_family, holm
from bench.tournament import mixed_tournament, null_identical_tournament, null_iid_tournament


def fail(msg: str) -> int:
    print(f"FAILED:TST-0299-probe1 {msg}")
    return 1


def main() -> int:
    ident = null_identical_tournament()
    iid = null_iid_tournament()
    mixed = mixed_tournament()
    ident_f = ident["family"]
    iid_f = iid["family"]
    mix_f = mixed["family"]

    print(f"family_size_identical={ident_f['family_size']}")
    print(f"family_size_iid={iid_f['family_size']}")
    print(f"family_size_mixed={mix_f['family_size']}")
    if ident_f["family_size"] != 40 or iid_f["family_size"] != 40 or mix_f["family_size"] != 40:
        return fail("correction was not applied to a family of 40")

    methods = mix_f["correction_methods"]
    print(f"correction_methods={methods}")
    if "benjamini-hochberg" not in methods or "holm" not in methods:
        return fail("BH and Holm were not both applied")

    ps = [r["p_uncorrected"] for r in mix_f["comparisons"]]
    ids = [r["id"] for r in mix_f["comparisons"]]
    bh = benjamini_hochberg(ps, alpha=0.05)
    ho = holm(ps, alpha=0.05)
    if sum(bh["rejected"]) != mix_f["bh_discovery_count"]:
        return fail("BH discovery count mismatch vs recomputed")
    if sum(ho["rejected"]) != mix_f["holm_certified_count"]:
        return fail("Holm certified count mismatch vs recomputed")
    fam2 = correct_family(ps, ids=ids, alpha=0.05)
    if fam2["family_size"] != 40:
        return fail("recomputed family_size is not 40")

    print(
        "identical "
        f"uncorrected={ident_f['uncorrected_discovery_count']} "
        f"bh={ident_f['bh_discovery_count']} holm={ident_f['holm_certified_count']}"
    )
    if ident_f["uncorrected_discovery_count"] != 0:
        return fail("identical-to-baseline candidates must have p=1 and zero uncorrected winners")
    if ident_f["bh_discovery_count"] != 0 or ident_f["holm_certified_count"] != 0:
        return fail("identical null tournament yielded corrected discoveries")

    print(
        "iid_null "
        f"uncorrected={iid_f['uncorrected_discovery_count']} "
        f"bh={iid_f['bh_discovery_count']} holm={iid_f['holm_certified_count']} "
        f"seed={iid['seed']}"
    )
    if iid_f["uncorrected_discovery_count"] < 1:
        return fail("iid null tournament produced no uncorrected winners; chance-winner control is inert")
    if iid_f["bh_discovery_count"] != 0 or iid_f["holm_certified_count"] != 0:
        return fail(
            "iid null tournament yielded corrected discoveries "
            f"bh={iid_f['bh_discovery_count']} holm={iid_f['holm_certified_count']}"
        )

    print(
        "mixed "
        f"uncorrected={mix_f['uncorrected_discovery_count']} "
        f"bh={mix_f['bh_discovery_count']} holm={mix_f['holm_certified_count']} "
        f"shrink_delta={mixed['shrink_delta']}"
    )
    if mix_f["uncorrected_discovery_count"] <= mix_f["holm_certified_count"]:
        return fail("mixed tournament certification list did not shrink after correction")

    rev = R.review_live_runs()
    print(f"reviewer_verdict={rev['verdict']}")
    if rev["verdict"] != "PASS":
        return fail("independent re-run from raw scores failed")

    if not P.RECEIPT.is_file() or P.RECEIPT.stat().st_size <= 0:
        return fail("receipt missing")
    text = P.RECEIPT.read_text(encoding="utf-8")
    if P.SENTINEL not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt-unparseable:{exc}")
    st = str(doc.get("state") or "").upper()
    if st in P.NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if int(doc.get("family_size") or 0) != 40:
        return fail("receipt family_size is not 40")
    uc = (doc.get("uncorrected_verdict_counts") or {}).get("null-iid")
    cc = (doc.get("corrected_verdict_counts") or {}).get("null-iid") or {}
    if uc != iid_f["uncorrected_discovery_count"]:
        return fail("receipt iid uncorrected count mismatch")
    if cc.get("bh") != 0 or cc.get("holm") != 0:
        return fail("receipt iid corrected counts are not zero")
    if doc.get("certification_list_shrinks") is not True:
        return fail("receipt does not show certification-list shrink")

    print(
        "uncorrected_vs_corrected "
        f"mixed_uncorrected={mix_f['uncorrected_discovery_count']} "
        f"mixed_bh={mix_f['bh_discovery_count']} "
        f"mixed_holm={mix_f['holm_certified_count']}"
    )
    print("SUCCESS:TST-0299-probe1 family-size null-tournament BH Holm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

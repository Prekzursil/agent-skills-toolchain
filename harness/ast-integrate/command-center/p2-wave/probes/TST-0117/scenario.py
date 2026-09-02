"""Live evaluations for TST-0117 named probes.

Catalog tests_required:
  * test_two_inputs_with_one_root_cause_dedup_to_one_entry
  * test_crashing_input_is_minimised
  * test_corpus_seeds_are_reproducible_from_the_receipt
"""
from __future__ import annotations

import json
from pathlib import Path

from fuzz_triage.engine import (
    SEED_RECIPES,
    committed_corpus,
    crash_from_outcome,
    execute_tracked,
    materialise,
    minimise,
    minimise_identity,
    payload_fingerprint,
    run_campaign,
    sha256_bytes,
    triage_crashes,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "command-center/receipts/TST-0117.json"
SEEDS_JSON = HERE / "corpus" / "seeds.json"
CAMPAIGN_SEED = 117000
CAMPAIGN_BUDGET = 120


def _payload_fp(outcome, data: bytes) -> str:
    return payload_fingerprint(outcome, data)


def test_two_inputs_with_one_root_cause_dedup_to_one_entry() -> dict:
    left = b"hello\xffworld-pad"
    right = b"\xff" + b"other-padding-xx"
    oa = execute_tracked(left)
    ob = execute_tracked(right)
    same_fp = (
        (not oa.ok)
        and (not ob.ok)
        and oa.fingerprint == ob.fingerprint
        and oa.exception_func == "_crash_a"
        and ob.exception_func == "_crash_a"
        and left != right
    )
    live = triage_crashes([crash_from_outcome(oa), crash_from_outcome(ob)])
    mutant = triage_crashes(
        [crash_from_outcome(oa), crash_from_outcome(ob)],
        fingerprint=_payload_fp,
        do_minimise=False,
    )
    # Distinct root cause (0xFE) must NOT collapse into the 0xFF bucket.
    oc = execute_tracked(b"sep\xfe")
    mixed = triage_crashes(
        [
            crash_from_outcome(oa),
            crash_from_outcome(ob),
            crash_from_outcome(oc),
        ]
    )
    campaign = run_campaign(campaign_seed=CAMPAIGN_SEED, budget=CAMPAIGN_BUDGET)
    funcs = {e.exception_func for e in campaign.triage}
    passed = bool(
        same_fp
        and len(live) == 1
        and live[0].count == 2
        and live[0].exception_func == "_crash_a"
        and len(mutant) == 2
        and len(mixed) == 2
        and {e.exception_func for e in mixed} == {"_crash_a", "_crash_b"}
        and len(campaign.triage) >= 1
        and "_crash_a" in funcs
        and campaign.kept_for_coverage >= 1
        and campaign.crash_count >= 2
    )
    return {
        "pass": passed,
        "same_stack_fingerprint": same_fp,
        "live_triage_count": len(live),
        "live_count_field": live[0].count if live else 0,
        "live_func": live[0].exception_func if live else None,
        "live_fingerprint": live[0].fingerprint if live else None,
        "mutant_payload_hash_triage_count": len(mutant),
        "mixed_root_causes": len(mixed),
        "mixed_funcs": sorted({e.exception_func for e in mixed}),
        "both_states": {
            "good_stack_fp_collapses_to_one": len(live) == 1,
            "broken_payload_hash_splits_to_two": len(mutant) == 2,
        },
        "campaign_seed": campaign.campaign_seed,
        "campaign_budget": campaign.budget,
        "campaign_crash_count": campaign.crash_count,
        "campaign_triage_count": len(campaign.triage),
        "campaign_funcs": sorted(funcs),
        "campaign_kept_for_coverage": campaign.kept_for_coverage,
        "campaign_coverage_size": len(campaign.coverage),
        "reproduction": {
            "same_seed_same_triage_fps": _same_seed_reproduces(campaign),
        },
    }


def _same_seed_reproduces(first) -> bool:
    second = run_campaign(campaign_seed=first.campaign_seed, budget=first.budget)
    fps1 = [e.fingerprint for e in first.triage]
    fps2 = [e.fingerprint for e in second.triage]
    min1 = [e.minimised for e in first.triage]
    min2 = [e.minimised for e in second.triage]
    return fps1 == fps2 and min1 == min2 and first.crash_count == second.crash_count


def test_crashing_input_is_minimised() -> dict:
    padded = b"AAAA\xffBBBBCCCC"
    out = execute_tracked(padded)
    fp = out.fingerprint or ""
    live = minimise(padded, fp)
    mutant = minimise_identity(padded, fp)
    still = execute_tracked(live)
    overshrink = execute_tracked(b"")
    passed = bool(
        (not out.ok)
        and live == b"\xff"
        and len(live) < len(padded)
        and still.fingerprint == fp
        and (not still.ok)
        and mutant == padded
        and mutant != live
        and overshrink.ok
    )
    return {
        "pass": passed,
        "padded_hex": padded.hex(),
        "padded_nbytes": len(padded),
        "minimised_hex": live.hex(),
        "minimised_nbytes": len(live),
        "identity_mutant_nbytes": len(mutant),
        "identity_mutant_equals_padded": mutant == padded,
        "minimised_still_same_fp": still.fingerprint == fp,
        "both_states": {
            "good_shrinks_to_token": live == b"\xff",
            "broken_identity_keeps_padding": mutant == padded,
        },
    }


def test_corpus_seeds_are_reproducible_from_the_receipt() -> dict:
    records = committed_corpus()
    twice = [materialise(dict(r)) for r in SEED_RECIPES]
    again = [materialise(dict(r)) for r in SEED_RECIPES]
    hex_match = [a.hex() == b.hex() for a, b in zip(twice, again)]
    rec_match = [
        rec["bytes_hex"] == materialise(rec["recipe"]).hex()
        and rec["sha256"] == sha256_bytes(materialise(rec["recipe"]))
        for rec in records
    ]
    disk_ok = False
    disk_n = 0
    if SEEDS_JSON.is_file():
        disk = json.loads(SEEDS_JSON.read_text(encoding="utf-8"))
        disk_rows = disk.get("seeds") if isinstance(disk, dict) else disk
        disk_ok = isinstance(disk_rows, list) and [
            (row.get("id"), row.get("sha256"), row.get("bytes_hex"))
            for row in disk_rows
        ] == [(r["id"], r["sha256"], r["bytes_hex"]) for r in records]
        disk_n = len(disk_rows) if isinstance(disk_rows, list) else 0
    receipt_ok = False
    receipt_n = 0
    receipt_seed = None
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        seeds = ((doc.get("corpus") or {}).get("seeds")) or []
        receipt_n = len(seeds)
        receipt_ok = [
            (row.get("id"), row.get("sha256"), row.get("bytes_hex"))
            for row in seeds
        ] == [(r["id"], r["sha256"], r["bytes_hex"]) for r in records]
        receipt_seed = (doc.get("campaign") or {}).get("campaign_seed")
        if receipt_ok and receipt_seed is not None:
            replay = run_campaign(
                campaign_seed=int(receipt_seed),
                budget=int((doc.get("campaign") or {}).get("budget") or CAMPAIGN_BUDGET),
            )
            live_fps = [e.fingerprint for e in replay.triage]
            rec_fps = [
                e.get("fingerprint")
                for e in ((doc.get("triage") or {}).get("entries") or [])
            ]
            receipt_ok = receipt_ok and live_fps == rec_fps
    passed = bool(
        len(records) == len(SEED_RECIPES) == 5
        and all(hex_match)
        and all(rec_match)
        and disk_ok
        and (not RECEIPT.is_file() or receipt_ok)
        and all(b"\xff" not in materialise(dict(r)) for r in SEED_RECIPES)
        and all(b"\xfe" not in materialise(dict(r)) for r in SEED_RECIPES)
    )
    return {
        "pass": passed,
        "seed_count": len(records),
        "materialise_twice_identical": all(hex_match),
        "provenance_sha_matches_bytes": all(rec_match),
        "disk_seeds_match": disk_ok,
        "disk_seed_count": disk_n,
        "receipt_present": RECEIPT.is_file(),
        "receipt_seeds_match": receipt_ok if RECEIPT.is_file() else None,
        "receipt_seed_count": receipt_n,
        "seed_ids": [r["id"] for r in records],
        "seed_sha256": [r["sha256"] for r in records],
    }

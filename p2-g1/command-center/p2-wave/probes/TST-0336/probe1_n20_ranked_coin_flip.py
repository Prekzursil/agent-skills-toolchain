#!/usr/bin/env python3
"""Probe 1: N>=20 first-attempt flake rates, ranked list, coin-flip quarantine.

Signal a (empirical ledger). Mechanically different from probe 2, which
checks report visibility, debt fields, and retry-absorption on a separate
pass over attempt lists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
from suite import FIXED_NOW, REGISTRY, TESTS, commit_sha  # noqa: E402

ART = REPO / "command-center/receipts/TST-0336.json"
N = 20
UID = "TST-0336"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0336-probe1 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0336" not in text:
        return "sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    return None


def by_id(ranked: list[dict]) -> dict:
    return {r["test_id"]: r for r in ranked}


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    sha = commit_sha()
    live = L.measure_suite(
        TESTS, N, sha, max_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    ranked = live["ranked"]
    idx = by_id(ranked)
    if live["n"] != N:
        return fail(f"n={live['n']} want={N}")
    if any(r["commit_sha"] != sha for r in ranked):
        return fail("commit SHA drifted across tests")
    if any(r["provisional"] for r in ranked):
        return fail("N=20 rows labelled provisional")

    coin = idx["coin_flip"]
    if coin["classification"] != "FLAKY":
        return fail(f"coin_flip class={coin['classification']}")
    if coin["fails"] != 10 or coin["passes"] != 10:
        return fail(f"coin_flip not 10/10: {coin['passes']}/{coin['fails']}")
    if not (coin["flake_rate"] > L.THRESHOLD):
        return fail(f"coin_flip rate {coin['flake_rate']} not above threshold")
    if coin["quarantined"] is not True:
        return fail("coin_flip not quarantined")
    if coin["can_block"] is True:
        return fail("quarantined coin_flip can_block")
    if "coin_flip" not in live["quarantined_ids"]:
        return fail("coin_flip missing from quarantined_ids")

    above = idx["just_above"]
    if above["fails"] != 2 or above["quarantined"] is not True:
        return fail(f"just_above not quarantined: {above}")

    thresh = idx["at_threshold"]
    if thresh["fails"] != 1:
        return fail(f"at_threshold fails={thresh['fails']}")
    if thresh["flake_rate"] != L.THRESHOLD:
        return fail(f"at_threshold rate={thresh['flake_rate']}")
    if thresh["quarantined"] is True:
        return fail("at_threshold quarantined; threshold is strictly-above")

    stable = idx["stable_pass"]
    if stable["classification"] != "DETERMINISTIC" or stable["quarantined"]:
        return fail(f"stable_pass misclassified: {stable}")

    broken = idx["broken_always"]
    if broken["classification"] != "BROKEN" or broken["quarantined"]:
        return fail(f"broken_always misclassified: {broken}")
    if broken["can_block"] is not True:
        return fail("BROKEN must still block")
    if "broken_always" not in live["suite_blockers"]:
        return fail("broken_always not a suite blocker")

    bait = idx["retry_bait"]
    if bait["classification"] != "BROKEN":
        return fail(f"retry_bait first-attempt class={bait['classification']}")

    rates = [r["flake_rate"] for r in ranked]
    if rates != sorted(rates, reverse=True):
        return fail(f"ranked list not descending: {rates}")

    # Provisional control: same suite, N=5, every rate labelled provisional.
    short = L.measure_suite(
        TESTS, 5, sha, max_attempts=1, now=FIXED_NOW, registry=REGISTRY
    )
    if not all(r["provisional"] for r in short["ranked"]):
        return fail("N=5 rates were not labelled provisional")
    if any(r["provisional"] is False for r in short["ranked"]):
        return fail("N=5 leaked a definitive label")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    rec_ranked = (doc.get("flake_ledger") or {}).get("ranked") or []
    rec_idx = by_id(rec_ranked)
    if rec_idx.get("coin_flip", {}).get("quarantined") is not True:
        return fail("artifact coin_flip not quarantined")
    if rec_idx.get("coin_flip", {}).get("repetitions") != N:
        return fail("artifact coin_flip repetitions != 20")

    out = {
        "probe": "probe1-n20-ranked-coin-flip",
        "unit_id": UID,
        "n": N,
        "commit_sha": sha,
        "coin_flip_quarantined": True,
        "coin_flip_flake_rate": coin["flake_rate"],
        "coin_flip_repetitions": coin["repetitions"],
        "just_above_quarantined": True,
        "at_threshold_quarantined": False,
        "broken_blocks": True,
        "ranked_ids": [r["test_id"] for r in ranked],
        "ranked_rates": rates,
        "provisional_n5": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"n={N} coin_flip_quarantined=True rate={coin['flake_rate']} "
        f"just_above=True at_threshold=False broken_blocks=True "
        f"provisional_n5=True"
    )
    print("SUCCESS:TST-0336-probe1 n20 ranked coin-flip quarantine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

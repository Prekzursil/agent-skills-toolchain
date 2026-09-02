#!/usr/bin/env python3
"""Probe 1: ledger detects a planted coin-flip test (TST-0032).

Both-states:
  FIRE  — planted.coin_flip and planted.rare_flake are FLAKY and named.
  SILENT — planted.always_pass is DETERMINISTIC (not quarantined).

Independent recompute of class/ratio from raw outcomes must agree.
N<20 is refused. Same-(sha,order,n) retry without a new hypothesis is refused.
Quarantined tests still appear in the report (not hidden). Last-run of the
coin-flip PASSES (fail-on-odd), so detection is not 'last run failed'.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LIB))

from flake_quarantine.ledger import (  # noqa: E402
    BROKEN,
    DETERMINISTIC,
    FLAKY,
    InsufficientRepetitionsError,
    MIN_N,
    RetryWithoutHypothesisError,
    independent_ratios,
    measure,
)
from scenario import (  # noqa: E402
    ALWAYS_FAIL,
    ALWAYS_PASS,
    COIN_FLIP,
    N,
    ORDER,
    RARE_FLAKE,
    build_suite,
    run_planted,
)

UNIT = "TST-0032"
RAW = HERE / "probe1-planted-coin-flip.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0032-probe1 {msg}")
    return 1


def main() -> int:
    n19_refused = False
    try:
        measure(build_suite(), n=19, fingerprint={"sha": "x" * 64}, order=ORDER)
    except InsufficientRepetitionsError:
        n19_refused = True
    if not n19_refused:
        return fail("n=19 was classified instead of refused")

    ledger = run_planted()
    if int(ledger["n"]) != N or N < MIN_N:
        return fail(f"n={ledger['n']} want {N}")
    if list(ledger["order"]) != list(ORDER):
        return fail(f"order drifted {ledger['order']}")
    if not ledger.get("same_order"):
        return fail("same_order flag false")

    by_id = {r["id"]: r for r in ledger["rows"]}
    for name in ORDER:
        if name not in by_id:
            return fail(f"missing row {name}")
        if by_id[name]["n"] != N:
            return fail(f"{name} ran {by_id[name]['n']} times, want {N}")

    coin = by_id[COIN_FLIP]
    rare = by_id[RARE_FLAKE]
    ok = by_id[ALWAYS_PASS]
    broken = by_id[ALWAYS_FAIL]

    if coin["class"] != FLAKY or not coin["quarantined"]:
        return fail(f"coin_flip class={coin['class']} quarantined={coin['quarantined']}")
    if coin["passes"] != 10 or coin["pass_ratio"] != 0.5:
        return fail(f"coin_flip ratio {coin['pass_ratio']} passes={coin['passes']}")
    if coin["outcomes"][-1] is not True:
        return fail("coin_flip last run must PASS (fail-on-odd) so detection is not last-fail")
    if COIN_FLIP not in ledger["quarantined_named"]:
        return fail("coin_flip not named on quarantine list")

    if rare["class"] != FLAKY or rare["passes"] != 19:
        return fail(f"rare_flake class={rare['class']} passes={rare['passes']}")
    if RARE_FLAKE not in ledger["quarantined_named"]:
        return fail("rare_flake not named on quarantine list")

    if ok["class"] != DETERMINISTIC or ok["quarantined"] or ok["pass_ratio"] != 1.0:
        return fail(f"always_pass false-positive {ok}")
    if ALWAYS_PASS in ledger["quarantined"]:
        return fail("always_pass was quarantined")

    if broken["class"] != BROKEN or broken["pass_ratio"] != 0.0:
        return fail(f"always_fail class={broken['class']}")
    if ALWAYS_FAIL in ledger["quarantined"]:
        return fail("BROKEN test must not be labelled quarantined (that lane is FLAKY)")

    recomputed = independent_ratios(ledger["rows"])
    for name, row in by_id.items():
        rec = recomputed[name]
        if rec["class"] != row["class"] or rec["pass_ratio"] != row["pass_ratio"]:
            return fail(f"independent recompute mismatch {name}: {rec} vs {row}")
        if rec["quarantined"] != row["quarantined"]:
            return fail(f"independent quarantine mismatch {name}")

    if ledger.get("hidden_quarantine"):
        return fail("ledger hid quarantine")
    for name in ledger["quarantined"]:
        if not any(r["id"] == name for r in ledger["rows"]):
            return fail(f"quarantined {name} missing from report rows")

    retry_refused = False
    try:
        run_planted(prior=ledger)
    except RetryWithoutHypothesisError:
        retry_refused = True
    if not retry_refused:
        return fail("same-fingerprint retry without hypothesis was accepted")

    changed = run_planted(
        hypothesis="changed-hypothesis: re-measure after planted-suite edit",
        prior=ledger,
    )
    if changed["quarantined_named"] != ledger["quarantined_named"]:
        return fail("changed-hypothesis re-measure disagreed on names")

    payload = {
        "always_fail_class": broken["class"],
        "always_pass_class": ok["class"],
        "always_pass_not_quarantined": ALWAYS_PASS not in ledger["quarantined"],
        "changed_hypothesis_accepted": True,
        "coin_flip_class": coin["class"],
        "coin_flip_last_run_passed": True,
        "coin_flip_named": True,
        "coin_flip_pass_ratio": coin["pass_ratio"],
        "fingerprint_method": ledger["fingerprint"]["method"],
        "independent_recompute_agrees": True,
        "n": N,
        "n19_refused": True,
        "pass": True,
        "probe": "probe1-planted-coin-flip",
        "quarantined_named": list(ledger["quarantined_named"]),
        "rare_flake_class": rare["class"],
        "rare_flake_pass_ratio": rare["pass_ratio"],
        "retry_without_hypothesis_refused": True,
        "same_order": True,
        "sha": ledger["sha"],
        "unit_id": UNIT,
    }
    RAW.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"coin_flip={coin['class']} ratio={coin['pass_ratio']} "
        f"named={ledger['quarantined_named']} "
        f"always_pass={ok['class']} n19_refused={n19_refused} retry_refused={retry_refused}"
    )
    print("SUCCESS:TST-0032-probe1 planted coin-flip detected and named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

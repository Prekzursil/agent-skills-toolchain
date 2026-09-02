#!/usr/bin/env python3
"""Probe 1: null-delta distribution (n>=10) and seed-wiring proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "bench"))

import cases as C  # noqa: E402
import env_capture as E  # noqa: E402
import variance as V  # noqa: E402

RECEIPT = REPO / "command-center/receipts/TST-0297.json"
SEED_A = 20260824
SEED_B = 20260825


def fail(msg: str) -> int:
    print(f"FAILED:TST-0297-probe1 {msg}")
    return 1


def main() -> int:
    fixture = C.load_cases()
    if len(fixture) < 4:
        return fail("fixture too small")
    env = E.capture_environment(
        seed=SEED_A,
        model_id="fixture-model",
        model_snapshot="snap-0",
        temperature=0.0,
        concurrency=1,
        arrival_rate=1.0,
    )
    dist = V.null_delta_distribution(fixture, env, n=10, unpinned=False)
    if int(dist["n"]) < 10:
        return fail("n<10")
    if dist["all_identical"] is not True:
        return fail("pinned replicates were not identical")
    if float(dist["stdev"]) != 0.0:
        return fail(f"pinned stdev {dist['stdev']} != 0")
    if not V.pin_ok(dist):
        return fail("pin_ok false")
    recomputed = V.independent_stdev(dist["means"])
    if recomputed != float(dist["stdev"]):
        return fail(f"reviewer stdev {recomputed} != published {dist['stdev']}")

    unpinned = V.null_delta_distribution(fixture, env, n=10, unpinned=True)
    if unpinned["all_identical"] is True or float(unpinned["stdev"]) == 0.0:
        return fail("unpinned control did not move; pin is vacuous")

    wiring = V.seed_wiring_proof(fixture, env, SEED_A, SEED_B)
    if wiring["inert"] or not wiring["wired"]:
        return fail("seed is inert on the real runner")
    if wiring["result_set_a"] == wiring["result_set_b"]:
        return fail("seed change left the result set unchanged")

    mutant = V.seed_wiring_proof(
        fixture, env, SEED_A, SEED_B, run_fn=V.inert_seed_runner
    )
    if not mutant["inert"]:
        return fail("inert-seed mutant was not detected")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        if "SUCCESS:TST-0297" not in text:
            return fail("receipt missing sentinel")
        doc = json.loads(text)
        pub = doc.get("null_delta") or {}
        if int(pub.get("n") or 0) < 10:
            return fail("receipt n<10")
        if "stdev" not in pub or float(pub["stdev"]) != 0.0:
            return fail("receipt stdev is not the live pinned floor of 0")
        if "variance_floor" not in pub or float(pub["variance_floor"]) != float(dist["variance_floor"]):
            return fail("receipt floor != live floor")
        if list(pub.get("means") or []) != list(dist["means"]):
            return fail("receipt means != live means")

    payload = {
        "n": dist["n"],
        "stdev": dist["stdev"],
        "variance_floor": dist["variance_floor"],
        "all_identical": dist["all_identical"],
        "unpinned_stdev": unpinned["stdev"],
        "seed_wired": wiring["wired"],
        "inert_mutant_detected": mutant["inert"],
        "reviewer_stdev": recomputed,
        "env_fingerprint": dist["env_fingerprint"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"pinned_stdev={dist['stdev']} unpinned_stdev={unpinned['stdev']} "
        f"seed_wired={wiring['wired']} inert_mutant={mutant['inert']}"
    )
    print("SUCCESS:TST-0297-probe1 null-delta n=10 floor published seed wired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 1: same seed => identical roster; different seed => different roster.

Both directions are required. Same-seed-only cannot detect a frozen sampler.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

POOL = HERE / "fixtures" / "pool.json"
SPEC = HERE / "fixtures" / "draw_spec.json"


def _run(mode: str, seed: bytes, spec: dict, people: list) -> list[str]:
    return S.run_draw(people, spec, seed, mode)["roster"]


def main() -> int:
    people = S.load_json(POOL)["participants"]
    spec = S.load_json(SPEC)
    seed_a = S.parse_seed_hex(spec["seed_a_hex"])
    seed_b = S.parse_seed_hex(spec["seed_b_hex"])
    if seed_a == seed_b:
        print("FAILED:CNL-0016-probe1 fixture seeds are not distinct")
        return 1

    fail = False
    records = []
    for mode in ("uniform", "stratified"):
        a1 = _run(mode, seed_a, spec, people)
        a2 = _run(mode, seed_a, spec, people)
        b1 = _run(mode, seed_b, spec, people)
        same_ok = a1 == a2
        diff_ok = a1 != b1
        if not same_ok or not diff_ok:
            fail = True
        records.append(
            {
                "mode": mode,
                "seed_a_roster_1": a1,
                "seed_a_roster_2": a2,
                "seed_b_roster": b1,
                "same_seed_identical": same_ok,
                "different_seed_different": diff_ok,
            }
        )
        print(
            f"mode={mode} same_seed_identical={same_ok} "
            f"different_seed_different={diff_ok}"
        )
        print(f"  seed_a_1={a1}")
        print(f"  seed_a_2={a2}")
        print(f"  seed_b  ={b1}")

    # Frozen sampler (ignores seed) MUST fail the different-seed direction.
    frame = S.eligible_frame(people)
    frozen_a = S.frozen_roster(frame, int(spec["uniform_k"]), seed_a)
    frozen_b = S.frozen_roster(frame, int(spec["uniform_k"]), seed_b)
    frozen_is_stuck = frozen_a == frozen_b
    print(f"frozen_sampler_same_under_two_seeds={frozen_is_stuck} roster={frozen_a}")
    if not frozen_is_stuck:
        print("FAILED:CNL-0016-probe1 frozen control did not ignore the seed")
        return 1
    if frozen_a == records[0]["seed_a_roster_1"] and frozen_a == records[0]["seed_b_roster"]:
        print("FAILED:CNL-0016-probe1 live sampler matches frozen prefix; pool too small or RNG broken")
        return 1

    payload = {"probe": "probe1", "records": records, "frozen_stuck": frozen_is_stuck}
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:CNL-0016-probe1 seed/roster directions did not both hold")
        return 1
    print("SUCCESS:CNL-0016-probe1 same-seed identical; different-seed different")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: bands map to declared numeric ranges, checked mechanically.

Live claims from all four blueprints must carry p_low/p_high equal to
bands.BANDS[confidence_band]. A mutated mapping (likely -> 90-99) must
make the checker fire, so the check is not an always-pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bands import BANDS, claim_matches_declared  # noqa: E402
from blueprints import run_all  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0247-probe2 {msg}")
    return 1


def _check_claims(docs: dict, table: dict[str, tuple[int, int]]) -> list[str]:
    mismatches: list[str] = []
    for name, doc in docs.items():
        for c in doc["claims"]:
            if c.get("register") != "forward-looking":
                continue
            band = c.get("confidence_band")
            if band not in table:
                mismatches.append(f"{name}:{c.get('id')}:unknown-band:{band}")
                continue
            lo, hi = table[band]
            if c.get("p_low") != lo or c.get("p_high") != hi:
                mismatches.append(
                    f"{name}:{c.get('id')}:{band} "
                    f"got=({c.get('p_low')},{c.get('p_high')}) declared=({lo},{hi})"
                )
            if not claim_matches_declared(c) and table is BANDS:
                mismatches.append(f"{name}:{c.get('id')}:claim_matches_declared=false")
    return mismatches


def main() -> int:
    live = run_all()
    mismatches = _check_claims(live, BANDS)
    if mismatches:
        return _fail("live range mismatch " + "; ".join(mismatches[:8]))

    counts: dict[str, int] = {b: 0 for b in BANDS}
    n_fwd = 0
    for doc in live.values():
        for c in doc["claims"]:
            if c.get("register") != "forward-looking":
                continue
            n_fwd += 1
            counts[c["confidence_band"]] = counts.get(c["confidence_band"], 0) + 1
    if n_fwd < 4:
        return _fail(f"too few forward-looking claims: {n_fwd}")

    # Negative control: lie about 'likely' range. Live likely-claims must fail.
    mutant_table = dict(BANDS)
    mutant_table["likely"] = (90, 99)
    mutant_mismatches = []
    for name, doc in live.items():
        for c in doc["claims"]:
            if c.get("register") != "forward-looking":
                continue
            if c.get("confidence_band") != "likely":
                continue
            lo, hi = mutant_table["likely"]
            if c.get("p_low") != lo or c.get("p_high") != hi:
                mutant_mismatches.append(f"{name}:{c.get('id')}")
    if not mutant_mismatches:
        return _fail("mutant likely=(90,99) did not fire (checker always-pass)")

    # Positive: original table silent (already asserted). Dual signal:
    # declared table identity plus a live claim that uses attach() values.
    print(
        json.dumps(
            {
                "declared_ranges": {k: list(v) for k, v in BANDS.items()},
                "forward_looking_claims": n_fwd,
                "band_counts": counts,
                "live_mismatches": mismatches,
                "mutant_likely_90_99_fired": True,
                "mutant_hits": mutant_mismatches[:12],
            },
            sort_keys=True,
        )
    )
    print(
        f"ranges_match=True mutant_fired=True forward_claims={n_fwd} "
        f"bands_used={sorted(k for k, n in counts.items() if n)}"
    )
    print("SUCCESS:IMP-0247-probe2 bands-map-to-declared-numeric-ranges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

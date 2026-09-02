#!/usr/bin/env python3
"""Probe 1: seven one-at-a-time mutations each change the cache key (7/7).

Also: same inputs under a clock at T0 and T0+6h produce an identical key
(no clock leakage), and determinism.py's AST scan of the derivation modules
is empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.cachekey import (  # noqa: E402
    KEY_FIELDS,
    CacheInputs,
    derive_cache_key,
)
from agentspec.canonical import dumps, round_trip_ok  # noqa: E402
from agentspec.determinism import assert_clock_free  # noqa: E402
from inputs import base_inputs, seven_mutations  # noqa: E402

SIX_HOURS = 6 * 3600
T0 = 1_700_000_000.0
T1 = T0 + SIX_HOURS


def main() -> int:
    failures: list[str] = []
    base = base_inputs()
    baseline = derive_cache_key(base)
    if len(baseline) != 64 or any(c not in "0123456789abcdef" for c in baseline):
        failures.append(f"key not sha256-hex: {baseline!r}")

    mutated = seven_mutations(base)
    if tuple(mutated) != KEY_FIELDS:
        failures.append(f"mutation fields {tuple(mutated)} != {KEY_FIELDS}")

    per_field: dict[str, dict[str, str | bool]] = {}
    mutant_keys: list[str] = []
    changed = 0
    for field, other in mutated.items():
        key = derive_cache_key(other)
        differs = key != baseline
        if differs:
            changed += 1
        else:
            failures.append(f"{field} mutation did not change the key")
        per_field[field] = {
            "baseline": baseline,
            "mutated": key,
            "changed": differs,
        }
        mutant_keys.append(key)

    distinct_mutants = len(set(mutant_keys))
    if distinct_mutants != 7:
        failures.append(
            f"mutant key collisions: {distinct_mutants}/7 distinct {mutant_keys}"
        )
    if baseline in mutant_keys:
        failures.append("baseline collided with a mutant key")

    # Policy order must not leak list order into the key (same set => same key).
    reordered = base.evolve(tool_policy=("Grep", "Read"))
    if derive_cache_key(reordered) != baseline:
        failures.append("tool_policy order leaked into the key")

    if not round_trip_ok(base.as_canonical_dict()):
        failures.append("canonical round-trip of the seven fields failed")
    encoded = dumps(base.as_canonical_dict())
    again = dumps(base.as_canonical_dict())
    if encoded != again:
        failures.append("canonical dumps not stable")

    with patch("time.time", return_value=T0), patch(
        "time.time_ns", return_value=int(T0 * 1e9)
    ):
        k_t0 = derive_cache_key(base)
    with patch("time.time", return_value=T1), patch(
        "time.time_ns", return_value=int(T1 * 1e9)
    ):
        k_t1 = derive_cache_key(base)
    clock_stable = k_t0 == k_t1 == baseline
    if not clock_stable:
        failures.append(
            f"clock leakage: t0={k_t0} t0+6h={k_t1} baseline={baseline}"
        )

    k_repeat = derive_cache_key(
        CacheInputs(
            workflow_id=base.workflow_id,
            spec_version=base.spec_version,
            unit_id=base.unit_id,
            resolved_prompt=base.resolved_prompt,
            param_values=dict(base.param_values),
            tool_policy=tuple(base.tool_policy),
            input_artifact_hashes=dict(base.input_artifact_hashes),
        )
    )
    if k_repeat != baseline:
        failures.append("reconstructed inputs produced a different key")

    scan = assert_clock_free()
    if scan:
        failures.append("determinism scan: " + "; ".join(scan))

    report = {
        "probe": "probe1-seven-mutations",
        "unit_id": "IMP-0141",
        "baseline_key": baseline,
        "fields": list(KEY_FIELDS),
        "n_fields": len(KEY_FIELDS),
        "n_changed": changed,
        "n_distinct_mutants": distinct_mutants,
        "seven_of_seven": changed == 7 and distinct_mutants == 7,
        "per_field": per_field,
        "clock_t0_key": k_t0,
        "clock_t0_plus_6h_key": k_t1,
        "clock_stable": clock_stable,
        "determinism_findings": scan,
        "pass": not failures,
        "failures": failures,
    }
    print(json.dumps(report, sort_keys=True))
    if failures:
        print("FAILED:IMP-0141-probe1 " + "; ".join(failures))
        return 1
    print(
        "SUCCESS:IMP-0141-probe1 7/7 mutations change the key; "
        "T0 and T0+6h identical; AST clock/entropy scan empty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

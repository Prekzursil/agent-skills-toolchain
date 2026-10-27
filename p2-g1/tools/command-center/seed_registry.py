#!/usr/bin/env python3
"""Seed registry and multi-seed sweep for TST-0343 (C18).

A test that quietly depends on a fixed seed passes forever and protects
nothing outside that seed. Every collectible test MUST declare whether it
is seed-sensitive and why. The runner then executes the suite across a
recorded seed set and classifies every varying outcome:

  * narrow-assertion — same seed is bit-stable; outcomes differ across seeds.
    The assertion is too tight for the property it claims to cover.
  * flaky-C11       — the same recorded seed disagrees with itself. That is a
    detector failure, not a retry. Re-run is permitted only with a NEW seed.

The harness injects random.Random(seed). It never seeds the process-global
RNG, so a test that reads entropy outside the injected stream is C11, not
seed-sensitivity.

Planted controls (must be detected, never "fixed" into green):
  * test_planted_narrow_shuffle — pins one permutation; PASS on seed 127 only.
  * test_planted_hidden_counter_flake — hidden call counter; same seed flips.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
SUITE_PATH = REPO / "command-center" / "p2-wave" / "probes" / "TST-0343" / "suite.py"
SEED_REGISTRY_PATH = REPO / "command-center" / "SEED-REGISTRY.json"
TEST_REGISTRY_PATH = REPO / "command-center" / "TEST-REGISTRY.json"

STABLE = "stable"
NARROW = "narrow-assertion"
FLAKY = "flaky-C11"

PLANTED_NARROW_ID = "test_planted_narrow_shuffle"
PLANTED_FLAKE_ID = "test_planted_hidden_counter_flake"
PLANTED_NARROW_SEED = 127

# First ten primes >= 101. Recorded; re-running a listed seed is not a retry.
SEEDS: tuple[int, ...] = (101, 107, 109, 113, 127, 131, 137, 139, 149, 151)
SAME_SEED_REPEATS = 3
WILSON_Z = 1.96

RETRY_POLICY = (
    "Re-run is permitted only with a NEW recorded seed; re-running the same "
    "seed to get a different answer is a detector failure and must be "
    "reported as one."
)

# Permutation Random(127).shuffle(list(range(6))) produces. Unique in SEEDS.
PLANTED_NARROW_PERMUTATION: list[int] = [1, 2, 3, 5, 4, 0]


@dataclass
class TestSpec:
    """One collectible test plus its seed-sensitivity declaration."""

    id: str
    seed_sensitive: bool
    why: str
    fn: Callable[..., Any]
    planted: str | None = None


def _r8(value: float) -> float:
    return round(float(value), 8)


def wilson_interval(k: int, n: int, z: float = WILSON_Z) -> dict[str, float | int]:
    """Wilson score interval for a binomial pass-rate, plus the point estimate.

    Returns keys k, n, p, lo, hi, z. lo/hi are clamped to [0, 1] and rounded
    to 8 decimals so a reviewer re-deriving from (k, n) matches the receipt.
    """
    if n <= 0:
        return {"k": k, "n": n, "p": 0.0, "lo": 0.0, "hi": 1.0, "z": z}
    k = int(k)
    n = int(n)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    adj = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    lo = max(0.0, (centre - adj) / denom)
    hi = min(1.0, (centre + adj) / denom)
    return {
        "k": k,
        "n": n,
        "p": _r8(p),
        "lo": _r8(lo),
        "hi": _r8(hi),
        "z": z,
    }


def cohens_h(p1: float, p0: float) -> float:
    """Cohen's h = 2 (arcsin sqrt(p1) - arcsin sqrt(p0))."""
    return 2.0 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p0)))


def _load_suite():
    spec = importlib.util.spec_from_file_location("tst0343_suite", SUITE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load suite from {SUITE_PATH}")
    module = importlib.util.module_from_spec(spec)
    # suite.py imports this module; register before exec to break the cycle.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def specs() -> list[TestSpec]:
    suite = _load_suite()
    return list(suite.SPECS)


def run_one(fn: Callable[..., Any], seed: int) -> str:
    rng = random.Random(seed)
    try:
        fn(rng)
        return "PASS"
    except AssertionError:
        return "FAIL"
    except Exception as exc:  # noqa: BLE001 — surface as ERROR, do not swallow
        return f"ERROR:{type(exc).__name__}"


def _classify(
    per_seed: dict[str, str],
    same_seed_repeats: dict[str, list[str]],
) -> dict[str, Any]:
    matrix_values = list(per_seed.values())
    varies_across_seeds = len(set(matrix_values)) > 1
    flake_seeds: list[str] = []
    for seed, reps in same_seed_repeats.items():
        if len(set(reps)) > 1:
            flake_seeds.append(seed)
    same_seed_reproducible = not flake_seeds
    if not same_seed_reproducible:
        klass = FLAKY
    elif varies_across_seeds:
        klass = NARROW
    else:
        klass = STABLE
    return {
        "class": klass,
        "varies_across_seeds": varies_across_seeds,
        "same_seed_reproducible": same_seed_reproducible,
        "flake_seeds": flake_seeds,
    }


def run_sweep(seeds: tuple[int, ...] | list[int] | None = None) -> dict[str, Any]:
    """Execute every registered test on every recorded seed; classify rows."""
    suite = _load_suite()
    recorded = list(seeds if seeds is not None else SEEDS)
    if len(recorded) != len(set(recorded)):
        raise ValueError("duplicate seeds in sweep")
    test_specs = list(suite.SPECS)
    if hasattr(suite, "reset_planted_state"):
        suite.reset_planted_state()

    rows: list[dict[str, Any]] = []
    matrix: dict[str, dict[str, str]] = {}

    for spec in test_specs:
        # Reset planted counters once per test, never per seed: a per-seed
        # reset would hide the C11 plant (first attempt would always PASS).
        if hasattr(suite, "reset_planted_state"):
            suite.reset_planted_state()
        per_seed: dict[str, str] = {}
        for seed in recorded:
            per_seed[str(seed)] = run_one(spec.fn, seed)
        matrix[spec.id] = per_seed
        same_seed_repeats: dict[str, list[str]] = {}
        for seed in recorded:
            same_seed_repeats[str(seed)] = [
                run_one(spec.fn, seed) for _ in range(SAME_SEED_REPEATS)
            ]
        flags = _classify(per_seed, same_seed_repeats)
        k = sum(1 for v in per_seed.values() if v == "PASS")
        n = len(per_seed)
        stats = wilson_interval(k, n)
        stats["cohens_h_vs_always_pass"] = _r8(cohens_h(float(stats["p"]), 1.0))
        undeclared = flags["class"] != STABLE and not spec.seed_sensitive
        rows.append(
            {
                "id": spec.id,
                "class": flags["class"],
                "seed_sensitive_declared": spec.seed_sensitive,
                "why": spec.why,
                "planted": spec.planted,
                "undeclared_sensitivity": undeclared,
                "per_seed": per_seed,
                "pass_count": k,
                "n_seeds": n,
                "stats": stats,
                "same_seed_reproducible": flags["same_seed_reproducible"],
                "varies_across_seeds": flags["varies_across_seeds"],
                "flake_seeds": flags["flake_seeds"],
                "same_seed_repeats": same_seed_repeats,
            }
        )

    varying_ids = [r["id"] for r in rows if r["class"] != STABLE]
    narrow_ids = [r["id"] for r in rows if r["class"] == NARROW]
    flaky_ids = [r["id"] for r in rows if r["class"] == FLAKY]
    undeclared_ids = [r["id"] for r in rows if r["undeclared_sensitivity"]]
    planted_narrow = next((r for r in rows if r["id"] == PLANTED_NARROW_ID), None)
    planted_flake = next((r for r in rows if r["id"] == PLANTED_FLAKE_ID), None)

    return {
        "seeds": recorded,
        "n_seeds": len(recorded),
        "n_tests": len(test_specs),
        "matrix": matrix,
        "rows": rows,
        "varying_ids": varying_ids,
        "narrow_assertion_ids": narrow_ids,
        "flaky_c11_ids": flaky_ids,
        "undeclared_ids": undeclared_ids,
        "planted_narrow_detected": bool(
            planted_narrow
            and planted_narrow["class"] == NARROW
            and planted_narrow["pass_count"] == 1
            and planted_narrow["per_seed"].get(str(PLANTED_NARROW_SEED)) == "PASS"
        ),
        "planted_flake_detected": bool(
            planted_flake and planted_flake["class"] == FLAKY
        ),
        "retry_policy": RETRY_POLICY,
    }


def _declaration_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in report["rows"]:
        out.append(
            {
                "id": row["id"],
                "seed_sensitive": row["seed_sensitive_declared"],
                "why": row["why"],
                "planted": row["planted"],
                "class": row["class"],
                "undeclared_sensitivity": row["undeclared_sensitivity"],
                "pass_count": row["pass_count"],
                "n_seeds": row["n_seeds"],
            }
        )
    return out


def write_registries(report: dict[str, Any]) -> None:
    """Write SEED-REGISTRY.json. Do not replace the estate TEST-REGISTRY.json.

    command-center/TEST-REGISTRY.json records which tests protect which
    command-center invariants (TI-1..TI-9). Overwriting it with the TST-0343
    suite would break tools/command-center/tests/test_registry.py. Seed
    declarations for THIS unit live in SEED-REGISTRY.json; TEST-REGISTRY.json
    is an input (catalog) and is left intact.
    """
    SEED_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "unit_id": "TST-0343",
        "purpose": (
            "Every test in the TST-0343 seed-sweep suite declares whether it "
            "is seed-sensitive and why. A single-seed green run cannot support "
            "a seed-independence claim."
        ),
        "seeds": report["seeds"],
        "n_seeds": report["n_seeds"],
        "n_tests": report["n_tests"],
        "retry_policy": report["retry_policy"],
        "estate_test_registry": "command-center/TEST-REGISTRY.json",
        "estate_test_registry_note": (
            "Estate-wide discovery of every collectible test is TST-0326. "
            "This file is the TST-0343 seed-sweep declaration set."
        ),
        "tests": _declaration_rows(report),
        "varying_ids": report["varying_ids"],
        "narrow_assertion_ids": report["narrow_assertion_ids"],
        "flaky_c11_ids": report["flaky_c11_ids"],
        "undeclared_ids": report["undeclared_ids"],
        "planted_narrow_detected": report["planted_narrow_detected"],
        "planted_flake_detected": report["planted_flake_detected"],
    }
    SEED_REGISTRY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    if not TEST_REGISTRY_PATH.is_file():
        # Catalog lists TEST-REGISTRY.json as an input. If it is absent, do
        # not invent an estate registry; seed declarations already landed.
        return


def main() -> int:
    report = run_sweep()
    write_registries(report)
    print(
        json.dumps(
            {
                "n_seeds": report["n_seeds"],
                "n_tests": report["n_tests"],
                "varying_ids": report["varying_ids"],
                "narrow_assertion_ids": report["narrow_assertion_ids"],
                "flaky_c11_ids": report["flaky_c11_ids"],
                "planted_narrow_detected": report["planted_narrow_detected"],
                "planted_flake_detected": report["planted_flake_detected"],
            },
            indent=2,
        )
    )
    if not report["planted_narrow_detected"] or not report["planted_flake_detected"]:
        print("FAILED:seed-registry planted controls not detected", file=sys.stderr)
        return 1
    print("SUCCESS:seed-registry sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

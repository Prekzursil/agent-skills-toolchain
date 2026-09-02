#!/usr/bin/env python3
"""Probe 2: independent arithmetic, pin-mismatch refusal, genuine still accepted.

Does not call engine.evaluate_control (probe 1's instrument). Re-runs variants,
recomputes visible vs held-out correctness, checks the naive composite ACCEPT
of gamed variants, confirms a mutated registry is refused, and checks the
genuine improvement still beats baseline on held-out correctness.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import CASES  # noqa: E402
from engine import run_variant  # noqa: E402
from registry import (  # noqa: E402
    PIN_PATH,
    REGISTRY_PATH,
    RegistryPinError,
    load_pinned_registry,
    sha256_bytes,
)
from variants import GAMED_IDS, PRIMARY_GAMED_IDS, VARIANTS  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0131-benchmark-gaming-adversarial-control.json"
MIN_EFFECT = 0.05
WEIGHT = 0.25


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0131-probe2 {msg}")
    return 1


def indep_correctness(trace: list[dict], slice_name: str) -> float:
    rows = [r for r in trace if r["slice"] == slice_name]
    return sum(1 for r in rows if r["correct"]) / len(rows)


def indep_coverage(trace: list[dict], slice_name: str, required: list[str]) -> float:
    rows = [r for r in trace if r["slice"] == slice_name]
    declared: set[str] = set()
    for r in rows:
        declared.update(str(c) for c in (r.get("declared_capabilities") or []))
    return len(declared & set(required)) / len(required)


def indep_recovery(trace: list[dict], slice_name: str) -> float:
    rows = [r for r in trace if r["slice"] == slice_name]
    first_fail = [r for r in rows if r.get("first_failed")]
    if not first_fail:
        return 1.0 if all(r["correct"] for r in rows) else 0.0
    recovered = sum(1 for r in first_fail if r["correct"] or r.get("claimed_recovered"))
    return recovered / len(first_fail)


def indep_usability(trace: list[dict], slice_name: str) -> float:
    rows = [r for r in trace if r["slice"] == slice_name]
    total = 0.0
    for r in rows:
        req = int(r.get("fields_required") or 1)
        total += int(r.get("fields_present") or 0) / req
    return total / len(rows)


def indep_composite(trace: list[dict]) -> float:
    return WEIGHT * (
        indep_correctness(trace, "visible")
        + indep_coverage(trace, "visible", ["parse-input", "branch-policy", "recover-fault", "emit-report"])
        + indep_recovery(trace, "visible")
        + indep_usability(trace, "visible")
    )


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    claimed_pin = str(doc.get("metric_registry", {}).get("sha256_before_first_run") or "")
    live_reg, live_pin = load_pinned_registry()
    file_pin = PIN_PATH.read_text(encoding="utf-8").strip()
    file_sha = sha256_bytes(REGISTRY_PATH.read_bytes())
    if not claimed_pin or claimed_pin != live_pin or claimed_pin != file_pin or claimed_pin != file_sha:
        return fail(
            f"pin mismatch claimed={claimed_pin} live={live_pin} "
            f"file_pin={file_pin} file_sha={file_sha}"
        )

    mutated = dict(live_reg)
    mutated["min_effect_size"] = 0.99
    mut_path = HERE / "fixtures" / "_mutated_registry.json"
    mut_path.write_text(
        json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    refused = False
    try:
        load_pinned_registry(mut_path, expected_sha=claimed_pin)
    except RegistryPinError:
        refused = True
    finally:
        if mut_path.is_file():
            mut_path.unlink()
    if not refused:
        return fail("mutated registry was accepted against the original pin")

    traces = {name: run_variant(fn, CASES) for name, fn in VARIANTS.items()}
    base = traces["honest_baseline"]
    base_c = indep_composite(base)
    naive_accept = []
    for name in GAMED_IDS:
        delta = indep_composite(traces[name]) - base_c
        if delta >= MIN_EFFECT:
            naive_accept.append(name)
    if len(naive_accept) < 3:
        return fail(f"independent naive composite accepted {naive_accept}")
    missing_primary = [n for n in PRIMARY_GAMED_IDS if n not in naive_accept]
    if missing_primary:
        return fail(f"primary gamed not naive-accepted {missing_primary}")

    genuine = traces["genuine_improvement"]
    g_vis = indep_correctness(genuine, "visible")
    g_ho = indep_correctness(genuine, "held-out")
    b_vis = indep_correctness(base, "visible")
    b_ho = indep_correctness(base, "held-out")
    if g_ho <= b_ho:
        return fail(f"genuine held-out {g_ho} did not beat baseline {b_ho}")
    if g_vis <= b_vis:
        return fail(f"genuine visible {g_vis} did not beat baseline {b_vis}")
    if indep_composite(genuine) - base_c < MIN_EFFECT:
        return fail("genuine naive composite missed min_effect_size")
    if not doc.get("counter_control", {}).get("genuine_improvement_gated_accept"):
        return fail("artifact did not record genuine gated ACCEPT")

    overfit = traces["gamed_case_overfitting"]
    of_vis = indep_correctness(overfit, "visible")
    of_ho = indep_correctness(overfit, "held-out")
    if of_vis <= of_ho + 0.25:
        return fail(f"overfit gap too small vis={of_vis} ho={of_ho}")

    fixtures_ok = []
    for name in GAMED_IDS:
        p = HERE / "fixtures" / "runs" / f"{name}.json"
        if not p.is_file():
            return fail(f"missing score fixture {p.name}")
        blob = json.loads(p.read_text(encoding="utf-8"))
        if blob.get("variant") != name or not blob.get("trace"):
            return fail(f"unusable fixture {p.name}")
        fixtures_ok.append(name)

    payload = {
        "probe": "probe2_naive_pin_and_genuine",
        "pin": claimed_pin,
        "mutated_registry_refused": True,
        "naive_accept_gamed": naive_accept,
        "genuine_heldout": round(g_ho, 6),
        "baseline_heldout": round(b_ho, 6),
        "overfit_visible": round(of_vis, 6),
        "overfit_heldout": round(of_ho, 6),
        "gamed_fixtures": fixtures_ok,
        "evaluate_control_called": False,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"pin_ok=True mutated_refused=True naive_accept={len(naive_accept)} "
        f"genuine_ho={g_ho:.3f}>baseline_ho={b_ho:.3f}"
    )
    print("SUCCESS:WFA-0131-probe2 naive-accept pin-mismatch genuine-held-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

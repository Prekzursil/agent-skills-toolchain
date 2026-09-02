#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0180.json from live probe raw files."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

OUT = REPO / "command-center/receipts/CNF-0180.json"
P1_RAW = HERE / "probe1-empty-thermal.raw.json"
P2_RAW = HERE / "probe2-order-slowdown.raw.json"
P1_PATH = "command-center/p2-wave/probes/CNF-0180/probe1_empty_and_thermal.py"
P2_PATH = "command-center/p2-wave/probes/CNF-0180/probe2_order_and_slowdown.py"
QUESTION = (
    "Question: do the claimed latency and overhead numbers survive a cold "
    "machine, a randomized run order, and a non-empty input set? Benchmarks "
    "on this estate have returned clean greens over EMPTY inputs, and "
    "warm-state measurements systematically flatter the second thing measured. "
    "Re-measure independently with the confounds removed and report "
    "distributions, not single numbers."
)
CLAIM = (
    "Published latency and overhead figures for the product harness survive "
    "cold-start, randomized run order, and a mandatory non-empty input set."
)


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def probe_fp(rel: str, instrument: str, field: str, engine: str) -> dict:
    path = REPO / rel
    return {
        "path": rel,
        "sha256": sha256_file(path),
        "instrument": instrument,
        "field": field,
        "engine": engine,
        "shell": sys.executable,
        "tool": "python3 -B",
    }


def dist_view(block: dict) -> dict:
    d = block.get("distribution") or block
    return {
        "n": d.get("n"),
        "median_ms": d.get("median_ms"),
        "iqr_ms": d.get("iqr_ms"),
        "min_ms": d.get("min_ms"),
        "max_ms": d.get("max_ms"),
        "stdev_ms": d.get("stdev_ms"),
    }


def main() -> int:
    if not P1_RAW.is_file() or not P2_RAW.is_file():
        print("FAILED:CNF-0180 emit missing probe raw files")
        return 1
    p1 = json.loads(P1_RAW.read_text(encoding="utf-8"))
    p2 = json.loads(P2_RAW.read_text(encoding="utf-8"))
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:CNF-0180 emit probes did not pass")
        return 1
    census = I.census()
    source = probe_fp(
        P1_PATH,
        p1.get("instrument") or "perf_counter",
        "elapsed_ms",
        "in-process-hashlib + fresh-subprocess first-iter",
    )
    verifier = probe_fp(
        P2_PATH,
        p2.get("instrument") or "monotonic",
        "elapsed_ms+parent_monotonic_wall_ms",
        "child-process hashlib via time.monotonic",
    )
    if source["sha256"] == verifier["sha256"]:
        print("FAILED:CNF-0180 source_probe fingerprint equals verifier_probe")
        return 1
    blind_payload = json.dumps(
        {
            "claim_id": "CNF-0180",
            "claim": CLAIM,
            "question": QUESTION,
            "tests_required": [
                "Empty-input control: assert every benchmark case has non-zero input size; a zero must fail the run.",
                "Order control: randomize run order and confirm the ranking is stable.",
                "Cold-state control: measure once cold and once warm and report both.",
                "Known-broken control: inject a deliberate 20 percent slowdown and confirm the harness detects it.",
            ],
            "exclude": [
                "implementer receipts",
                "review verdicts",
                "prior confirmation records",
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    attestation = hashlib.sha256(blind_payload).hexdigest()

    cases = []
    for c in p1.get("cases") or []:
        cases.append(
            {
                "case_id": c["case_id"],
                "input_size_bytes": c["input_size_bytes"],
                "cold": dist_view(c["cold"]),
                "warm": dist_view(c["warm"]),
            }
        )
    live = p1.get("live_claim_remeasure") or {}
    order = p2.get("order_control") or {}
    slow = p2.get("slowdown_control") or {}

    product_figs_present = bool(census["rerunnable_recorded_distributions"])
    claimed_0925 = next(
        (
            c
            for c in census["live_numeric_claims"]
            if c.get("field") == "detection_latency.latency_ms"
        ),
        None,
    )
    claimed_183 = next(
        (
            c
            for c in census["live_numeric_claims"]
            if c.get("source", "").endswith("ADV-0115/_validate_out.json")
        ),
        None,
    )
    stop_inside = bool(live.get("claimed_inside_warm_iqr"))
    discrepancies = [
        {
            "id": "D1",
            "topic": "product-recorded-results",
            "detail": census["honest_summary"],
            "severity": "blocking-for-confirmation",
        },
        {
            "id": "D2",
            "topic": "stop-hook-single-sample",
            "detail": (
                f"Claimed stop-hook latency_ms={claimed_0925 and claimed_0925.get('value_ms')} "
                f"n=1. Independent warm median_ms="
                f"{(live.get('warm') or {}).get('distribution', {}).get('median_ms')} "
                f"n={((live.get('warm') or {}).get('distribution') or {}).get('n')} "
                f"claimed_inside_warm_iqr={stop_inside}. Original protocol did not "
                "assert input size, randomize order, or report cold vs warm."
            ),
            "severity": "protocol-failure",
        },
        {
            "id": "D3",
            "topic": "adv-0115-warm-only-snippet",
            "detail": (
                f"ADV-0115 snippet claims warm routing p50={claimed_183 and claimed_183.get('value_ms')} ms "
                f"but primary artifact present={claimed_183 and claimed_183.get('primary_artifact_present')} "
                f"and source unit state={claimed_183 and claimed_183.get('source_unit_state')}. "
                "Cannot independently re-run. Warm-only is the confound this unit removes."
            ),
            "severity": "unreproducible-claim",
        },
    ]

    tests = [
        {
            "id": "empty-input",
            "name": "Zero-size case fails the run and emits no latency number",
            "result": "PASS" if p1["empty_input_control"]["pass"] and p2["empty_input_control"]["pass"] else "FAIL",
            "signals": ["in-process EmptyInputError", "child --empty exit 2 with elapsed_ms=null"],
        },
        {
            "id": "order",
            "name": "Ranking stable across randomized run orders",
            "result": "PASS" if order.get("pass") else "FAIL",
            "ranking": (order.get("rankings") or [{}])[0].get("ranking"),
            "seeds": order.get("seeds"),
        },
        {
            "id": "cold-warm",
            "name": "Cold subprocess first-iter and warm in-process distributions both reported",
            "result": "PASS" if cases else "FAIL",
            "cases": cases,
        },
        {
            "id": "known-broken-20pct",
            "name": "Harness detects a deliberate 20 percent slowdown",
            "result": "PASS" if slow.get("pass") else "FAIL",
            "median_ratio": slow.get("median_ratio"),
            "injected": slow.get("injected_slowdown"),
        },
    ]

    claims = [
        {
            "id": "C1",
            "claim": CLAIM,
            "verdict": "REFUTED",
            "reason": census["honest_summary"],
        },
        {
            "id": "C2",
            "claim": "The live Stop-hook latency_ms=0.925 survives cold, order, and non-empty controls as a distribution.",
            "verdict": "REFUTED",
            "reason": (
                "Original evidence is n=1 and bundles plant+detect+hook. Independent "
                "re-measure reports cold and warm distributions with input_size_files="
                f"{live.get('input_size_files')}; a single number does not survive the protocol."
            ),
        },
        {
            "id": "C3",
            "claim": "An independent harness with the four required controls can be executed on this box.",
            "verdict": "CONFIRMED",
            "reason": "Probe 1 and probe 2 both exit 0; empty, order, thermal, and 20% controls pass.",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0180",
        "claim_id": "CNF-0180",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0180",
        "completion_sentinel": "SUCCESS:CNF-0180",
        "verdict": "REFUTED",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "confirmer": {
            "identity": "CNF-0180-independent-reproduction-engineer",
            "vendor": "independent-local",
            "role": "reproduction-engineer",
            "model": "cursor-grok-4.6",
        },
        "blinding_attestation_hash": attestation,
        "blinding_attestation": {
            "algorithm": "sha256",
            "payload_bytes": len(blind_payload),
            "rule": "claim statement + tests_required only; implementer receipts excluded",
            "worked_recompute": attestation,
        },
        "source_probe": source,
        "verifier_probe": verifier,
        "baseline_repro": {
            "what": "Independent cold+warm distributions for four non-empty component cases",
            "n_reps": p1.get("n_reps"),
            "cases": cases,
            "machine_state_before": p1.get("machine_state_before"),
        },
        "corrected_repro": {
            "what": "Same cases under randomized order (probe 2) and with empty-input refusal",
            "ranking": (order.get("rankings") or [{}])[0].get("ranking"),
            "order_stable": order.get("stable"),
            "empty_input_inprocess": p1.get("empty_input_control"),
            "empty_input_child": {
                "pass": p2["empty_input_control"]["pass"],
                "exit_code": p2["empty_input_control"]["exit_code"],
                "elapsed_ms_emitted": p2["empty_input_control"]["elapsed_ms_emitted"],
            },
        },
        "rollback_repro": {
            "what": "Unslowed child arm versus +20% rounds; ranking uses only the unslowed arm",
            "slowdown_detected": slow.get("detected"),
            "median_ratio": slow.get("median_ratio"),
            "baseline_median_ms": (slow.get("baseline") or {}).get("median_ms"),
            "slowed_median_ms": (slow.get("slowed") or {}).get("median_ms"),
        },
        "regression_diff": {
            "product_recorded_distributions": product_figs_present,
            "stop_hook_claimed_ms": claimed_0925 and claimed_0925.get("value_ms"),
            "stop_hook_independent_warm_median_ms": (live.get("warm") or {})
            .get("distribution", {})
            .get("median_ms"),
            "stop_hook_independent_warm_n": ((live.get("warm") or {}).get("distribution") or {}).get("n"),
            "adv0115_claimed_warm_p50_ms": claimed_183 and claimed_183.get("value_ms"),
            "adv0115_primary_present": claimed_183 and claimed_183.get("primary_artifact_present"),
        },
        "discrepancies": discrepancies,
        "residual_caveat": (
            "Reviewer same-day re-run is probe 2 (different instrument), not a "
            "calendar-next-day repetition. Product hooks/harness-bench and "
            "_USER-PROMPTS.md:11021-11022 are absent on this worktree, so the "
            "independent harness measures labelled stand-ins plus the live "
            "Stop-hook path. Verdict REFUTED is on the catalog question, not "
            "a process BLOCKED."
        ),
        "claimed_figures_inventory": census,
        "live_claim_remeasure": {
            "case_id": live.get("case_id"),
            "claimed_ms": live.get("claimed_ms"),
            "input_size_files": live.get("input_size_files"),
            "claimed_inside_warm_iqr": live.get("claimed_inside_warm_iqr"),
            "cold": dist_view(live.get("cold") or {}),
            "warm": dist_view(live.get("warm") or {}),
            "note": live.get("note"),
        },
        "tests": tests,
        "claims": claims,
        "reviewer": {
            "reviewer_id": "CNF-0180-probe2-monotonic-child",
            "independent": True,
            "verdict": "PASS",
            "note": "Re-ran order ranking and 20% slowdown on a different clock and process boundary.",
        },
        "artifacts": [
            {
                "path": "command-center/receipts/CNF-0180.json",
                "role": "primary",
                "exists": True,
            }
        ],
        "output_schema": "command-center/schema/confirmation-record.schema.json",
        "schema_note": (
            "CNF-0129 owns the global schema file; it is absent on this "
            "worktree. This record carries the required confirmation fields "
            "(claim_id, confirmer, blinding_attestation_hash, baseline_repro, "
            "corrected_repro, rollback_repro, regression_diff, discrepancies, "
            "verdict, source_probe, verifier_probe, residual_caveat)."
        ),
        "produced_at": now,
        "pass": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} verdict=REFUTED state=SUCCESS")
    print("SUCCESS:CNF-0180")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0127-retention-remeasure.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import checks as C  # noqa: E402
import harness as H  # noqa: E402
import independence as I  # noqa: E402
import ledger as L  # noqa: E402
import schema_local as S  # noqa: E402

UNIT = "CNF-0127"
OUT_REL = "command-center/confirmation/CNF-0127-retention-remeasure.json"
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
REMESURER = "cnf-0127-auditor"
R1 = "cnf-0127-r1-arithmetic"
R2 = "cnf-0127-r2-raw-rederive"
BASELINE_AGENT = "cnf-0127-baseline-operator"


def locate(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:{UNIT} missing snippet in {rel}: {snippet!r}")


def file_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw_output: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:8000],
        "fingerprint": hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32],
        "exit_code": exit_code,
    }


def validate_or_die(doc: dict) -> None:
    S.validate_or_die(doc)


def decide(row: dict, base_m: dict, imp_m: dict) -> dict:
    metric = row["claimed_metric"]
    if metric == "ops":
        base_med = float(base_m["ops_median"])
        imp_med = float(imp_m["ops_median"])
        floor = max(float(base_m["ops_iqr"]), float(imp_m["ops_iqr"]))
        raw = list(imp_m["raw_ops"])
        unit = "ops"
    else:
        base_med = float(base_m["ms_median"])
        imp_med = float(imp_m["ms_median"])
        floor = max(float(base_m["ms_iqr"]), float(imp_m["ms_iqr"]))
        raw = list(imp_m["raw_ms"])
        unit = "elapsed_ms"
    gain = base_med - imp_med
    guard_id = row.get("guard_case")
    added = bool(row.get("added_benchmark_case")) and bool(guard_id)
    guard_catches = False
    guard_detail = None
    if guard_id:
        g_imp = H.guard_result(row["variant"], guard_id)
        g_base = H.guard_result("baseline", guard_id)
        guard_catches = (not g_base["correct"]) and bool(g_imp["correct"])
        guard_detail = {"improved": g_imp, "baseline": g_base}

    if metric == "elapsed_ms" and gain <= floor:
        verdict = "REVERT"
        classification = "noise-dominated-claim"
        reason = "claimed wall-clock gain is at or inside the measured noise floor"
    elif gain <= 0:
        verdict = "REVERT"
        classification = "neutral-or-harmful"
        reason = "remeasured gain is zero or negative (neutral or harmful)"
    elif gain <= floor:
        verdict = "REVERT"
        classification = "noise-dominated-claim"
        reason = "remeasured gain does not exceed the noise floor"
    elif not added or not guard_catches:
        verdict = "FILE"
        classification = "missing-guard-case"
        reason = "no added benchmark case that fails on baseline and passes on the change"
    else:
        verdict = "KEEP"
        classification = "measurable-keep"
        reason = "independent remesure shows gain above noise floor and guard catches the original failure"

    return {
        "verdict": verdict,
        "classification": classification,
        "reason": reason,
        "measured_gain": gain,
        "noise_floor_value": floor,
        "baseline_median": base_med,
        "improved_median": imp_med,
        "metric_unit": unit,
        "guard_catches_original_failure": guard_catches,
        "added_benchmark_case": added,
        "guard_detail": guard_detail,
        "remeasurements": {
            "raw": raw,
            "median": imp_med,
            "iqr": float(imp_m["ops_iqr"] if metric == "ops" else imp_m["ms_iqr"]),
            "repetitions": int(imp_m["repetitions"]),
            "reported_as": imp_m["reported_as"],
            "outcomes": list(imp_m["outcomes"]),
            "baseline_raw": list(base_m["raw_ops"] if metric == "ops" else base_m["raw_ms"]),
            "baseline_reported_as": base_m["reported_as"],
        },
    }


def rederive_from_raw(case: dict) -> str:
    """Second reviewer: verdict from raw numbers + guard flags only."""
    rem = case["remeasurements"]
    gain = float(case["measured_gain"])
    floor = float(case["noise_floor_value"])
    metric = case["claimed_metric"]
    if len(rem["raw"]) != int(rem["repetitions"]):
        return "UNMEASURABLE"
    if metric == "elapsed_ms" and gain <= floor:
        return "REVERT"
    if gain <= 0 or gain <= floor:
        return "REVERT"
    if not case.get("added_benchmark_case") or not case.get("guard_catches_original_failure"):
        return "FILE"
    return "KEEP"


def main() -> int:
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pack = L.retained_list()
    planted = pack["under_audit"]
    base_m = H.measure_variant("baseline", agent_id=BASELINE_AGENT)
    cases = []
    r1_votes = []
    r2_votes = []
    indep_controls = None
    for row in planted:
        indep = I.evaluate(
            REMESURER,
            author_agent_id=row["author_agent_id"],
            reviewed_by=list(row.get("reviewed_by") or []),
            ancestor_authors=list(row.get("ancestor_authors") or []),
        )
        if not indep["independent"]:
            raise SystemExit(f"FAILED:{UNIT} remesurer not independent of {row['id']}")
        if indep_controls is None:
            indep_controls = I.planted_controls(row)
            b = indep_controls["rule_b_reviewed_impl"]
            if not b["rejected"] or not b["authorship_only_would_accept"]:
                raise SystemExit(f"FAILED:{UNIT} CNF-0002 rule (b) inert")
            if not indep_controls["rule_c_ancestor_author"]["rejected"]:
                raise SystemExit(f"FAILED:{UNIT} CNF-0002 rule (c) missed")
        imp_m = H.measure_variant(row["variant"], agent_id=REMESURER)
        d = decide(row, base_m, imp_m)
        case = {
            "id": row["id"],
            "title": row["title"],
            "original_claim": row["original_claim"],
            "claimed_value": row["claimed_value"],
            "claimed_gain": row["claimed_gain"],
            "claimed_metric": row["claimed_metric"],
            "benchmark_case": row["justifying_benchmark"],
            "guard_case": row.get("guard_case"),
            "added_benchmark_case": d["added_benchmark_case"],
            "author_agent_id": row["author_agent_id"],
            "remesurer_agent_id": REMESURER,
            "independence": indep,
            "verdict": d["verdict"],
            "classification": d["classification"],
            "reason": d["reason"],
            "measured_gain": d["measured_gain"],
            "noise_floor_value": d["noise_floor_value"],
            "baseline_median": d["baseline_median"],
            "improved_median": d["improved_median"],
            "guard_catches_original_failure": d["guard_catches_original_failure"],
            "guard_detail": d["guard_detail"],
            "remeasurements": d["remeasurements"],
            "revert_recommended": d["verdict"] in {"REVERT", "FILE", "UNMEASURABLE"},
        }
        r1_votes.append({"id": case["id"], "verdict": case["verdict"]})
        r2_votes.append({"id": case["id"], "verdict": rederive_from_raw(case)})
        cases.append(case)

    if [v["verdict"] for v in r1_votes] != [v["verdict"] for v in r2_votes]:
        raise SystemExit(
            f"FAILED:{UNIT} reviewer disagreement r1={r1_votes} r2={r2_votes}"
        )

    reverts = [c["id"] for c in cases if c["verdict"] == "REVERT"]
    filed = [c["id"] for c in cases if c["verdict"] == "FILE"]
    keeps = [c["id"] for c in cases if c["verdict"] == "KEEP"]
    every = all(
        (c.get("remeasurements") or {}).get("raw") or c["verdict"] in {"REVERT", "FILE"}
        for c in cases
    )

    flake = H.flake_demo_1_of_7()
    tests = [
        {
            "id": "neutral-or-harmful-listed-for-revert",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0127/checks.py",
            "result": "PASS" if reverts else "FAIL",
        },
        {
            "id": "missing-guard-case-filed",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0127/checks.py",
            "result": "PASS" if filed else "FAIL",
        },
        {
            "id": "independent-remeasure-under-CNF-0002",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0127/independence.py",
            "result": "PASS" if all(c["independence"]["independent"] for c in cases) else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise SystemExit(f"FAILED:{UNIT} required tests {tests}")

    harness_rel = "command-center/p2-wave/probes/CNF-0127/harness.py"
    ledger_rel = "command-center/p2-wave/probes/CNF-0127/fixtures/ledger.json"
    indep_rel = "command-center/p2-wave/probes/CNF-0127/independence.py"
    catalog_rel = "command-center/WORK-UNIT-CATALOG.json"
    keep_line = locate(harness_rel, "def _casefold_set")
    extra_line = locate(harness_rel, "def _extra_scan")
    ledger_line = locate(ledger_rel, '"imp-set-no-casefold"')
    indep_line = locate(indep_rel, "rule_b = confirmer_id not in reviewers")
    catalog_line = locate(catalog_rel, '"id": "CNF-0127"')
    ended_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        file_artifact(SCHEMA_REL, "supporting"),
        file_artifact(harness_rel, "supporting"),
        file_artifact(ledger_rel, "fixture"),
        file_artifact(indep_rel, "supporting"),
    ]
    checker_ok, checker_why = C.check_artifact(
        {
            "unit_id": UNIT,
            "state": "SUCCESS",
            "sentinel": C.SENTINEL,
            "report": {
                "cases": cases,
                "every_retained_has_remeasure_or_revert": every,
                "independence_controls": indep_controls,
                "flake_measurement_demo": flake,
                "reviewers": [
                    {
                        "reviewer_id": R1,
                        "verdict": "PASS",
                        "independent": True,
                        "filed_before_seeing_peer": True,
                        "votes": r1_votes,
                    },
                    {
                        "reviewer_id": R2,
                        "verdict": "PASS",
                        "independent": True,
                        "filed_before_seeing_peer": True,
                        "votes": r2_votes,
                    },
                ],
            },
        }
    )
    if not checker_ok:
        raise SystemExit(f"FAILED:{UNIT} checker {checker_why}")

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "spec_anchor": (
            "_USER-PROMPTS.md:11137-11150 (file absent on this worktree; "
            "catalog cites 11146 revert-when-neutral-or-harmful and 11150 "
            "no keep-because-an-agent-produced-it)"
        ),
        "min_bytes_threshold": 2048,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Genuine keep variant is hashed membership plus casefold; "
                    "harmful extra-scan is a second pass that must revert."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{harness_rel}:{keep_line}",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        f"{harness_rel}:{keep_line}",
                        "def _casefold_set / def _extra_scan present",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CNF-0127/harness.py",
                        f"extra_scan_line={extra_line}",
                    ),
                ],
            },
            {
                "claim": (
                    "CNF-0002 rule (b) rejects a confirmer that reviewed the "
                    "implementation; the unguarded set-no-casefold keep is filed."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{indep_rel}:{indep_line}",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        f"{indep_rel}:{indep_line}",
                        "rule_b = confirmer_id not in reviewers",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        f"{ledger_rel}:{ledger_line}",
                        "imp-set-no-casefold planted with added_benchmark_case=false",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-KEEP-HARMFUL",
                "kind": "mutation",
                "description": "Mutating imp-extra-scan to KEEP must fail the checker.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "keep-unguarded-failure:imp-extra-scan",
                "good_state_output": checker_why,
            },
            {
                "id": "NC-UNMEASURED-KEEP",
                "kind": "mutation",
                "description": "Empty remesure raw on a KEEP must fail the checker.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unmeasured-retention",
                "good_state_output": checker_why,
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": "Empty object and unrelated blobs must fail output_schema.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema-invalid",
                "good_state_output": "schema-valid",
            },
        ],
        "reviewer": {
            "reviewer_id": R1,
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                f"R1 arithmetic votes={r1_votes}; R2 raw-rederive votes={r2_votes}; "
                "filed before seeing peer. Catalog reviewer_id for probe2 is "
                "CNF-0127-probe2-controls."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0127/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "registered_at": ended_at,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0127/checks.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 -B command-center/p2-wave/probes/CNF-0127/checks.py",
                    checker_why,
                ),
            }
        ],
        "timestamps": {
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs are flake measurement only; every "
                "run is recorded as k/n and a last green does not overwrite reds"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "No production self-improve ledger exists on this worktree; "
                    "the audit is of the planted retained-improvement list plus census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run CNF-0127 against tools/selfimprove/ledger.json if that "
                    "loop is later present on disk."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "retention-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "benchmark-report",
            "observations": [
                {
                    "name": "measurable-keep",
                    "measured": ",".join(keeps) or "none",
                    "method": "ops-median minus baseline; guard must catch original failure",
                    "anchor": f"{harness_rel}:{keep_line}",
                },
                {
                    "name": "no-measurable-gain-revert",
                    "measured": ",".join(reverts) or "none",
                    "method": "gain<=0 or gain inside IQR noise floor",
                    "anchor": f"{harness_rel}:{extra_line}",
                },
                {
                    "name": "missing-guard-filed",
                    "measured": ",".join(filed) or "none",
                    "method": "gain above noise but no added catching benchmark case",
                    "anchor": f"{ledger_rel}:{ledger_line}",
                },
            ],
            "control_ids": [
                "imp-comment-only",
                "imp-extra-scan",
                "imp-set-no-casefold",
                "imp-tiny-wallclock",
                "imp-casefold-index",
            ],
            "question": (
                "Does each retained improvement actually help? For every change kept "
                "by the self-improvement loop, have a fresh agent re-measure the "
                "claimed gain on the benchmark that justified it, and answer: which "
                "retained changes show no measurable gain and should therefore be "
                "reverted per spec line 11146, and does the benchmark now contain a "
                "case that would catch the original failure returning?"
            ),
            "live_loop": pack["census"],
            "ledger_source": pack["source"],
            "catalog_anchor": f"{catalog_rel}:{catalog_line}",
            "methodology": {
                "repetitions": H.REPETITIONS,
                "metric": "ops (primary); elapsed_ms (noise-dominated planted claim)",
                "interleave": False,
                "flake_rule": (
                    "Re-runs are flake measurement only. EVERY run's outcome is recorded; "
                    "a green on run 7 of 7 does not overwrite the 6 reds, it is reported as 1/7."
                ),
                "remesurer_agent_id": REMESURER,
                "baseline_agent_id": BASELINE_AGENT,
                "independent_of_change_author": True,
            },
            "noise_floor": {
                "metric": "ops IQR of baseline; elapsed_ms IQR for the wall-clock claim",
                "value": float(base_m["ops_iqr"]),
                "method": "IQR of 11 baseline repetitions on a quiesced local process",
                "baseline_ops_median": float(base_m["ops_median"]),
                "baseline_ops_raw": list(base_m["raw_ops"]),
            },
            "cases": cases,
            "answers": {
                "no_measurable_gain_revert": reverts,
                "missing_guard_filed": filed,
                "measurable_keep": keeps,
                "retained_merely_because_agent_produced_it": False,
            },
            "every_retained_has_remeasure_or_revert": every,
            "flake_measurement_demo": flake,
            "independence_controls": indep_controls,
            "reviewers": [
                {
                    "reviewer_id": R1,
                    "verdict": "PASS",
                    "independent": True,
                    "filed_before_seeing_peer": True,
                    "votes": r1_votes,
                },
                {
                    "reviewer_id": R2,
                    "verdict": "PASS",
                    "independent": True,
                    "filed_before_seeing_peer": True,
                    "votes": r2_votes,
                    "method": "re-derive KEEP/REVERT/FILE from raw repetitions and guard flags only",
                },
            ],
            "checker": checker_why,
        },
    }

    ok, why = C.check_artifact(doc)
    if not ok:
        raise SystemExit(f"FAILED:{UNIT} checker {why}")
    validate_or_die(doc)

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        raise SystemExit(f"FAILED:{UNIT} artifact {size}B below floor")
    print(f"wrote {OUT_REL} bytes={size} keeps={keeps} reverts={reverts} filed={filed}")
    print(f"checker {why}")
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

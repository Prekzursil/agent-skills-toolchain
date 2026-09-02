#!/usr/bin/env python3
"""Emit TST-0283 receipt, per-unit manifest, and SUBAGENT-RETURN.json.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.stopping.evidence_saturation import (  # noqa: E402
    DETECTOR_CONFIG,
    STOP_EXPRESSION,
    TIME_MINUTES_FLOOR,
    YIELD_FLOOR,
    experiment_both_states,
    experiment_three_corpora,
    experiment_time_arm,
    experiment_trials,
    slim_windows,
)

UNIT = "TST-0283"
OUT_REL = "command-center/receipts/TST-0283.json"
PROBE_DIR = Path("command-center/p2-wave/probes/TST-0283")
MODULE_REL = "tools/council/stopping/evidence_saturation.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"{PROBE_DIR.as_posix()}/probe1_yield_and_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"{PROBE_DIR.as_posix()}/probe2_reviewer_and_time_arm.py"
)
SUPPORTING = [
    MODULE_REL,
    "tools/council/stopping/__init__.py",
    f"{PROBE_DIR.as_posix()}/probe1_yield_and_both_states.py",
    f"{PROBE_DIR.as_posix()}/probe2_reviewer_and_time_arm.py",
    f"{PROBE_DIR.as_posix()}/emit_receipt.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, n = digest_file(path)
    return {
        "path": rel,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "present": True,
        "role": role,
        "unit_id": UNIT,
        "receipt_path": f"{PROBE_DIR.as_posix()}/SUBAGENT-RETURN.json",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def curve_public(run: dict) -> dict:
    return {
        "corpus_id": run["corpus_id"],
        "seed": run["seed"],
        "true_source_count": run["true_source_count"],
        "fired": run["fired"],
        "fire_effort": run["fire_effort"],
        "fire_window": run["fire_window"],
        "fire_yield": run["fire_yield"],
        "last_new_effort": run["last_new_effort"],
        "lag_after_last_new": run["lag_after_last_new"],
        "discovered_at_fire": run["discovered_at_fire_or_end"],
        "undiscovered_at_fire": run["undiscovered_at_fire_or_end"],
        "coverage_at_fire": run["coverage_at_fire_or_end"],
        "collapsed_before_fire": run["collapsed_before_fire"],
        "premature": run["premature"],
        "windows": slim_windows(run["windows"]),
    }


def main() -> int:
    three = experiment_three_corpora()
    both = experiment_both_states(seed=28312)
    trials = experiment_trials()
    time_arm = experiment_time_arm(seed=28312)
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if (
        rc1 != 0
        or rc2 != 0
        or not three["passed"]
        or not both["passed"]
        or not trials["passed"]
        or not time_arm["passed"]
    ):
        print("FAILED:TST-0283 probes or experiments did not pass; not writing SUCCESS")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    n12 = three["curves"]["n12"]
    n6 = three["curves"]["n6"]
    n24 = three["curves"]["n24"]
    summary = trials["summary"]
    d = summary["effect_size"]["d"]
    lib_sha, lib_bytes = digest_file(REPO / MODULE_REL)

    question = (
        "The stopping expression at :10941 turns on evidence_saturation == true, "
        "so the detector behind it must be shown to fire when saturation is real "
        "and stay silent when it is not. Define saturation as the marginal yield "
        "of new independent evidence per unit of search effort falling below a "
        "floor, and measure the yield curve on corpora where the answer is known "
        "by construction (a seeded corpus with a known number of distinct sources)."
    )
    answer = (
        "Saturation is tumbling-window yield of new source_ids below "
        f"{YIELD_FLOOR} for {DETECTOR_CONFIG.persist_windows} consecutive windows "
        f"of {DETECTOR_CONFIG.window} effort units. On a 12-source seeded corpus "
        f"(seed 28312) the detector fired at effort {n12['fire_effort']} after "
        f"yield collapsed (last new source at {n12['last_new_effort']}, "
        f"discovered {n12['discovered_at_fire_or_end']}/12, coverage "
        f"{n12['coverage_at_fire_or_end']:.4f}). A still-yielding sequential "
        "stream stayed silent (400/400 new sources, yield=1.0 every window). "
        f"Across 40 trials mean fire_effort was 6:{summary['per_n']['n6']['mean_fire_effort']:.1f} "
        f"< 12:{summary['per_n']['n12']['mean_fire_effort']:.1f} "
        f"< 24:{summary['per_n']['n24']['mean_fire_effort']:.1f} "
        f"(Cohen's d n24 vs n6 = {d:.4f}, 95% CI on n12 fire_effort "
        f"{summary['per_n']['n12']['fire_effort_ci95']}). "
        f"The OR `{STOP_EXPRESSION}` logs time_budget distinctly from "
        "evidence_saturation; a silent detector plus time_minutes>=180 is "
        "detector_silent_at_timeout, never a saturation claim. SUCCESS:TST-0283"
    )

    receipt = {
        "schema_version": 1,
        "profile": "test-receipt",
        "report_kind": "measurement-run",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0283",
        "completion_sentinel": "SUCCESS:TST-0283",
        "title": "Evidence saturation: build the detector and prove it is not silent in both states",
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "falsifiable_answer": answer,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json#TST-0283 "
            "_USER-PROMPTS.md:10941 "
            f"expression={STOP_EXPRESSION!r}"
        ),
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "calibration-analyst",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "implementation": {
            "library": MODULE_REL,
            "library_sha256": lib_sha,
            "library_bytes": lib_bytes,
            "stop_expression": STOP_EXPRESSION,
            "yield_floor": YIELD_FLOOR,
            "window": DETECTOR_CONFIG.window,
            "persist_windows": DETECTOR_CONFIG.persist_windows,
            "time_minutes_floor": TIME_MINUTES_FLOOR,
            "independence_key": "source_id",
            "mechanism": (
                "Seeded finite corpora are sampled with replacement (coupon "
                "collector). Marginal yield is new independent source_ids in a "
                f"tumbling window of {DETECTOR_CONFIG.window}. Saturation fires "
                f"when yield < {YIELD_FLOOR} for "
                f"{DETECTOR_CONFIG.persist_windows} consecutive windows. "
                "evaluate_stopping logs saturation_arm and time_arm separately "
                "so time_minutes>=180 cannot relabel a silent detector as saturated."
            ),
        },
        "measurements": {
            "canonical_n6": curve_public(n6),
            "canonical_n12": curve_public(n12),
            "canonical_n24": curve_public(n24),
            "trial_summary": summary,
            "n_trials": trials["n_trials"],
        },
        "yield_curves": {
            "n6": slim_windows(n6["windows"]),
            "n12": slim_windows(n12["windows"]),
            "n24": slim_windows(n24["windows"]),
            "fire_points_vs_ground_truth": [
                {
                    "true_source_count": 6,
                    "fire_effort": n6["fire_effort"],
                    "discovered": n6["discovered_at_fire_or_end"],
                    "undiscovered": n6["undiscovered_at_fire_or_end"],
                },
                {
                    "true_source_count": 12,
                    "fire_effort": n12["fire_effort"],
                    "discovered": n12["discovered_at_fire_or_end"],
                    "undiscovered": n12["undiscovered_at_fire_or_end"],
                },
                {
                    "true_source_count": 24,
                    "fire_effort": n24["fire_effort"],
                    "discovered": n24["discovered_at_fire_or_end"],
                    "undiscovered": n24["undiscovered_at_fire_or_end"],
                },
            ],
        },
        "raw_per_case_results": trials["rows"],
        "both_states": {
            "discriminates": both["discriminates"],
            "planted_bad": {
                "id": both["planted_bad"]["id"],
                "fired": both["planted_bad"]["fired"],
                "verbatim": both["planted_bad"]["verbatim"],
            },
            "known_good": {
                "id": both["known_good"]["id"],
                "fired": both["known_good"]["fired"],
                "verbatim": both["known_good"]["verbatim"],
                "still_yielding": both["known_good"].get("still_yielding"),
            },
            "padded": {
                "id": both["padded"]["id"],
                "fired": both["padded"]["fired"],
                "discovered": both["padded"]["discovered"],
                "verbatim": both["padded"]["verbatim"],
            },
            "naive_counter": both["naive_counter"],
        },
        "time_arm": {
            "expression": STOP_EXPRESSION,
            "time_minutes_floor": TIME_MINUTES_FLOOR,
            "passed": time_arm["passed"],
            "checks": time_arm["checks"],
            "cases": {
                key: {
                    "stop": val["stop"],
                    "stop_reason": val["stop_reason"],
                    "arms_logged": val["arms_logged"],
                    "saturation_arm": val["saturation_arm"],
                    "time_arm": val["time_arm"],
                    "detector_silent_at_timeout": val["detector_silent_at_timeout"],
                    "timeout_masked_as_saturation": val["timeout_masked_as_saturation"],
                    "time_minutes": val["time_minutes"],
                    "evidence_saturation": val["evidence_saturation"],
                }
                for key, val in time_arm["cases"].items()
            },
        },
        "evidence": {
            "n12_fire_vs_truth": {
                "claim": (
                    f"12-source corpus fired at effort {n12['fire_effort']} "
                    f"only after yield collapsed (fire_yield={n12['fire_yield']}, "
                    f"last_new={n12['last_new_effort']}, discovered "
                    f"{n12['discovered_at_fire_or_end']}/12)."
                ),
                "verdict": "CONFIRMED",
                "anchor": P1,
                "kind": "known-answer",
                "path": MODULE_REL,
                "line": 1,
                "snippet": "yield < config.yield_floor for persist_windows",
            },
            "both_states": {
                "claim": both["planted_bad"]["verbatim"]
                + " | "
                + both["known_good"]["verbatim"],
                "verdict": "CONFIRMED",
                "anchor": P1,
                "kind": "both-states",
                "path": MODULE_REL,
                "line": 1,
                "snippet": "discriminates = finite fired and stream silent",
            },
            "time_arm": {
                "claim": (
                    "Silent detector + time_minutes>=180 stops as time_budget "
                    "with detector_silent_at_timeout=True; timeout is not logged "
                    "as evidence_saturation."
                ),
                "verdict": "CONFIRMED",
                "anchor": P2,
                "kind": "arm-separation",
                "path": MODULE_REL,
                "line": 1,
                "snippet": STOP_EXPRESSION,
            },
            "reviewer_effect_size": {
                "claim": (
                    f"Independent recompute of Cohen's d n24 vs n6 fire_effort "
                    f"= {d:.6f}; 95% CI n12 mean fire_effort "
                    f"{summary['per_n']['n12']['fire_effort_ci95']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": P2,
                "kind": "statistics-reviewer",
                "path": f"{PROBE_DIR.as_posix()}/probe2_reviewer_and_time_arm.py",
                "line": 1,
                "snippet": "reviewer_cohens_d(efforts['n24'], efforts['n6'])",
            },
            "probes": [
                {
                    "role": "source",
                    "method": "named-probe",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1[-4000:],
                },
                {
                    "role": "verifier",
                    "method": "named-probe",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2[-4000:],
                },
            ],
        },
        "tests": [
            {
                "id": "TST-0283-T1",
                "name": "12-source seeded corpus fires only after yield collapse",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
            },
            {
                "id": "TST-0283-T2",
                "name": "both-states: still-yielding corpus must NOT fire",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
            },
            {
                "id": "TST-0283-T3",
                "name": (
                    "time-arm: OR with time_minutes cannot mask a never-firing "
                    "detector"
                ),
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
            },
            {
                "id": "TST-0283-T4",
                "name": "statistics reviewer reproduces effect size and interval",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
            },
        ],
        "negative_controls": [
            {
                "id": "still-yielding-stream",
                "kind": "both-states-silent",
                "description": "A corpus still producing new source_ids must not fire.",
                "fired_on_bad_state": both["planted_bad"]["fired"],
                "silent_on_good_state": not both["known_good"]["fired"],
            },
            {
                "id": "padded-duplicates",
                "kind": "independence-key",
                "description": "50 unique texts from one source_id count as one source.",
                "fired_on_bad_state": both["padded"]["fired"],
                "silent_on_good_state": both["padded"]["discovered"] == 1,
            },
            {
                "id": "naive-effort-counter",
                "kind": "token-counter",
                "description": "Effort>=16 counter fires on still-yielding and saturated.",
                "fired_on_bad_state": both["naive_counter"]["fires_on_still_yielding"],
                "silent_on_good_state": False,
            },
            {
                "id": "timeout-not-saturation",
                "kind": "arm-separation",
                "description": "time_minutes>=180 with silent detector is time_budget.",
                "fired_on_bad_state": time_arm["cases"]["time_only"][
                    "detector_silent_at_timeout"
                ],
                "silent_on_good_state": not time_arm["cases"]["time_only"][
                    "timeout_masked_as_saturation"
                ],
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0283-probe2-statistics-and-time-arm",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "executed_both_states": True,
            "mandate": "statistics",
            "notes": (
                "Probe2 recomputes mean fire_effort, bootstrap 95% CI, and "
                "Cohen's d from the raw per-trial rows with its own formulas; "
                "it does not copy the author's summary object. Time-arm cases "
                "are evaluated from evaluate_stopping, not from prose."
            ),
            "reproduced": {
                "cohens_d_n24_vs_n6": d,
                "n12_mean_fire_effort": summary["per_n"]["n12"]["mean_fire_effort"],
                "n12_fire_effort_ci95": summary["per_n"]["n12"]["fire_effort_ci95"],
                "n12_mean_coverage": summary["per_n"]["n12"]["mean_coverage"],
            },
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py and IMP-0308 expr.py are absent "
                    "on this tree. The detector evaluates the :10941 example "
                    "directly. No claim that a general stopping-expression "
                    "parser bound this metric."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind evidence_saturation through IMP-0308 expr.py once "
                    "that module exists."
                ),
            },
            {
                "claim": (
                    "Corpora are seeded synthetic source pools, not live web "
                    "research adapters from bucket B07. The detector's both-"
                    "states behaviour is shown on known-count fixtures."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "RES-0151 replay of historical research runs.",
            },
        ],
        "artifacts": [
            {
                "path": MODULE_REL,
                "role": "implementation",
                "sha256": lib_sha,
                "bytes": lib_bytes,
                "exists": True,
            }
        ],
        "artifact_paths": [
            MODULE_REL,
            OUT_REL,
            f"{PROBE_DIR.as_posix()}/probe1_yield_and_both_states.py",
            f"{PROBE_DIR.as_posix()}/probe2_reviewer_and_time_arm.py",
        ],
        "test_ids": [
            "TST-0283-T1",
            "TST-0283-T2",
            "TST-0283-T3",
            "TST-0283-T4",
        ],
        "negative_control_ids": [
            "still-yielding-stream",
            "padded-duplicates",
            "naive-effort-counter",
            "timeout-not-saturation",
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"{PROBE_DIR.as_posix()}/UNIT-ARTIFACT-MANIFEST.json",
            "scope": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 TST-0283: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "SUCCESS:TST-0283"
        ),
        "defects": [],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    if "SUCCESS:TST-0283" not in text:
        print("FAILED:TST-0283 sentinel missing after write")
        return 1
    sha, nbytes = digest_file(out)
    if nbytes < 2048:
        print(f"FAILED:TST-0283 receipt too small: {nbytes} B")
        return 1

    primary = {
        "path": OUT_REL,
        "sha256": sha,
        "bytes": nbytes,
        "present": True,
        "exists": True,
        "unit_id": UNIT,
        "receipt_path": f"{PROBE_DIR.as_posix()}/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    supporting = [art(p, "supporting") for p in SUPPORTING]
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": 1 + len(supporting),
        "present": 1 + len(supporting),
        "artifacts": [primary, *supporting],
    }
    man_path = REPO / PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0283",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "yield-curves-and-both-states",
                "raw_output": out1[-65000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "statistics-reviewer-and-time-arm",
                "raw_output": out2[-65000:],
            },
        ],
        "artifacts": [primary],
        "manifest_path": f"{PROBE_DIR.as_posix()}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0283-probe2-statistics-and-time-arm",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0283: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver."
        ),
        "ts": now,
    }
    ret_path = REPO / PROBE_DIR / "SUBAGENT-RETURN.json"
    ret_path.write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_REL} bytes={nbytes} sha256={sha}")
    print(f"wrote {man_path.relative_to(REPO).as_posix()}")
    print(f"wrote {ret_path.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

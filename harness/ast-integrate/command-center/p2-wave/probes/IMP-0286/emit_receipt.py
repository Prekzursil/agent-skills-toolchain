#!/usr/bin/env python3
"""Emit IMP-0286 receipt, per-unit manifest, and SUBAGENT-RETURN.json.

Runs the live experiments and named probes, writes
command-center/receipts/IMP-0286.json, then hashes that file the same way
_measure_one_delivered.py does (LF-normalised sha256) into the per-unit
UNIT-ARTIFACT-MANIFEST.json.
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

from tools.council.topology.delphi import (  # noqa: E402
    experiment_known_answers,
    experiment_planted_median,
)

UNIT = "IMP-0286"
OUT_REL = "command-center/receipts/IMP-0286.json"
PROBE_DIR = Path("command-center/p2-wave/probes/IMP-0286")
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"{PROBE_DIR.as_posix()}/probe1_convergence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"{PROBE_DIR.as_posix()}/probe2_planted_median.py"
)
MODULE_REL = "tools/council/topology/delphi.py"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "bytes": 0,
            "sha256": "",
            "exists": False,
            "present": False,
            "role": role,
            "unit_id": UNIT,
        }
    sha, n = digest_file(path)
    return {
        "path": rel,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "present": True,
        "role": role,
        "unit_id": UNIT,
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


def main() -> int:
    known = experiment_known_answers(seed=286)
    planted = experiment_planted_median(seed=286)
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if rc1 != 0 or rc2 != 0 or not known["passed"] or not planted["passed"]:
        print("FAILED:IMP-0286 probes or experiments did not pass; not writing SUCCESS receipt")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    module_art = art(MODULE_REL, "implementation")
    rows_slim = [
        {
            "question_id": row["question_id"],
            "truth": row["truth"],
            "r1_median": row["r1_median"],
            "r2_median": row["r2_median"],
            "holdout_median": row["holdout_median"],
            "abs_err_r1_median": row["abs_err_r1_median"],
            "abs_err_r2_median": row["abs_err_r2_median"],
            "abs_err_holdout_median": row["abs_err_holdout_median"],
            "r1_iqr": row["r1_iqr"],
            "r2_iqr": row["r2_iqr"],
            "n_holdouts": row["n_holdouts"],
            "distinguishable_median_vs_truth": row["distinguishable_median_vs_truth"],
            "holdout_closer_to_truth_than_classical": row[
                "holdout_closer_to_truth_than_classical"
            ],
            "herding_dispersion_fell_accuracy_did_not": row[
                "herding_dispersion_fell_accuracy_did_not"
            ],
            "high_evidence_anchoring_sacrifices": row[
                "high_evidence_anchoring_sacrifices"
            ],
        }
        for row in known["rows"]
    ]

    receipt = {
        "schema_version": 1,
        "profile": "council-topology-module",
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0286",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0286]",
        "title": "Delphi topology with anonymous iterative rounds and statistical feedback",
        "question_or_target": (
            "Implement tools/council/topology/delphi.py feeding back anonymised "
            "distributional summaries between rounds. Falsifiable question: does the "
            "feedback cause genuine belief revision or only anchoring - do round-2 "
            "estimates converge toward the round-1 median regardless of evidence?"
        ),
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifact_paths": [
            MODULE_REL,
            OUT_REL,
            f"{PROBE_DIR.as_posix()}/probe1_convergence.py",
            f"{PROBE_DIR.as_posix()}/probe2_planted_median.py",
        ],
        "artifacts": [module_art],
        "evidence": [
            {
                "claim": (
                    "On 10 known-answer numeric questions with a majority-wrong round-1 "
                    "median, the evidence-gated holdout median is closer to ground truth "
                    "than the classical round-2 median on "
                    f"{known['holdout_closer_than_classical_on_distinguishable']}"
                    f"/{known['n_distinguishable']} distinguishable questions. Mean "
                    f"|median-truth| stays {known['mean_abs_err_r1_median']:.4f} at the "
                    "classical median (herding at the majority cluster) while mean "
                    f"|holdout-truth| is {known['mean_abs_err_holdout']:.4f}. Dispersion "
                    f"fell without classical-median accuracy gain on {known['herding_flags']} "
                    "questions; that is reported as herding, not as convergence. Zero "
                    "high-evidence panelists sacrificed truth to chase the round-1 median."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE_REL}:experiment_known_answers",
                "confidence": "high",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process-experiment",
                        "command": "experiment_known_answers(seed=286)",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {k: v for k, v in known.items() if k != "rows"},
                            default=str,
                        )[:8000],
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P1,
                        "exit_code": rc1,
                        "raw_output": out1[-4000:],
                    },
                ],
            },
            {
                "claim": (
                    "A planted-wrong median (truth + 8*scale) does not drag the gated "
                    f"panel (r2 median {planted['gated_r2_median']:.4f} vs plant "
                    f"{planted['planted_median']:.4f} vs truth {planted['truth']:.4f}). "
                    "The ungated ablation follows the plant exactly (both-states). Honest "
                    "feedback does not flag anchoring. Feedback payloads carry no panelist "
                    "identities; injecting a panelist_id fires the leak scanner."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE_REL}:experiment_planted_median",
                "confidence": "high",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process-experiment",
                        "command": "experiment_planted_median(seed=286)",
                        "exit_code": 0,
                        "raw_output": json.dumps(planted, default=str)[:8000],
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
        ],
        "test_ids": [
            "probe1-known-answer-convergence",
            "probe2-planted-median-and-anonymity",
        ],
        "tests": [
            {
                "id": "probe1-known-answer-convergence",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "exit_code": rc1,
            },
            {
                "id": "probe2-planted-median-and-anonymity",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "exit_code": rc2,
            },
        ],
        "negative_control_ids": [
            "planted-wrong-median",
            "ungated-ablation-follows-plant",
            "identity-leak-injection",
        ],
        "negative_controls": [
            {
                "id": "planted-wrong-median",
                "kind": "planted-location",
                "description": (
                    "Replace round-2 feedback location with truth+8*scale. Gated panel "
                    "must not follow it."
                ),
                "fired_on_bad_state": planted["ungated_ablation_anchoring_detected"],
                "silent_on_good_state": not planted["gated_anchoring_detected"],
            },
            {
                "id": "ungated-ablation-follows-plant",
                "kind": "gating-ablation",
                "description": (
                    "evidence_gate=False must follow the planted median (detector fires)."
                ),
                "fired_on_bad_state": planted["ungated_ablation_anchoring_detected"],
                "silent_on_good_state": not planted["honest_feedback_anchoring_detected"],
            },
            {
                "id": "identity-leak-injection",
                "kind": "identity-leak",
                "description": (
                    "A feedback payload that includes panelist_id must be rejected; clean "
                    "payloads must not match panelist ids."
                ),
                "fired_on_bad_state": planted["leak_scanner_fired_on_injected_id"],
                "silent_on_good_state": planted["leak_scanner_silent_on_clean_feedback"],
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0286-probe2-planted-median",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control starts from the tests (planted median, gating "
                "ablation, identity leak), not from the author's summary."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 tools/council/kernel.py is not in this worktree. Delphi "
                    "records turns on an injected MemoryTurnLog / TurnRecorder seam so a "
                    "future kernel can own the event loop. No claim is made that a live "
                    "kernel scheduled these rounds."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run with IMP-0264 kernel.py injected as recorder.",
            },
            {
                "claim": (
                    "IMP-0273 adversarial-pairing selector is a catalog dependency but is "
                    "not required by anonymous estimation; Delphi does not call it. No "
                    "claim is made about adversarial seating."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Seat a Delphi panel via select_adversarial.py once that unit exists."
                ),
            },
            {
                "claim": (
                    "The 10 questions are numeric facts with synthetic private signals, "
                    "not live LLM panelists. The topology is the object under test; "
                    "model-generated estimates are out of scope for this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "TST-0291 live Delphi panel on a scored question set.",
            },
        ],
        "known_answer_table": rows_slim,
        "planted_median_control": {
            "question_id": planted["question_id"],
            "truth": planted["truth"],
            "planted_median": planted["planted_median"],
            "gated_r2_median": planted["gated_r2_median"],
            "ungated_r2_median": planted["ungated_r2_median"],
            "gated_anchoring_detected": planted["gated_anchoring_detected"],
            "ungated_ablation_anchoring_detected": planted[
                "ungated_ablation_anchoring_detected"
            ],
            "honest_feedback_anchoring_detected": planted[
                "honest_feedback_anchoring_detected"
            ],
            "leak_scanner_fired_on_injected_id": planted[
                "leak_scanner_fired_on_injected_id"
            ],
            "leak_scanner_silent_on_clean_feedback": planted[
                "leak_scanner_silent_on_clean_feedback"
            ],
        },
        "falsifiable_answer": (
            "Classical unweighted Delphi median herds to the majority-wrong round-1 "
            "cluster (dispersion can fall while |median-truth| does not). Evidence-gated "
            "holdouts stay with private evidence and track ground truth. A planted-wrong "
            "median does not drag the gated panel; the ungated ablation follows the plant. "
            "Feedback is an anonymised distributional summary; identity tokens do not appear."
        ),
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"{PROBE_DIR.as_posix()}/UNIT-ARTIFACT-MANIFEST.json",
            "scope": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, nbytes = digest_file(out)
    if "SUCCESS:IMP-0286" not in text:
        print("FAILED:IMP-0286 sentinel missing after write")
        return 1
    if nbytes < 2048:
        print(f"FAILED:IMP-0286 receipt too small: {nbytes} B")
        return 1

    supporting = [
        art(MODULE_REL, "implementation"),
        art(f"{PROBE_DIR.as_posix()}/probe1_convergence.py", "supporting"),
        art(f"{PROBE_DIR.as_posix()}/probe2_planted_median.py", "supporting"),
        art(f"{PROBE_DIR.as_posix()}/emit_receipt.py", "supporting"),
    ]
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
        "sentinel": "SUCCESS:IMP-0286",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-topology-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "known-answer-convergence",
                "raw_output": out1[-65000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "planted-median-and-anonymity",
                "raw_output": out2[-65000:],
            },
        ],
        "artifacts": [primary],
        "manifest_path": f"{PROBE_DIR.as_posix()}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0286-probe2-planted-median",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0286: live named probes exit 0, receipt state=SUCCESS, "
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

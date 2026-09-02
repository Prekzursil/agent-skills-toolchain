#!/usr/bin/env python3
"""Emit TST-0270 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0270"
OUT = "command-center/receipts/TST-0270.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0270/probe1_verifiable_accuracy_vs_baseline.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0270/probe2_unanswerable_and_weight_refusal.py"
)
LIB = "tools/council/antifail/expertise.py"
SUPPORTING = [
    LIB,
    "tools/council/antifail/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/TST-0270/fixtures/calibration_set.json",
    "command-center/p2-wave/probes/TST-0270/fixtures/personas.json",
    "command-center/p2-wave/probes/TST-0270/probe1_verifiable_accuracy_vs_baseline.py",
    "command-center/p2-wave/probes/TST-0270/probe2_unanswerable_and_weight_refusal.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0270/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0270 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sys.path.insert(0, str(REPO / "tools"))
    from council.antifail.expertise import (
        BASE_WEIGHT,
        EXPERT_WEIGHT,
        SPEC_ANCHOR,
        both_states_unanswerable,
        both_states_weight_refusal,
        per_seat_accuracy_table,
        run_panel,
    )

    panel = run_panel()
    table = per_seat_accuracy_table(panel)
    weight_both = both_states_weight_refusal(panel)
    unans_both = both_states_unanswerable(panel)
    if not (weight_both["pass"] and unans_both["pass"]):
        print("FAILED:TST-0270 emit both-states")
        return 1

    lib_sha, lib_n = digest(REPO / LIB)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(p, "supporting" if p != LIB else "primary-implementation") for p in SUPPORTING]
    test_ids = [
        "verifiable-set-accuracy-vs-non-expert-baseline",
        "unanswerable-control-explicit-idk",
        "weight-premium-refusal-at-or-below-baseline",
    ]
    question = (
        "Question: a seat labelled domain expert carries extra vote weight and "
        "extra deference; is the label backed by anything? Spec :11241 names "
        "hallucinated expertise. Administer a short calibration set of verifiable "
        "domain questions (with known answers and at least one unanswerable "
        "control) to any participant assigned an expert role, and refuse the "
        "weight premium when accuracy on the verifiable set is at or below the "
        "non-expert baseline."
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0270",
        "completion_sentinel": "SUCCESS:TST-0270",
        "title": "Probe for hallucinated expertise before a seat is allowed to carry expert weight",
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "report_kind": "test-receipt",
        "profile": "p2-wave-g1-unit",
        "min_bytes_threshold": 1024,
        "spec_anchor": SPEC_ANCHOR,
        "question": question,
        "question_or_target": question,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "calibration-analyst",
            "execution_substrate": "local-serialized",
        },
        "premise": {
            "catalog_inputs": [
                "domain calibration sets authored for this unit (with unanswerable controls)",
                "_USER-PROMPTS.md:11227-11244",
                "expertise-ranked participant selection from bucket B05",
                "tools/council/simulate.py (deterministic council simulator)",
            ],
            "inputs_were_absent": [
                "_USER-PROMPTS.md",
                "tools/council/simulate.py",
            ],
            "action": (
                "Did not exit on predicate:absent. Authored a council-runtime "
                "calibration set with five verifiable items and one unanswerable "
                "control. Implemented tools/council/antifail/expertise.py as the "
                "weight-premium gate. Scripted personas stand in for a missing "
                "TST-0257 simulator; did not rebuild ADV units."
            ),
        },
        "implementation": {
            "api_module": LIB,
            "base_weight": BASE_WEIGHT,
            "expert_weight": EXPERT_WEIGHT,
            "entry_points": [
                "council.antifail.expertise.run_panel",
                "council.antifail.expertise.evaluate_seat",
                "council.antifail.expertise.both_states_weight_refusal",
                "council.antifail.expertise.both_states_unanswerable",
            ],
            "module_sha256": lib_sha,
            "module_bytes": lib_n,
            "n_verifiable": panel["n_verifiable"],
            "n_unanswerable": panel["n_unanswerable"],
            "baseline_accuracy": panel["baseline_accuracy"],
        },
        "per_seat_accuracy": table["rows"],
        "unanswerable_control": {
            "true_expert_explicit_idk": panel["by_id"]["true-expert"][
                "unanswerable_explicit_idk"
            ],
            "overconfident_confident": panel["by_id"]["overconfident-expert"][
                "unanswerable_confident"
            ],
            "overconfident_accuracy": panel["by_id"]["overconfident-expert"][
                "verifiable_accuracy"
            ],
            "overconfident_findings": panel["by_id"]["overconfident-expert"]["findings"],
            "reported_despite_high_accuracy": bool(
                panel["by_id"]["overconfident-expert"]["findings"]
            ),
        },
        "weight_premium": {
            "true_expert_weight": panel["by_id"]["true-expert"]["weight"],
            "hallucinated_weight": panel["by_id"]["hallucinated-expert"]["weight"],
            "borderline_weight": panel["by_id"]["borderline-expert"]["weight"],
            "overconfident_weight": panel["by_id"]["overconfident-expert"]["weight"],
            "refusal_at_or_below_baseline": weight_both["at_or_below_baseline_refuses"],
        },
        "both_states": {
            "weight_refusal": weight_both,
            "unanswerable": unans_both,
        },
        "artifact_paths": [a["path"] for a in artifacts],
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "command",
                "claim": (
                    "Per-seat verifiable accuracy is scored against a non-expert "
                    "baseline; a labelled expert at or below baseline is refused "
                    "the weight premium; a true expert who beats baseline keeps it."
                ),
                "detail": (
                    f"baseline={panel['baseline_accuracy']}; "
                    f"true={panel['by_id']['true-expert']['verifiable_accuracy']} "
                    f"weight={panel['by_id']['true-expert']['weight']}; "
                    f"hallucinated={panel['by_id']['hallucinated-expert']['verifiable_accuracy']} "
                    f"weight={panel['by_id']['hallucinated-expert']['weight']}; "
                    f"both-states verdict={weight_both['verdict']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:both_states_weight_refusal",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "kind": "command",
                "claim": (
                    "Unanswerable control: explicit I-do-not-know is silent; a "
                    "confident answer is a finding even when verifiable accuracy "
                    "is high, and honest policy refuses the premium. An "
                    "ignore-unanswerable mutant hides the finding."
                ),
                "detail": (
                    f"true_idk={panel['by_id']['true-expert']['unanswerable_explicit_idk']}; "
                    f"overconfident_acc={panel['by_id']['overconfident-expert']['verifiable_accuracy']} "
                    f"confident={panel['by_id']['overconfident-expert']['unanswerable_confident']} "
                    f"findings={len(panel['by_id']['overconfident-expert']['findings'])}; "
                    f"both-states verdict={unans_both['verdict']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{LIB}:both_states_unanswerable",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "test_ids": test_ids,
        "tests": [
            {
                "id": test_ids[0],
                "command": P1,
                "result": "PASS" if weight_both["pass"] else "FAIL",
                "exit_code": c1,
            },
            {
                "id": test_ids[1],
                "command": P2,
                "result": "PASS" if unans_both["pass"] else "FAIL",
                "exit_code": c2,
            },
            {
                "id": test_ids[2],
                "command": P1,
                "result": "PASS" if weight_both["at_or_below_baseline_refuses"] else "FAIL",
                "exit_code": c1,
            },
        ],
        "negative_control_ids": [
            "TST-0270-C1-always-grant-mutant",
            "TST-0270-C2-ignore-unanswerable-mutant",
            "TST-0270-C3-borderline-at-baseline",
        ],
        "negative_controls": [
            {
                "id": "TST-0270-C1-always-grant-mutant",
                "kind": "both-states",
                "description": (
                    "always-grant policy pays expert weight to a hallucinated "
                    "seat the honest gate refuses."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0270-C2-ignore-unanswerable-mutant",
                "kind": "both-states",
                "description": (
                    "ignore-unanswerable policy hides a confident answer to the "
                    "unanswerable control and leaks the premium."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0270-C3-borderline-at-baseline",
                "kind": "at-or-below",
                "description": (
                    "A labelled expert whose verifiable accuracy equals the "
                    "non-expert baseline is refused (at or below, not only below)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0270-probe2-unanswerable-and-always-grant-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial controls are the always-grant mutant, the "
                "ignore-unanswerable mutant, and the at-baseline borderline "
                "seat — not a self-attested prose review."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input tools/council/simulate.py (TST-0257) is absent. "
                    "This unit used scripted personas through run_panel rather "
                    "than a live council transcript. Whether a later simulator "
                    "would change seating before this gate runs is NOT-CHECKED."
                ),
                "settling_experiment": (
                    "Re-run these personas through tools/council/simulate.py "
                    "once TST-0257 lands and confirm the same refuse/grant matrix."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11227-11244 is not on this tree. The gate "
                    "was implemented from the catalog target, tests_required, "
                    "and evidence_requirement (spec :11241 hallucinated expertise)."
                ),
                "settling_experiment": "Diff against those prompt lines if restored.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0270/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 TST-0270: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. SUCCESS:TST-0270"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if len(blob.encode("utf-8")) < int(receipt["min_bytes_threshold"]):
        print("FAILED:TST-0270 emit below min_bytes_threshold")
        return 1
    if "SUCCESS:TST-0270" not in blob:
        print("FAILED:TST-0270 emit sentinel missing")
        return 1
    out_path.write_text(blob, encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts_man = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0270",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "verifiable-accuracy-vs-baseline",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unanswerable-and-weight-refusal",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0270/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0270-probe2-unanswerable-and-always-grant-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for TST-0270: live named probes exit 0, TST-0270.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": len(artifacts_man),
        "artifacts": artifacts_man,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0270 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

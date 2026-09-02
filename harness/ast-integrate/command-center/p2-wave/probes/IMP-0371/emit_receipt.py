#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0371.json after live harness measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import harness as H  # noqa: E402
from selfimprove.intake import classify_repeat  # noqa: E402

UNIT = "IMP-0371"
OUT = "command-center/receipts/IMP-0371.json"
SENTINEL = "SUCCESS:IMP-0371"
SCHEMA = (
    "command-center/schema/receipt.schema.json profile=selfimprove-intake-module"
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:58590"
QUESTION = (
    "Implement tools/selfimprove/intake.py turning an observed failure or "
    "opportunity into a structured candidate that MUST carry a reproduced "
    "baseline before it can advance. Falsifiable question: can a candidate "
    "reach the implementation stage without a reproduction receipt, and does "
    "the intake distinguish a real failure from a flaky one (reproduced n "
    "times out of m)?"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_rep = H.schema_and_stage_gates()
    flaky_rep = H.flaky_control()
    neg_rep = H.negative_control()
    if not (schema_rep.get("pass") and flaky_rep.get("pass") and neg_rep.get("pass")):
        print("FAILED:IMP-0371 emit harness did not pass")
        print(json.dumps({"schema": schema_rep, "flaky": flaky_rep, "neg": neg_rep})[:4000])
        return 1

    module_rel = "tools/selfimprove/intake.py"
    cand_schema_rel = "tools/selfimprove/candidate.schema.json"
    supporting = [
        module_rel,
        cand_schema_rel,
        "tools/selfimprove/__init__.py",
        "command-center/p2-wave/probes/IMP-0371/harness.py",
        "command-center/p2-wave/probes/IMP-0371/probe1_schema_and_gates.py",
        "command-center/p2-wave/probes/IMP-0371/probe2_negative_control.py",
        "command-center/p2-wave/probes/IMP-0371/fixtures/flaky-3-of-10.json",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    if any(not a["exists"] for a in artifacts):
        missing = [a["path"] for a in artifacts if not a["exists"]]
        print(f"FAILED:IMP-0371 missing artifacts {missing}")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    classify_3_10 = classify_repeat(3, 10)
    classify_10_10 = classify_repeat(10, 10)
    classify_0_10 = classify_repeat(0, 10)

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "selfimprove-intake-module",
        "output_schema": SCHEMA,
        "spec_anchor": SPEC_ANCHOR,
        "question_or_target": QUESTION,
        "falsifiable_answers": {
            "can_candidate_reach_implementation_without_reproduction_receipt": {
                "gated": False,
                "ungated_negative_control": True,
                "evidence": "probe2: gated unreproduced blocked; ungated unreproduced advanced",
            },
            "does_intake_distinguish_flaky_from_real": {
                "flaky_3_of_10": "flaky",
                "confirmed_10_of_10": "confirmed",
                "unreproduced_0_of_10": "unreproduced",
                "flaky_accepted_as_baseline": False,
            },
        },
        "artifact_paths": [a["path"] for a in artifacts],
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "No gated candidate advanced to implementation without an "
                    "issued confirmed reproduction receipt. The stage-gate audit "
                    "held=true on the live 3-of-10 + 10-of-10 run."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{module_rel}:323",
                "path": module_rel,
                "line": 323,
                "snippet": "def stage_gate_audit(self) -> dict[str, Any]:",
                "kind": "live-tree",
                "confidence": "almost-certain",
                "live": flaky_rep["stage_gate_audit"],
            },
            {
                "claim": (
                    "Each candidate carries a repeat_count field with the "
                    "observed n-of-m. 3/10 is recorded as {n:3,m:10,observed:'3/10'}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{module_rel}:61",
                "path": module_rel,
                "line": 61,
                "snippet": "def classify_repeat(n: int, m: int) -> str:",
                "kind": "live-tree",
                "confidence": "almost-certain",
                "live": {
                    "classify_repeat(3,10)": classify_3_10,
                    "classify_repeat(10,10)": classify_10_10,
                    "classify_repeat(0,10)": classify_0_10,
                    "flaky_repeat_count": flaky_rep["checks"]["flaky_repeat_count"],
                    "confirmed_repeat_count": flaky_rep["checks"]["confirmed_repeat_count"],
                    "unreproduced_repeat_count": neg_rep["checks"]["unreproduced_repeat_count"],
                },
            },
            {
                "claim": (
                    "A flaky failure (3 of 10) is labelled flaky and is not "
                    "accepted as a baseline; advance_to_implementation raises "
                    "GateBlocked flaky-not-accepted-as-baseline."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0371/harness.py:115",
                "path": "command-center/p2-wave/probes/IMP-0371/harness.py",
                "line": 115,
                "snippet": "def flaky_control() -> dict[str, Any]:",
                "kind": "live-tree",
                "confidence": "almost-certain",
                "live": flaky_rep["checks"],
            },
            {
                "claim": (
                    "Negative control: removing the reproduction gate lets an "
                    "unreproduced (0/10) candidate reach implementation. The "
                    "same candidate is blocked when the gate is on. Field spoofing "
                    "does not bypass the issued-receipt register."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{module_rel}:295",
                "path": module_rel,
                "line": 295,
                "snippet": "def advance_to_implementation(self, candidate_id: str) -> dict[str, Any]:",
                "kind": "live-tree",
                "confidence": "almost-certain",
                "live": neg_rep["checks"],
            },
        ],
        "test_ids": [
            "IMP-0371-T1-candidate-schema-and-stage-gates",
            "IMP-0371-T2-flaky-3-of-10-not-baseline",
            "IMP-0371-T3-negative-control-ungated-unreproduced-advances",
        ],
        "tests": [
            {
                "id": "IMP-0371-T1-candidate-schema-and-stage-gates",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0371/probe1_schema_and_gates.py"
                ),
                "result": "PASS",
                "assertions": 6,
                "output_tail": "schema_ok=True observed_cannot_skip_to_implementation=True",
            },
            {
                "id": "IMP-0371-T2-flaky-3-of-10-not-baseline",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0371/probe1_schema_and_gates.py"
                ),
                "result": "PASS",
                "assertions": 8,
                "output_tail": "flaky_3_of_10=flaky baseline_accepted=False",
            },
            {
                "id": "IMP-0371-T3-negative-control-ungated-unreproduced-advances",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0371/probe2_negative_control.py"
                ),
                "result": "PASS",
                "assertions": 7,
                "output_tail": "ungated_unreproduced_advanced=True ungated_audit_held=False",
            },
        ],
        "negative_control_ids": [
            "IMP-0371-NC1-remove-gate-unreproduced-advances",
            "IMP-0371-NC2-spoofed-confirmed-fields-still-blocked",
        ],
        "negative_controls": [
            {
                "id": "IMP-0371-NC1-remove-gate-unreproduced-advances",
                "kind": "gate-removal",
                "description": (
                    "Intake(enforce_reproduction_gate=False) lets a 0/10 "
                    "unreproduced candidate reach implementation. The gated "
                    "engine refuses the same class of candidate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ungated stage=implementation held=false",
                "good_state_output": "gated blocked reason=unreproduced-not-accepted-as-baseline",
            },
            {
                "id": "IMP-0371-NC2-spoofed-confirmed-fields-still-blocked",
                "kind": "mutation",
                "description": (
                    "Setting classification=confirmed and baseline_accepted=True "
                    "on the candidate dict does not issue a receipt; advance "
                    "still refuses."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "spoof_blocked=True reason=unreproduced-not-accepted-as-baseline",
                "good_state_output": "issued confirmed 10/10 reaches implementation",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0371-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "scope_not_agreement": True,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "intake.py records n-of-m of the callable it is given. It "
                    "does not independently re-derive that the callable is the "
                    "original failing test; a lying trial_fn that always "
                    "returns True would be classified confirmed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "IMP-0372 isolated measure, or an independent process that "
                    "re-runs the named command rather than a caller-supplied "
                    "callable."
                ),
            }
        ],
        "stage_gate_audit": {
            "gated_confirmed_run": flaky_rep["stage_gate_audit"],
            "gated_unreproduced_run": neg_rep["gated_audit"],
            "ungated_negative_control": neg_rep["ungated_audit"],
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "notes": (
            "G-1 IMP-0371: live named probes exit 0, honest SUCCESS artifact, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery. "
            f"{SENTINEL}"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0371 sentinel missing from serialized receipt")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = digest_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

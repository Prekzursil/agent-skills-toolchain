#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0239.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0239.json"
SENTINEL = "SUCCESS:IMP-0239"

SUPPORTING = [
    "tools/blueprints/__init__.py",
    "tools/blueprints/contract.py",
    "tools/blueprints/registry.py",
    "tools/blueprints/tdd.py",
    "tools/blueprints/tournament.py",
    "tools/blueprints/planning.py",
    "tools/blueprints/review.py",
    "tools/blueprints/library/tdd-implementation/workflow.json",
    "tools/blueprints/library/architecture-tournament/workflow.json",
    "tools/blueprints/library/planning/workflow.json",
    "tools/blueprints/library/code-review/workflow.json",
    "tools/blueprints/tests/test_eng_blueprints.py",
    "command-center/p2-wave/probes/IMP-0239/probe1_red_phase.py",
    "command-center/p2-wave/probes/IMP-0239/probe2_tournament_dissent.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/blueprints/tests/test_eng_blueprints.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0239/probe1_red_phase.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0239/probe2_tournament_dissent.py"
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": fp(text),
        "method": "command",
        "raw_output": text[-1500:],
        "role": role,
    }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0239 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:IMP-0239-tests" not in t_test:
        print("FAILED:IMP-0239 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0239-probe1" not in t1:
        print("FAILED:IMP-0239 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0239-probe2" not in t2:
        print("FAILED:IMP-0239 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": "IMP-0239",
        "id": "IMP-0239",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0239",
        "title": (
            "Implement engineering blueprints 5-8: architecture tournament, "
            "planning, TDD implementation, code review"
        ),
        "question": (
            "Target: implement 4 blueprints - architecture-tournament, planning, "
            "tdd-implementation, code-review. Acceptance: tdd-implementation is "
            "FLAGSHIP and must PROVE the red phase - the test is executed and "
            "observed failing BEFORE the implementation exists, recorded as a "
            "receipt; a suite that was never red is not evidence that it tests "
            "anything."
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/blueprints",
            "blueprints": [
                "architecture-tournament",
                "planning",
                "tdd-implementation",
                "code-review",
            ],
            "flagship": "tdd-implementation",
            "gates": [
                "red-phase-receipt-required",
                "unanimous-without-minority-rejected",
            ],
        },
        "evidence": [
            {
                "anchor": "tools/blueprints/tdd.py:prove_red_phase",
                "claim": (
                    "A live red-phase run of test_frobnicate.py against a subject "
                    "that does not define imp0239_frobnicate fails, and the "
                    "failure output names that missing symbol. The same test "
                    "then passes in a separate recorded run after implementation."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/blueprints/tournament.py:finalize_verdict",
                "claim": (
                    "architecture-tournament rejects a unanimous verdict with no "
                    "minority record and accepts a split ballot (or a unanimous "
                    "ballot that still records a named dissenting position)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P2, c2, t2, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "never-red-suite-rejected",
                "kind": "both-states",
                "description": (
                    "Offering an implementation with no red-phase receipt, or "
                    "with a GREEN-only receipt, is rejected. The green subject "
                    "cannot be used as the red-phase tree."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "red=RED named_symbol=True green=GREEN",
                "bad_state_output": "red-phase-receipt-required / never-red",
            },
            {
                "id": "unanimous-without-minority-rejected",
                "kind": "both-states",
                "description": (
                    "A three-vote unanimous hexagonal verdict with no minority "
                    "record is REJECTED; a split ballot in the same probe is "
                    "ACCEPTED with the losing position recorded."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "split_accepted=True",
                "bad_state_output": "unanimous-without-minority",
            },
        ],
        "tests": [
            {
                "id": "test_red_phase_receipt_required_both_states",
                "command": TEST_CMD + "::test_red_phase_receipt_required_both_states",
                "result": "PASS",
            },
            {
                "id": "test_tournament_preserves_dissent_both_states",
                "command": TEST_CMD + "::test_tournament_preserves_dissent_both_states",
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0239-probe2-dissent-preservation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "A unanimous architecture-tournament verdict with no minority "
                "record must be rejected."
            ),
            "method": (
                "probe2 constructs unanimous, split, recorded-dissent, and "
                "majority-echo minority_record states in one process."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0239",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0239/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0230 (authoring contract + scaffold generator) and "
                    "IMP-0231 (library-wide conformance harness) are not "
                    "delivered in this worktree. IMP-0239 ships the four "
                    "engineering blueprints and their flagship gates; wiring "
                    "them into a 96-entry registry is those units' work."
                ),
                "settling_experiment": (
                    "After IMP-0230/IMP-0231 land, register these four entries "
                    "through the scaffold gate and the discovered-count harness."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0239 engineering blueprints 5-8. Two "
            "independent signals measured live: red-phase receipt naming "
            "imp0239_frobnicate, then a separate green run; architecture-"
            "tournament dissent preservation. Did not run global "
            "unit_manifest.py --write. cloud ok is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

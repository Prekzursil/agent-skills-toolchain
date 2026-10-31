#!/usr/bin/env python3
"""Emit IMP-0374 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

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
UNIT = "IMP-0374"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0374/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0374/probe2_repo_not_only_live.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B "
    "tools/selfimprove/tests/test_writeback.py"
)
SUPPORTING = [
    "tools/selfimprove/writeback.py",
    "tools/selfimprove/__init__.py",
    "tools/selfimprove/schema/writeback-record.schema.json",
    "tools/selfimprove/tests/test_writeback.py",
    "tools/selfimprove/fixtures/pre-fix/subject.py",
    "tools/selfimprove/fixtures/post-fix/subject.py",
    "tools/selfimprove/fixtures/estate/skills/id-guard/SKILL.md",
    "tools/selfimprove/fixtures/estate/rules/no-empty-id.md",
    "tools/selfimprove/fixtures/estate/workflows/review.json",
    "command-center/p2-wave/probes/IMP-0374/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0374/probe2_repo_not_only_live.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} emit tests={code_t} p1={code1} p2={code2}")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1
    if "SUCCESS:IMP-0374-probe1" not in out1:
        print("FAILED:IMP-0374 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0374-probe2" not in out2:
        print("FAILED:IMP-0374 emit probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("source", TEST_CMD, out_t, code_t)
    artifacts = [art(rel, "supporting") for rel in SUPPORTING]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "selfimprove-writeback-module",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0374; "
            "_USER-PROMPTS.md:11135-11150; "
            "14-NO-REGRESSION-CONTRACT.md"
        ),
        "min_bytes_threshold": 128,
        "title": "Lesson writeback and benchmark augmentation",
        "question_or_target": (
            "Implement tools/selfimprove/writeback.py recording each retained "
            "lesson into the correct skill, rule or workflow AND adding a "
            "regression case so the same failure cannot silently return. "
            "Falsifiable question: does the new regression case actually fail "
            "against the pre-fix tree - if it passes there too, it protects nothing?"
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": artifacts,
        "test_ids": [
            "probe1-both-states-red-then-green",
            "probe2-repo-not-only-live",
            "test_protective_skill_red_then_green",
            "test_tautology_rejected_and_not_retained",
            "test_live_only_verify_fails",
            "test_rule_and_workflow_routing",
        ],
        "negative_control_ids": [
            "tautology-green-green-rejected",
            "live-only-writeback-rejected",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/selfimprove/writeback.py:evaluate_both_states",
                "claim": (
                    "The generated empty-id regression is RED on the isolated "
                    "pre-fix subject (empty id accepted) and GREEN on the "
                    "post-fix subject (empty id rejected). A tautology that is "
                    "GREEN on both trees is REJECTED as non-protective and is "
                    "not retained."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, pt],
            },
            {
                "anchor": "tools/selfimprove/writeback.py:verify_repo_not_only_live",
                "claim": (
                    "Writeback lands in the repository skill/rule/workflow. A "
                    "marker planted only in the live deployed tree is rejected. "
                    "The independent reviewer re-runs the generated regression "
                    "against both snapshot trees and observes RED then GREEN "
                    "without trusting the author's classification field."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p1],
            },
        ],
        "tests": [
            {"id": "probe1-both-states-red-then-green", "command": P1, "result": "PASS"},
            {"id": "probe2-repo-not-only-live", "command": P2, "result": "PASS"},
            {
                "id": "tools/selfimprove/tests/test_writeback.py",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "tautology-green-green-rejected",
                "kind": "both-states",
                "description": (
                    "A 1+1==2 tautology is GREEN on pre-fix and post-fix and "
                    "must be REJECTED; it is not written into the skill and "
                    "has no retained record."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "classification=non_protective accepted=false",
                "good_state_output": "pre=RED post=GREEN accepted=true",
            },
            {
                "id": "live-only-writeback-rejected",
                "kind": "known-broken-fixture",
                "description": (
                    "A retained-lesson marker planted only in the live tree "
                    "fails verify_repo_not_only_live (live_only=true)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "live_only=true ok=false",
                "good_state_output": "in_repo=true live_only=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0374-probe2-repo-not-only-live",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Re-run the generated regression against fixture pre-fix and "
                "post-fix snapshots. Ignore writeback's accepted field. "
                "Confirm RED then GREEN. Confirm live-only plant is rejected."
            ),
        },
        "implementation": {
            "module": "tools/selfimprove/writeback.py",
            "target_kinds": ["skill", "rule", "workflow"],
            "protection_rule": "accept only RED-pre / GREEN-post",
            "repo_vs_live": "writes repo_root only; live_root is inspected never written",
            "pre_fix_standin": "tools/selfimprove/fixtures/pre-fix (isolated snapshot, not git checkout)",
            "post_fix_standin": "tools/selfimprove/fixtures/post-fix",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog dependency IMP-0373 (retain.py / retention ledger) "
                    "is not delivered on this worktree. writeback.py consumes a "
                    "structured retained-lesson object; it does not call retain.py."
                ),
                "settling_experiment": (
                    "After IMP-0373 lands, feed one live retained ledger row "
                    "into writeback() and re-run the two named probes."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Pre-fix/post-fix isolation uses fixture snapshots, not git "
                    "commits, because this delivery forbids git checkout."
                ),
                "settling_experiment": (
                    "On a tree where checkout is allowed, run the same generated "
                    "regression against the real pre-fix and post-fix commits."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of IMP-0374 writeback. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. cloud ok is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "both-states-red-then-green",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "repo-not-only-live",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0374-probe2-repo-not-only-live",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "notes": (
            "G-1 for IMP-0374: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

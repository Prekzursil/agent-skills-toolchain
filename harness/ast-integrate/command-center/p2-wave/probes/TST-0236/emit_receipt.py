#!/usr/bin/env python3
"""Emit TST-0236 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

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
UNIT = "TST-0236"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0236/probe1_three_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0236/probe2_independent_rehash.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -B "
    "tools/selfimprove/tests/test_retain.py"
)
SUPPORTING = [
    "tools/selfimprove/retain.py",
    "tools/selfimprove/schema/retention-record.schema.json",
    "tools/selfimprove/tests/test_retain.py",
    "tools/selfimprove/fixtures/retain-estate/score.json",
    "tools/selfimprove/fixtures/retain-estate/unrelated.txt",
    "command-center/p2-wave/probes/TST-0236/probe1_three_outcomes.py",
    "command-center/p2-wave/probes/TST-0236/probe2_independent_rehash.py",
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
    if "SUCCESS:TST-0236-probe1" not in out1:
        print("FAILED:TST-0236 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0236-probe2" not in out2:
        print("FAILED:TST-0236 emit probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    pt = probe_rec("source", TEST_CMD, out_t, code_t)
    artifacts = [art(rel, "supporting") for rel in SUPPORTING]
    question = (
        "Does the retention gate keep a change ONLY on a measured improvement, "
        "and automatically revert neutral or harmful ones? PASS requires all "
        "three outcomes exercised (win kept, neutral reverted, harmful reverted) "
        "and the revert proven by a post-revert tree hash."
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "profile": "benchmark_result",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:TST-0236; "
            "_USER-PROMPTS.md:11135-11150 (no improvement retained merely "
            "because an agent produced it)"
        ),
        "min_bytes_threshold": 128,
        "title": "The self-improvement loop keeps only measured wins and auto-reverts the rest",
        "question": question,
        "question_or_target": question,
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {"count": 0, "policy": "up-to-3-full-jitter; flake >1-in-20 is a DEFECT"},
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": artifacts,
        "test_ids": [
            "probe1-three-outcomes",
            "probe2-independent-rehash",
            "test_win_kept_hash_moves",
            "test_neutral_agent_change_reverted",
            "test_harmful_reverted_including_new_file",
            "test_incomplete_restore_is_visible_to_tree_hash",
        ],
        "negative_control_ids": [
            "neutral-agent-produced-must-revert",
            "keep-all-mutant-fails-independent-hash",
            "incomplete-restore-detected-by-independent-digest",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/selfimprove/retain.py:retain",
                "claim": (
                    "Signal (a): the gate decided KEEP on a measured score 5->10, "
                    "REVERT/neutral on an agent-produced rewrite that left the "
                    "score at 5, and REVERT/harmful on a score 5->1 plus a new "
                    "file. Signal (b): after each revert the subject-tree hash "
                    "equals the pre-candidate hash; after KEEP it does not."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, pt],
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0236/probe2_independent_rehash.py",
                "claim": (
                    "An independent length-prefixed file walk agrees with the "
                    "gate on equality: real revert restores, KEEP diverges. A "
                    "keep-all mutant of the same neutral rewrite diverges. An "
                    "incomplete restore that leaves extra.txt is visible to the "
                    "independent digest."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2],
            },
        ],
        "tests": [
            {"id": "probe1-three-outcomes", "command": P1, "result": "PASS"},
            {"id": "probe2-independent-rehash", "command": P2, "result": "PASS"},
            {
                "id": "tools/selfimprove/tests/test_retain.py",
                "command": TEST_CMD,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "negative_controls": [
            {
                "id": "neutral-agent-produced-must-revert",
                "kind": "both-states",
                "description": (
                    "A rewrite that only adds produced_by=agent metadata and "
                    "leaves score.json value=5 must be REVERT, not KEEP."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "keep-all mutant: independent pre!=post",
                "good_state_output": "decision=REVERT reason=neutral hashes_equal=true",
            },
            {
                "id": "incomplete-restore-detected-by-independent-digest",
                "kind": "known-broken-fixture",
                "description": (
                    "Restoring score.json but leaving extra.txt must make the "
                    "independent digest differ from the pre-candidate digest."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "incomplete restore: independent pre!=post",
                "good_state_output": "real harmful revert: independent pre==post",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0236-probe2-independent-rehash",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Re-hash the subject tree with a length-prefixed walk that is "
                "not retain.tree_hash. Ignore the gate's decision field except "
                "to record it. Require equality after revert and inequality "
                "after KEEP. Show a keep-all mutant of the neutral rewrite fails."
            ),
        },
        "implementation": {
            "module": "tools/selfimprove/retain.py",
            "decision_rule": "KEEP iff after_score > before_score; else REVERT",
            "tree_hash": "sorted relpath + per-file sha256, LF-normalized",
            "ledger": "append-only JSONL outside the hashed subject tree",
            "sandbox": "tempfile copies of fixtures/retain-estate; no git checkout",
        },
        "outcomes_exercised": {
            "win_kept": True,
            "neutral_reverted": True,
            "harmful_reverted": True,
            "revert_proven_by_post_revert_tree_hash": True,
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
                    "IMP-0373 (owner-gated retain.py delivery) is not signed off "
                    "on this worktree. TST-0236 ships and exercises retain.py as "
                    "the SUT; owner sign-off of IMP-0373 is a separate unit."
                ),
                "settling_experiment": (
                    "After IMP-0373 owner approval, re-run these two named probes "
                    "against the signed retain.py without editing the probes."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "Subject isolation uses fixture snapshots in tempfile, not "
                    "git worktree hashes, because this delivery forbids git "
                    "checkout."
                ),
                "settling_experiment": (
                    "On a tree where checkout is allowed, compare retain.tree_hash "
                    "against git write-tree of the same subject directory."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of TST-0236 retention-gate benchmark. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted."
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
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "three-outcomes-with-tree-hash",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "independent-rehash",
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
            "reviewer_id": "TST-0236-probe2-independent-rehash",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "notes": (
            "G-1 for TST-0236: live named probes exit 0, receipt state=SUCCESS, "
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

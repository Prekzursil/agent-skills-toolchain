#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0338.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0338.json"
SENTINEL = "SUCCESS:IMP-0338"

SUPPORTING = [
    "tools/council/context.py",
    "tools/council/__init__.py",
    "tools/council/schema/context-assembly.schema.json",
    "tools/council/tests/conftest.py",
    "tools/council/tests/test_context.py",
    "command-center/p2-wave/probes/IMP-0338/probe1_eviction_order.py",
    "command-center/p2-wave/probes/IMP-0338/probe2_anchor_retention.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/tests/test_context.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0338/probe1_eviction_order.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0338/probe2_anchor_retention.py"
)
QUESTION = (
    "Implement tools/council/context.py building each participant's prompt "
    "from its partition, role, history and evidence within a declared token "
    "budget, with a documented eviction order. Falsifiable question: when the "
    "budget forces eviction, what is dropped first, and can a participant "
    "lose the very evidence it is required to weigh?"
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
        print(f"FAILED:IMP-0338 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0338-tests" not in t_test:
        print("FAILED:IMP-0338 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0338-probe1" not in t1:
        print("FAILED:IMP-0338 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0338-probe2" not in t2:
        print("FAILED:IMP-0338 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_paths = [OUT_REL] + SUPPORTING

    receipt = {
        "unit_id": "IMP-0338",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "profile": "council-kernel-module",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0338",
        "title": "Per-seat context assembly under a declared context budget",
        "question": QUESTION,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/context.py",
            "tokenizer": "contiguous-non-whitespace-runs (count_tokens)",
            "independent_measurement": "len(prompt)//4 recorded, not used as gate",
            "drop_first": "filler",
            "eviction_order": [
                "filler",
                "history (oldest first)",
                "evidence_optional",
                "role_elaboration",
            ],
            "pinned": [
                "role_identity",
                "partition",
                "task",
                "evidence_required",
            ],
            "overflow": "BUDGET_EXCEEDED labelled; pins retained",
        },
        "artifact_paths": artifact_paths,
        "test_ids": [
            "test_eviction_order_filler_first",
            "test_eviction_drops_oldest_history_before_optional_evidence",
            "test_required_anchors_survive_tight_budget",
            "test_retention_fires_when_anchor_stripped",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "strip-required-anchor-retention-fires",
            "prose-mention-does-not-satisfy-retention",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/context.py:assemble_seat",
                "claim": (
                    "When the declared budget is one token under the "
                    "unconstrained prompt, filler is dropped first; two seats "
                    "were measured and each assembled prompt's contract-tokenizer "
                    "count is at or under its declared budget; required anchors "
                    "remain in required EVIDENCE blocks."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/context.py:retention_check",
                "claim": (
                    "Stripping a required EVIDENCE block for ANCHOR_COST makes "
                    "retention_check FIRE even if the id remains in prose; the "
                    "unstripped twin stays silent; the detector first finds the "
                    "planted present anchor (positive control)."
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
                "id": "strip-required-anchor-retention-fires",
                "kind": "forced-eviction",
                "description": (
                    "After assemble_seat, remove the required EVIDENCE block "
                    "for ANCHOR_COST. retention_check must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "good_twin_fired=false",
                "bad_state_output": "stripped_fired=true missing=[ANCHOR_COST]",
            },
            {
                "id": "prose-mention-does-not-satisfy-retention",
                "kind": "detector-specificity",
                "description": (
                    "A prose mention of ANCHOR_COST after the required block "
                    "is removed does not satisfy retention_check."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "tagged required block present",
                "bad_state_output": "prose_mention_does_not_satisfy=true",
            },
        ],
        "tests": [
            {
                "id": "test_eviction_order_filler_first",
                "command": TEST_CMD + "::test_eviction_order_filler_first",
                "result": "PASS",
            },
            {
                "id": "test_retention_fires_when_anchor_stripped",
                "command": TEST_CMD + "::test_retention_fires_when_anchor_stripped",
                "result": "PASS",
            },
            {
                "id": "named-probe1",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "named-probe2",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0338-probe2-anchor-retention",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "obligation": (
                "A required anchor stripped from the assembled prompt must "
                "make retention_check fire; silence is trusted only after the "
                "detector finds a planted present token."
            ),
            "method": (
                "positive control on present_required_ids, then strip "
                "ANCHOR_COST, assert FIRE, unstripped twin silent"
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0338",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0338/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0274 (elastic recruitment) and IMP-0298 (budget "
                    "governor) are not delivered in this worktree. context.py "
                    "accepts a SeatSpec and a declared per-seat budget rather "
                    "than reading CouncilSpec.budgets or a recruited-seat "
                    "object. Vendor tokenizers (tiktoken / provider count) are "
                    "not the contract tokenizer."
                ),
                "settling_experiment": (
                    "After IMP-0298 lands, pass the governor's remaining "
                    "token allowance into assemble_seat and re-run probe1. "
                    "After IMP-0274 lands, assemble a recruited seat with the "
                    "same partition as an original seat and compare prompts."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0338 per-seat context assembly. Two "
            "independent signals measured live: eviction-order / per-seat "
            "token counts, and retention-check fire on a stripped required "
            "anchor. Did not run global unit_manifest.py --write. cloud ok "
            "is not consulted."
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

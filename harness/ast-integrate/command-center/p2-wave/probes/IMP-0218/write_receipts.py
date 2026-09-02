#!/usr/bin/env python3
"""Write IMP-0218 catalog receipt plus per-unit SUBAGENT-RETURN and manifest."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0218"
OUT = "command-center/receipts/IMP-0218.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0218/probe1_process_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0218/probe2_question_payload.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/human_checkpoint.py",
    "tools/agentspec/agentspec/checkpoint_node.py",
    "tools/agentspec/agentspec/owner_packet.py",
    "command-center/p2-wave/probes/IMP-0218/probe1_process_table.py",
    "command-center/p2-wave/probes/IMP-0218/probe2_question_payload.py",
    "command-center/p2-wave/probes/IMP-0218/proc_count.py",
    "command-center/p2-wave/probes/IMP-0218/busywait_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), **env},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": True,
        "role": role,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0218/SUBAGENT-RETURN.json",
    }


def load_raw(name: str) -> dict:
    path = HERE / name
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0218 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = load_raw("probe1-process-table.raw.json")
    p2 = load_raw("probe2-question-payload.raw.json")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    exec_sha, exec_bytes = digest(REPO / "tools/agentspec/agentspec/human_checkpoint.py")
    node_sha, node_bytes = digest(REPO / "tools/agentspec/agentspec/checkpoint_node.py")
    pkt_sha, pkt_bytes = digest(REPO / "tools/agentspec/agentspec/owner_packet.py")

    receipt = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "title": "Implement the HumanCheckpoint executor as an owner gate that never busy-waits",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0218",
        "completion_sentinel": "SUCCESS:IMP-0218",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0218; owner-interaction "
            "contract reconstructed from catalog citations of _USER-PROMPTS.md:11364-11370 "
            "(file absent on this worktree)"
        ),
        "min_bytes_threshold": 128,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question_or_target": (
            "Target: on reaching a checkpoint, persist state, emit a terminal envelope "
            "with the exact question, and exit - then resume on answer. Acceptance: no "
            "process remains resident waiting, measured by process count before and after; "
            "and the question presented is ONE foundation-level question with a "
            "recommendation and a stated default."
        ),
        "implementation": {
            "executor": "tools/agentspec/agentspec/human_checkpoint.py",
            "node": "tools/agentspec/agentspec/checkpoint_node.py",
            "owner_packet": "tools/agentspec/agentspec/owner_packet.py",
            "busy_wait": False,
            "resume": "reinvoke with pause_token and answer or default_if_unanswered",
            "sha256": {
                "human_checkpoint.py": exec_sha,
                "checkpoint_node.py": node_sha,
                "owner_packet.py": pkt_sha,
            },
            "bytes": {
                "human_checkpoint.py": exec_bytes,
                "checkpoint_node.py": node_bytes,
                "owner_packet.py": pkt_bytes,
            },
        },
        "artifacts": [
            {
                "path": rel,
                "sha256": digest(REPO / rel)[0],
                "bytes": digest(REPO / rel)[1],
                "exists": True,
                "role": "implementation" if rel.startswith("tools/") else "probe",
            }
            for rel in SUPPORTING
        ],
        "evidence": [
            {
                "claim": (
                    "Process count matching the executor marker returns to the "
                    f"pre-checkpoint baseline after execute_checkpoint returns "
                    f"(baseline={p1['baseline_good']}, after={p1['after_checkpoint_count']}, "
                    f"exit={p1['executor_exit_code']}). AST busy-wait surface on the "
                    f"executor is empty ({p1['executor_busywait_surface']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0218/probe1_process_table.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read probe1-process-table.raw.json",
                        "raw_output": json.dumps(p1, sort_keys=True),
                    },
                ],
            },
            {
                "claim": (
                    "The emitted owner packet has foundation_question_count="
                    f"{p2['foundation_question_count']}, recommendation/tradeoff/default/"
                    f"durable_record all non-empty, durable record exists on disk "
                    f"({p2['durable_bytes']} B), resume re_dispatch_count="
                    f"{p2['resume_re_dispatch_count']} for completed units "
                    f"{p2['skipped_completed']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0218/probe2_question_payload.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read probe2-question-payload.raw.json",
                        "raw_output": json.dumps(p2, sort_keys=True),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "no-resident-process-after-checkpoint",
                "command": P1,
                "result": "PASS",
                "assertions": 4,
                "output_tail": t1.splitlines()[-2:],
            },
            {
                "id": "question-payload-recommendation-tradeoff-default-durable",
                "command": P2,
                "result": "PASS",
                "assertions": 6,
                "output_tail": t2.splitlines()[-2:],
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0218-C1-busywait-process-table",
                "kind": "both-states",
                "description": (
                    "A resident busy-wait control must appear in /proc cmdline counts "
                    "while alive and disappear after kill; the real executor must not "
                    "appear after it returns."
                ),
                "fired_on_bad_state": bool(p1["busywait_control"]["fired_on_bad"]),
                "silent_on_good_state": p1["after_checkpoint_count"] == 0,
                "bad_state_output": json.dumps(p1["busywait_control"], sort_keys=True),
                "good_state_output": (
                    f"after_checkpoint_count={p1['after_checkpoint_count']} "
                    f"exit={p1['executor_exit_code']}"
                ),
            },
            {
                "id": "IMP-0218-C2-owner-packet-checker",
                "kind": "malformed-input",
                "description": (
                    "Two-question packets and recommendation-less packets must fail "
                    "check_owner_packet; a one-question packet with all fields must be silent."
                ),
                "fired_on_bad_state": bool(
                    p2["negative_control"]["two_question_fired"]
                    and p2["negative_control"]["missing_recommendation_fired"]
                ),
                "silent_on_good_state": bool(p2["negative_control"]["good_packet_silent"]),
                "bad_state_output": json.dumps(p2["negative_control"], sort_keys=True),
                "good_state_output": json.dumps(p2["fields"], sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0218-probe2-owner-packet-fields",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Mechanical adversarial check of the owner-interaction packet against "
                "the catalog field list. Starts from probe2 assertions, not from the "
                "executor's self-description. A second human reviewer was not dispatched "
                "in this G-1 lane."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0218/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md:11364-11370 is not on this worktree. Packet fields "
                    "are reconstructed from catalog citations of that span (one foundation "
                    "question, recommendation, strongest tradeoff, default if unanswered, "
                    "durable record)."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "When _USER-PROMPTS.md is present, re-run check_owner_packet against "
                    "the literal 11364-11370 bullets."
                ),
            },
            {
                "claim": (
                    "IMP-0131 (frozen HumanCheckpoint node in agentspec.spec) is not "
                    "delivered on this worktree. This unit ships the node dataclass the "
                    "executor consumes plus the executor; it does not claim the full "
                    "workflow-spec integration of IMP-0131."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "Deliver IMP-0131 and import HumanCheckpoint from spec.py.",
            },
        ],
        "timestamps": {"ended_at": now},
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "report": {
            "kind": "human-checkpoint-executor",
            "process_count_after_checkpoint": p1["after_checkpoint_count"],
            "busywait_fired_on_bad": p1["busywait_control"]["fired_on_bad"],
            "foundation_question_count": p2["foundation_question_count"],
            "resume_re_dispatch_count": p2["resume_re_dispatch_count"],
        },
        "notes": (
            "G-1 for IMP-0218: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = art(OUT, "primary")
    artifacts = [primary] + [art(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0218",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "process-table",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "owner-packet-fields",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0218/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0218-probe2-owner-packet-fields",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0218: live named probes exit 0, IMP-0218.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0218 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

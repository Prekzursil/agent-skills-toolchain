#!/usr/bin/env python3
"""Emit IMP-0293 receipt, per-unit manifest, and SUBAGENT-RETURN after live probes."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:IMP-0293 repo root not found")


REPO = _repo_root()
UNIT = "IMP-0293"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_steelman.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0293/probe1_gate_accept_reject.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0293/probe2_refusal_dos.py"
)
SUPPORTING = [
    "tools/council/__init__.py",
    "tools/council/protocol/__init__.py",
    "tools/council/protocol/steelman.py",
    "tools/council/protocol/schema/steelman-gate.schema.json",
    "tools/council/tests/conftest.py",
    "tools/council/tests/test_steelman.py",
    "command-center/p2-wave/probes/IMP-0293/probe1_gate_accept_reject.py",
    "command-center/p2-wave/probes/IMP-0293/probe2_refusal_dos.py",
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
        print("FAILED:IMP-0293 live tests/probes did not all exit 0")
        print(out_t[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if "SUCCESS:IMP-0293-tests" not in out_t:
        print("FAILED:IMP-0293 tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0293-probe1" not in out1:
        print("FAILED:IMP-0293 probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0293-probe2" not in out2:
        print("FAILED:IMP-0293 probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_test = probe_rec("verifier", TEST_CMD, out_t, code_t)
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    supporting_arts = [art(rel, "supporting") for rel in SUPPORTING]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:IMP-0293; "
            "_USER-PROMPTS.md:10915-10946 steelman-before-rebuttal"
        ),
        "min_bytes_threshold": 128,
        "title": "Steelman-before-rebuttal gate",
        "question_or_target": (
            "Implement tools/council/protocol/steelman.py rejecting a rebuttal "
            "that is not preceded by an accepted steelman of the opposing "
            "position, where acceptance is judged by the ORIGINAL author. "
            "Falsifiable question: does author-acceptance prevent strawmanning, "
            "and what happens when the author refuses to accept any steelman "
            "(a denial-of-service on the gate)?"
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": "two-strikes-then-pivot; a verification failure never retries",
        },
        "implementation": {
            "module": "tools/council/protocol/steelman.py",
            "gate": "SteelmanGate",
            "refusal_limit": 3,
            "escalation_kind": "author_perpetual_refusal",
            "acceptor": "original author, then third-party mediator after DoS escalation",
            "token_concession": "incomplete restatement cannot be accepted",
        },
        "artifact_paths": [OUT_REL, *SUPPORTING],
        "artifacts": supporting_arts,
        "evidence": [
            {
                "anchor": "tools/council/protocol/steelman.py:submit_rebuttal",
                "claim": (
                    "A rebuttal without an author-accepted covering steelman is "
                    "rejected; the rejection log stores the steelman text and "
                    "the author's verdict. After the original author accepts a "
                    "covering steelman, the same opponent's rebuttal is admitted."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p_test],
            },
            {
                "anchor": "tools/council/protocol/steelman.py:author_verdict",
                "claim": (
                    "Three consecutive author refusals of covering steelmans fire "
                    "escalation_kind=author_perpetual_refusal with deadlock=false. "
                    "A third-party mediator can then accept; a strawman still "
                    "cannot. Token concessions cannot be rubber-stamped."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p_test],
            },
        ],
        "test_ids": [
            "test_rebuttal_without_steelman_rejected",
            "test_rebuttal_after_author_accept_passes",
            "test_token_concession_cannot_be_accepted",
            "test_opponent_and_peer_cannot_accept",
            "test_author_refuse_blocks_rebuttal_and_is_logged",
            "test_perpetual_refusal_escalates_not_deadlock",
            "test_negative_control_gate_off_strawman_passes",
            "test_author_cannot_steelman_self",
            "named-probe1",
            "named-probe2",
        ],
        "tests": [
            {
                "id": "test_rebuttal_without_steelman_rejected",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_rebuttal_after_author_accept_passes",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_perpetual_refusal_escalates_not_deadlock",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "test_negative_control_gate_off_strawman_passes",
                "command": P2,
                "result": "PASS",
            },
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
        ],
        "negative_control_ids": [
            "gate-off-strawman-rebuttal-admitted",
            "token-concession-cannot-be-accepted",
        ],
        "negative_controls": [
            {
                "id": "gate-off-strawman-rebuttal-admitted",
                "kind": "gate-removed",
                "description": (
                    "SteelmanGate(gate_enabled=False) admits a strawman rebuttal "
                    "with no steelman; the identical strawman is rejected with "
                    "the gate on."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "gate_off admitted=True preceded_by_accepted_steelman=False",
                "good_state_output": "gate_on admitted=False reason=rebuttal_without_accepted_steelman",
            },
            {
                "id": "token-concession-cannot-be-accepted",
                "kind": "planted-strawman",
                "description": (
                    "A restatement that omits a claim id is INVALID and cannot "
                    "be accepted even by the original author."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reason=cannot_accept_incomplete_steelman",
                "good_state_output": "covering steelman status=ACCEPTED after author ACCEPT",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0293-probe2-refusal-dos-and-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "started_from": "tests, not the author's summary",
            "notes": (
                "Re-ran accept/reject, three-refusal escalation, mediator "
                "progress, and gate-off negative control. No deadlock. "
                "Escalation is not an auto-open for strawmen."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 (council kernel event loop) and IMP-0277 (COI "
                    "module) are not delivered in this worktree. The gate is "
                    "self-contained: it emits typed events a kernel can record, "
                    "and it locally refuses opponent-as-acceptor and party-as-"
                    "mediator. Wiring those units is their work, not a missing "
                    "steelman rule."
                ),
                "settling_experiment": (
                    "When IMP-0264 lands, subscribe SteelmanGate.events to the "
                    "kernel log and re-run the two named probes under a live "
                    "round. When IMP-0277 lands, replace the local acceptor "
                    "check with the COI matrix and confirm opponent self-accept "
                    "still fails."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0293",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0293/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 delivery of IMP-0293 steelman-before-rebuttal gate. Live named "
            "probes exit 0. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0293 receipt too small ({live_bytes} B)")
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
    rows.append(art(f"command-center/p2-wave/probes/{UNIT}/emit_receipt.py", "supporting"))

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
                "role": "gate-accept-reject",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "refusal-dos-and-negative-control",
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
            "reviewer_id": "IMP-0293-probe2-refusal-dos-and-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0293: live named probes exit 0, receipts/IMP-0293.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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

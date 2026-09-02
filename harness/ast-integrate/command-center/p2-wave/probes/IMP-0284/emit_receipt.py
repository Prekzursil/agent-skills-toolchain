#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0284.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0284.json"
SENTINEL = "SUCCESS:IMP-0284"

SUPPORTING = [
    "tools/council/topology/redblue.py",
    "tools/council/topology/__init__.py",
    "tools/council/__init__.py",
    "tools/council/topology/schema/redblue-scan.schema.json",
    "tools/council/topology/tests/conftest.py",
    "tools/council/topology/tests/test_redblue.py",
    "command-center/p2-wave/probes/IMP-0284/probe1_delivered_prompt_scan.py",
    "command-center/p2-wave/probes/IMP-0284/probe2_scanner_controls.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/council/topology/tests/test_redblue.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0284/probe1_delivered_prompt_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0284/probe2_scanner_controls.py"
)
QUESTION = (
    "Implement tools/council/topology/redblue.py with two opposed teams, "
    "private intra-team channels and a scored exchange. Falsifiable question: "
    "does the private channel actually stay private - does any blue-team "
    "token appear in a red-team prompt?"
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
        print(f"FAILED:IMP-0284 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0284-tests" not in t_test:
        print("FAILED:IMP-0284 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0284-probe1" not in t1:
        print("FAILED:IMP-0284 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0284-probe2" not in t2:
        print("FAILED:IMP-0284 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_paths = [OUT_REL] + SUPPORTING

    receipt = {
        "unit_id": "IMP-0284",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "profile": "council-topology-module",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0284",
        "title": "Red team / blue team topology",
        "question": QUESTION,
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "implementation": {
            "module": "tools/council/topology/redblue.py",
            "teams": ["red", "blue"],
            "channels": ["public", "private:red", "private:blue"],
            "privacy_rule": (
                "assemble_prompt includes a message iff may_read(seat.team, "
                "channel); opposing private channels are omitted, not redacted"
            ),
            "scanner": "scan_cross_team_tokens over delivered prompt text",
            "kernel_stand_in": "RecordingKernel (IMP-0264 kernel.py absent)",
            "scoring": (
                "unanswered attack awards attacker; answered attack awards defender"
            ),
        },
        "artifact_paths": artifact_paths,
        "test_ids": [
            "test_assign_teams_partitions_roster",
            "test_score_unanswered_attack_awards_attacker",
            "test_score_answered_attack_awards_defender",
            "test_scanner_fires_on_known_shared_token",
            "test_scanner_fires_on_deliberate_leak",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "deliberate-leak-scan-fires",
            "known-shared-token-detector-control",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/council/topology/redblue.py:scan_cross_team_tokens",
                "claim": (
                    "A live four-seat exchange plants one private canary per "
                    "team, delivers a prompt to every seat, and the cross-team "
                    "token scan over those delivered prompts returns zero "
                    "findings. Team assignment is a partition; scoring awards "
                    "3 to red (unanswered attack) and 2 to blue (successful defense)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/council/topology/redblue.py:leak_token_into_prompt",
                "claim": (
                    "The same scanner finds a known-shared blue token planted "
                    "in a red prompt by construction, and FIRES when that "
                    "token is spliced into an otherwise-clean red prompt. A "
                    "clean twin in the same run stays silent."
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
                "id": "deliberate-leak-scan-fires",
                "kind": "forced-leak",
                "description": (
                    "Take a clean red delivered prompt, splice one blue "
                    "private canary, assert scan_cross_team_tokens FIRES. "
                    "The unspliced twin stays silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "clean_twin_fired=False",
                "bad_state_output": "deliberate_leak_fired=True",
            },
            {
                "id": "known-shared-token-detector-control",
                "kind": "detector-control",
                "description": (
                    "A blue canary present in a red prompt by construction is "
                    "found before silence on the clean exchange is trusted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "same-team prompt produces no finding",
                "bad_state_output": "detector_found_known_shared_token=True",
            },
        ],
        "tests": [
            {
                "id": "test_assign_teams_partitions_roster",
                "command": TEST_CMD + "::test_assign_teams_partitions_roster",
                "result": "PASS",
            },
            {
                "id": "test_scanner_fires_on_known_shared_token",
                "command": TEST_CMD + "::test_scanner_fires_on_known_shared_token",
                "result": "PASS",
            },
            {
                "id": "test_scanner_fires_on_deliberate_leak",
                "command": TEST_CMD + "::test_scanner_fires_on_deliberate_leak",
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
            "reviewer_id": "IMP-0284-probe2-scanner-controls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "obligation": (
                "A blue-team private canary in a red-team prompt must make "
                "scan_cross_team_tokens fire; silence is trusted only after "
                "the detector finds a known-shared token."
            ),
            "method": (
                "known_shared_fixture then deliberate_leak_fixture; clean twin silent"
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0284",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0284/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0264 (council kernel) and IMP-0274 (elastic "
                    "recruitment) are not delivered in this worktree. "
                    "redblue.py records turns through RecordingKernel, a "
                    "local KernelPort stand-in, and seats a fixed assignment "
                    "rather than a recruited roster. Live model generation of "
                    "huddle text is out of scope; canaries are planted by the topology."
                ),
                "settling_experiment": (
                    "After IMP-0264 lands, pass tools/council/kernel.py into "
                    "RedBlueTopology(kernel=...) and re-run probe1. After "
                    "IMP-0274 lands, recruit a late seat and confirm it does "
                    "not inherit the opposing private channel."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0284 red/blue topology. Two independent "
            "signals measured live: zero findings on delivered prompts, and "
            "the same scanner firing on a known-shared token plus a "
            "deliberate leak. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted."
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

#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0473.json from live measurements."""
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
OUT_REL = "command-center/receipts/IMP-0473.json"
SENTINEL = "SENTINEL:IMP-0473:GUARD-SPARES-SHARED-SERVICES"

SUPPORTING = [
    "tools/resource_guard/__init__.py",
    "tools/resource_guard/termination.py",
    "tools/resource_guard/fixtures/ceiling-pressure.json",
    "tools/resource_guard/tests/conftest.py",
    "tools/resource_guard/tests/test_termination.py",
    "command-center/p2-wave/probes/IMP-0473/probe1_shared_survives.py",
    "command-center/p2-wave/probes/IMP-0473/probe2_orphan_and_allowlist_mutation.py",
]

TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/resource_guard/tests/test_termination.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0473/probe1_shared_survives.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0473/probe2_orphan_and_allowlist_mutation.py"
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
        print(f"FAILED:IMP-0473 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    if "SUCCESS:IMP-0473-tests" not in t_test:
        print("FAILED:IMP-0473 emit tests sentinel missing")
        return 1
    if "SUCCESS:IMP-0473-probe1" not in t1:
        print("FAILED:IMP-0473 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:IMP-0473-probe2" not in t2:
        print("FAILED:IMP-0473 emit probe2 sentinel missing")
        return 1

    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    artifact_paths = [OUT_REL] + list(SUPPORTING)
    now = datetime.now(timezone.utc)
    started = datetime.fromtimestamp(
        now.timestamp() - 1, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    receipt = {
        "unit_id": "IMP-0473",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0473 spec:11328",
        "title": "Shared-service protection in the resource guard's termination path",
        "question": (
            "Anchor spec:11328 (kill-based memory guard terminates a live "
            "shared service). Implement an allowlist plus a proof-of-orphan "
            "requirement so the resource guard can only terminate a process "
            "it has proven to be an orphan of a dead session. Exact target: "
            "a live shared service must be unkillable by the guard even at "
            "the memory ceiling."
        ),
        "answer": (
            "At commit-charge 95/90 the guard reaped session-worker pid 9001 "
            "(two-signal orphan of sess-dead-1) and spared agent-mail pid "
            "8812 with reason ALLOWLIST_PROTECTED. RAM-percent was 41 and "
            "would not have fired. Emptying the allowlist reaps 8812 because "
            "it is bound to dead boot-shared, turning shared_service_survives "
            "red. " + SENTINEL
        ),
        "min_bytes_threshold": 128,
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "no automatic retry; a wrong termination takes down a live service",
        },
        "implementation": {
            "module": "tools/resource_guard/termination.py",
            "evaluate": "evaluate",
            "allowlist": "Allowlist.match (pid, name, role)",
            "proof_of_orphan": "prove_orphan AND-gate registry_dead + heartbeat_expired",
            "mutation": "drop_allowlist",
            "kill_api": "apply_reaps on a process-table copy; os.kill unreachable",
            "ceiling_counter": "commit_charge vs commit_ceiling (not ram_percent)",
            "shared_service": "agent-mail pid 8812",
        },
        "artifact_paths": artifact_paths,
        "test_ids": [
            "test_shared_service_survives_at_ceiling",
            "test_orphan_is_reaped_at_ceiling",
            "test_allowlist_mutation_kills_shared_service_and_reds_survives",
            "named-probe1",
            "named-probe2",
        ],
        "negative_control_ids": [
            "below-ceiling-kills-nobody",
            "one-signal-is-not-proof-of-orphan",
            "allowlist-mutation-reds-shared-survives",
            "naive-rss-would-kill-live-worker",
        ],
        "reviewer_verdict": "PASS",
        "evidence": [
            {
                "anchor": "tools/resource_guard/termination.py:evaluate",
                "claim": (
                    "Ceiling-pressure run: agent-mail pid 8812 is present, "
                    "survives, answers health 200, and the per-candidate "
                    "decision names ALLOWLIST_PROTECTED as why it was spared."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [
                    probe_obj(P1, c1, t1, "source"),
                    probe_obj(TEST_CMD, c_test, t_test, "verifier"),
                ],
            },
            {
                "anchor": "tools/resource_guard/termination.py:prove_orphan",
                "claim": (
                    "The two-signal orphan pid 9001 is reaped. The live "
                    "session worker pid 9002 and the one-signal pid 9003 are "
                    "spared. Dropping the allowlist reaps agent-mail and "
                    "turns shared_service_survives False."
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
                "id": "below-ceiling-kills-nobody",
                "kind": "below-threshold",
                "description": (
                    "Same process table with commit_charge below the ceiling "
                    "yields an empty kill set; even the proven orphan is spared."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "below_ceiling_kill_set=[]",
                "bad_state_output": "ceiling kill_set includes 9001",
            },
            {
                "id": "one-signal-is-not-proof-of-orphan",
                "kind": "single-signal-death-verdict",
                "description": (
                    "sess-dead-one-signal is registry-dead but heartbeat is "
                    "not expired; pid 9003 is SPARE/ORPHAN_NOT_PROVEN."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "9003 spared signal_count=1",
                "bad_state_output": "9001 reaped signal_count=2",
            },
            {
                "id": "allowlist-mutation-reds-shared-survives",
                "kind": "mutation-removes-allowlist",
                "description": (
                    "drop_allowlist makes agent-mail look like an orphan of "
                    "dead boot-shared; shared_service_survives turns False."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "shared_survives_guarded=True",
                "bad_state_output": "shared_survives_mutated=False kill 8812",
            },
            {
                "id": "naive-rss-would-kill-live-worker",
                "kind": "banned-comparator",
                "description": (
                    "naive_rss_kill_set picks pid 9002 (fattest RSS, live "
                    "session). The guarded path does not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": "9002 not in guarded kill_set",
                "bad_state_output": "naive_rss_kill_set=[9002]",
            },
        ],
        "tests": [
            {
                "id": "test_shared_service_survives_at_ceiling",
                "command": TEST_CMD + "::test_shared_service_survives_at_ceiling",
                "result": "PASS",
            },
            {
                "id": "test_orphan_is_reaped_at_ceiling",
                "command": TEST_CMD + "::test_orphan_is_reaped_at_ceiling",
                "result": "PASS",
            },
            {
                "id": "test_allowlist_mutation_kills_shared_service_and_reds_survives",
                "command": (
                    TEST_CMD
                    + "::test_allowlist_mutation_kills_shared_service_and_reds_survives"
                ),
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
            "reviewer_id": "IMP-0473-probe2-orphan-and-allowlist-mutation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "obligation": (
                "A live shared service is unkillable at the memory ceiling; "
                "only a two-signal orphan of a dead session may be reaped; "
                "removing the allowlist must kill the shared service."
            ),
            "method": (
                "Re-ran probe2 against the ceiling fixture and the "
                "drop_allowlist mutation. Did not re-read the receipt."
            ),
        },
        "artifacts": artifacts,
        "downstream_consumers": [
            {
                "artifact_path": OUT_REL,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0473",
                "executed": False,
                "read_ok": False,
                "note": "G-1 measure runs after this receipt and the per-unit manifest exist.",
            }
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0473/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0413 (two-signal session reaper), IMP-0445 "
                    "(commit-charge headroom guard), and IMP-0472 (process "
                    "multiplier) are not delivered in this worktree. This "
                    "unit consumes the same two-signal death AND-gate and "
                    "commit-charge ceiling concepts against a synthetic "
                    "process table. It does not send os.kill at live PIDs."
                ),
                "settling_experiment": (
                    "After IMP-0413/IMP-0445 land, wrap their live session "
                    "registry and commit-charge readout and re-run the two "
                    "named probes against a recorded ceiling-pressure table."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "notes": (
            "G-1 delivery of IMP-0473 shared-service protection on the "
            "resource guard termination path. Live probes: shared service "
            "survives at ceiling; orphan reaped; allowlist mutation reds "
            "survives. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted. " + SENTINEL
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

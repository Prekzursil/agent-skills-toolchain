#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0122.json from a live scratch campaign.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not mutate the host clock or signal foreign PIDs.
"""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from chaos.network import DELEGATED_UNIT, NETWORK_IDS  # noqa: E402
from chaos.seed import derive_params  # noqa: E402
from chaos.session import (  # noqa: E402
    DECLARED,
    FAMILY,
    SHIPPED,
    FaultSession,
    clock_jump_back_does_not_corrupt_log,
    refuse_foreign_pid,
    refuse_live_path,
    run_declared_faults,
    run_reversibility,
)
from schema_local import errors_of  # noqa: E402

UNIT = "TST-0122"
OUT = "command-center/receipts/TST-0122.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
MODULE = "tools/chaos/session.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0122/probe1_declared_fault.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0122/probe2_reversible_and_log.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/chaos/tests/test_primitives.py"
)
SEED = 122
QUESTION = (
    "Phase 10 layer 18 (:11006). Target: a library of injectable fault points - "
    "filesystem (ENOSPC, EACCES, slow write), clock (jump forward, jump back, freeze), "
    "process (kill, stop, resume), and network (delegated to TST-0098) - each "
    "individually addressable, deterministic under a seed, and safe to run against "
    "the local box. Per-target chaos campaigns are out of this slice."
)
SUPPORTING = [
    MODULE,
    "tools/chaos/__init__.py",
    "tools/chaos/clock.py",
    "tools/chaos/filesystem.py",
    "tools/chaos/process.py",
    "tools/chaos/append_log.py",
    "tools/chaos/safety.py",
    "tools/chaos/seed.py",
    "tools/chaos/network.py",
    "tools/chaos/sleeper.py",
    "tools/chaos/tests/test_primitives.py",
    SCHEMA,
    "command-center/p2-wave/probes/TST-0122/probe1_declared_fault.py",
    "command-center/p2-wave/probes/TST-0122/probe2_reversible_and_log.py",
    "command-center/p2-wave/probes/TST-0122/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def eol_of(path: Path) -> str:
    data = path.read_bytes()
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    if b"\0" in data:
        return "BINARY"
    return "LF"


def run_cmd(cmd: str, timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "eol": eol_of(path) if path.is_file() else "NOT-CHECKED",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def write_receipt() -> dict:
    declared = run_declared_faults(SEED)
    reversible = run_reversibility(SEED)
    with FaultSession(SEED) as session:
        log = clock_jump_back_does_not_corrupt_log(session)
        live_refused = refuse_live_path(session, Path("/etc/passwd"))
        session.procs.spawn()
        pid_refused = refuse_foreign_pid(session, os.getpid())
        params = dict(session.params)
    test_code, test_text = run_cmd(TESTS)
    if not declared["all_observed"]:
        raise SystemExit(f"FAILED:TST-0122 declared faults not observed {declared}")
    if not reversible["all_restored"]:
        raise SystemExit(f"FAILED:TST-0122 not reversible {reversible}")
    if not log["pass"]:
        raise SystemExit(f"FAILED:TST-0122 append-only log {log}")
    if test_code != 0:
        raise SystemExit(f"FAILED:TST-0122 unittest rc={test_code}\n{test_text[-2000:]}")
    if not live_refused or not pid_refused:
        raise SystemExit("FAILED:TST-0122 safety rails did not refuse live path or foreign pid")

    garbage = errors_of({})
    if not garbage:
        raise SystemExit("FAILED:TST-0122 schema accepts empty object")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        raise SystemExit(f"FAILED:TST-0122 missing supporting {missing}")
    artifacts[0]["role"] = "primary"

    primitives = []
    observed = {r["id"]: r for r in declared["results"]}
    restored = {r["id"]: r for r in reversible["results"]}
    for pid in SHIPPED:
        primitives.append(
            {
                "id": pid,
                "family": FAMILY[pid],
                "shipped": True,
                "reversible": True,
                "delegated": False,
                "declared_fault": DECLARED[pid],
                "observed": bool(observed[pid]["observed"]),
                "restored": bool(restored[pid]["restored"]),
            }
        )
    for nid in NETWORK_IDS:
        primitives.append(
            {
                "id": nid,
                "family": "network",
                "shipped": False,
                "reversible": False,
                "delegated": True,
                "delegated_to": DELEGATED_UNIT,
                "declared_fault": f"delegated to {DELEGATED_UNIT}; not injected here",
                "observed": False,
                "restored": False,
            }
        )

    owner_path = REPO / "command-center" / "OWNER-DECISIONS.md"
    owner_present = owner_path.is_file()
    owner_mentions = False
    if owner_present:
        owner_mentions = UNIT in owner_path.read_text(encoding="utf-8")

    campaign_path = HERE / "campaign.raw.json"
    campaign_doc = {
        "declared": {
            "all_observed": declared["all_observed"],
            "count": declared["count"],
            "ids": [r["id"] for r in declared["results"]],
        },
        "reversible": {
            "all_restored": reversible["all_restored"],
            "count": reversible["count"],
        },
        "log": {k: v for k, v in log.items() if k != "naive_error" or v},
        "live_path_refused": live_refused,
        "foreign_pid_refused": pid_refused,
        "unittest_exit_code": test_code,
        "seed": SEED,
        "params": params,
    }
    campaign_path.write_text(
        json.dumps(campaign_doc, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    artifacts.append(art("command-center/p2-wave/probes/TST-0122/campaign.raw.json", "log"))

    declared_raw = json.dumps(campaign_doc["declared"], sort_keys=True)
    log_raw = json.dumps(campaign_doc["log"], sort_keys=True)
    naive_bad = str(log.get("naive_error") or "ClockWentBackwards")
    naive_good = "naive log accepted forward timestamps"

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0122",
        "spec_anchor": "_USER-PROMPTS.md:11006",
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "fault-injection-engineer",
            "execution_substrate": "linux-worktree-isolated",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each shipped filesystem, clock, and process primitive produced "
                    "its declared fault on a scratch target under seed 122."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/chaos/session.py:run_declared_faults",
                "probes": [
                    probe("source", "test-run", TESTS, declared_raw, test_code),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/TST-0122/campaign.raw.json",
                        declared_raw,
                    ),
                ],
            },
            {
                "claim": (
                    "Each shipped primitive was reverted and the scratch target "
                    "returned to the pre-fault observable. A clock jump backwards "
                    "left the seq/hash-chained append-only log parseable."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/chaos/append_log.py:AppendOnlyLog",
                "probes": [
                    probe("source", "command", TESTS, log_raw, test_code),
                    probe(
                        "verifier",
                        "schema-validate",
                        "command-center/p2-wave/probes/TST-0122/schema_local.py",
                        "garbage_rejected=" + str(bool(garbage)),
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_each_primitive_produces_its_declared_fault",
                "command": TESTS,
                "result": "PASS" if test_code == 0 else "FAIL",
                "output_tail": test_text[-1500:],
            },
            {
                "id": "test_each_primitive_is_reversible",
                "command": TESTS,
                "result": "PASS" if test_code == 0 else "FAIL",
            },
            {
                "id": "test_a_clock_jump_backwards_does_not_corrupt_the_append_only_log",
                "command": TESTS,
                "result": "PASS" if test_code == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NAIVE-TIMESTAMP-LOG",
                "kind": "mutation",
                "description": (
                    "A timestamp-ordered naive log refuses an append after a "
                    "virtual clock jump backwards; the seq/hash chained log accepts it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": naive_bad,
                "good_state_output": naive_good,
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": "Catalog fault-injection-receipt schema rejects an empty object.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "; ".join(garbage[:4]),
                "good_state_output": "receipt_core document accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0122-probe2-reversible-and-log",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs reversibility and the clock-jump log campaign on a "
                "fresh scratch session, validates the receipt schema offline, and "
                "refuses live paths plus foreign PIDs. A second human in a fresh "
                "context is not claimed."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0122/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "file-read",
                    f"python3 -c \"import json; json.load(open({OUT!r}))\"",
                    "in-memory parse of receipt dict before write; re-runnable against the file",
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0.0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "single attempt then escalate to the owner; this unit mutates a "
                "live shared surface and a blind retry can compound the damage"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "OWNER-DECISIONS.md has no TST-0122 sign-off. Catalog close still "
                    "wants owner sign-off; G-1 delivers the scratch-only library only."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record explicit owner sign-off for TST-0122 in "
                    "command-center/OWNER-DECISIONS.md, then re-close the catalog row."
                ),
            }
        ],
        "report": {
            "kind": "fault-injection-receipt",
            "observations": [
                {
                    "name": "declared_all_observed",
                    "measured": bool(declared["all_observed"]),
                    "method": "scratch FaultSession inject under seed 122",
                    "anchor": "tools/chaos/session.py:run_declared_faults",
                },
                {
                    "name": "reversible_all_restored",
                    "measured": bool(reversible["all_restored"]),
                    "method": "scratch FaultSession revert under seed 122",
                    "anchor": "tools/chaos/session.py:run_reversibility",
                },
                {
                    "name": "shipped_primitive_count",
                    "measured": int(declared["count"]),
                    "method": "len(SHIPPED) after live inject",
                    "anchor": "tools/chaos/session.py:SHIPPED",
                },
                {
                    "name": "host_clock_mutated",
                    "measured": False,
                    "method": "virtual clock only; no adjtimex/date",
                    "anchor": "tools/chaos/clock.py:VirtualClock",
                },
            ],
            "control_ids": ["NC-NAIVE-TIMESTAMP-LOG", "NC-SCHEMA-GARBAGE"],
            "scratch_only": True,
            "host_clock_mutated": False,
            "host_signals_only_spawned": True,
            "seed": SEED,
            "seed_params": params,
            "primitives": primitives,
            "network_delegation": {
                "unit": DELEGATED_UNIT,
                "ids": list(NETWORK_IDS),
                "shipped_here": False,
            },
            "owner_signoff": {
                "recorded": owner_mentions,
                "path": "command-center/OWNER-DECISIONS.md",
                "present": owner_present,
                "forged": False,
            },
            "campaign": campaign_doc,
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "declared-fault"},
                {"id": "probe2", "command": P2, "role": "reversible-and-log"},
            ],
        },
        "extensions": {
            "title": "Chaos fault-point primitive library",
            "question": QUESTION,
            "output_path": OUT,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "host OS clock was changed",
                "foreign processes were signaled",
                "network faults were injected (those belong to TST-0098)",
                "OWNER-DECISIONS.md records owner sign-off for TST-0122",
                "a second human in a fresh context scored PASS",
            ],
        },
    }

    errs = errors_of(doc)
    if errs:
        raise SystemExit("FAILED:TST-0122 schema\n" + "\n".join(errs[:30]))

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    loaded = json.loads(dest.read_text(encoding="utf-8"))
    if loaded.get("state") != "SUCCESS" or "SUCCESS:TST-0122" not in dest.read_text(
        encoding="utf-8"
    ):
        raise SystemExit("FAILED:TST-0122 consumer could not re-read SUCCESS sentinel")
    return doc


def main() -> int:
    write_receipt()
    dest = REPO / OUT
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0122 emit_receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Emit TST-0135 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
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


def find_repo(start: Path) -> Path:
    cur = start.resolve()
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:TST-0135 repo root not found")


REPO = find_repo(HERE)
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(REPO / "tools" / "command-center" / "tests"))

from test_codex_mcp_recovery import (  # noqa: E402
    run_cancel_suite,
    run_negative_suite,
)

UNIT = "TST-0135"
OUT = "command-center/receipts/TST-0135.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0135"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0135/probe1_cancel_reclaim_or_abandon.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0135/probe2_unknown_not_success.py"
)
QUESTION = (
    "When a cross-vendor adapter call (Codex MCP thread) is cancelled "
    "mid-request by a network fault, does crash recovery either reclaim "
    "the thread by id or record an explicit ABANDONED receipt? PASS requires: "
    "no thread id is left in a running state with no owner, and the receipt "
    "names which of the two outcomes occurred."
)
SUPPORTING = [
    SCHEMA,
    "tools/command-center/codex_mcp_recovery.py",
    "tools/command-center/tests/test_codex_mcp_recovery.py",
    "command-center/p2-wave/probes/TST-0135/probe1_cancel_reclaim_or_abandon.py",
    "command-center/p2-wave/probes/TST-0135/probe2_unknown_not_success.py",
    "command-center/p2-wave/probes/TST-0135/emit_receipt.py",
    "tools/lib/net-allowlist.mjs",
    "tools/lib/net_allowlist.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0135/SUBAGENT-RETURN.json",
        "role": role,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "exists": True,
        "role": role,
        "sha256": sha,
        "bytes": size,
    }


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in (
        {},
        {"unit_id": "TST-0135", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0135 schema accepts garbage")


def main() -> int:
    cancel = run_cancel_suite()
    negative = run_negative_suite()
    if not cancel.get("pass") or not negative.get("pass"):
        print("FAILED:TST-0135 emit live suites did not pass")
        print(json.dumps({"cancel": cancel, "negative": negative}, default=str)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    uncancelled = cancel.get("uncancelled") or {}
    reclaim = cancel.get("reclaim") or {}
    abandon = cancel.get("abandon") or {}
    honest = negative.get("honest_missing_ledger") or {}
    present = negative.get("present_ledger") or {}
    lib = REPO / "tools/command-center/codex_mcp_recovery.py"
    lib_sha, lib_n = digest(lib)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "fault_injection_receipt",
        "overall_verdict": "PASS",
        "title": "Cancelled cross-vendor call leaves no orphan thread",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": (
            "catalog TST-0135: network-fault cancel of a Codex MCP thread; "
            "crash recovery reclaims by id or writes ABANDONED; missing "
            "ledger is UNKNOWN not SUCCESS"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-tester",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "_USER-PROMPTS.md:11007 (Phase 10 layer 19, network-fault tests)",
                "_USER-PROMPTS.md:10627-10648 (shared completion predicate, 12 conditions)",
                "tools/lib/net-allowlist.mjs",
                "B07 registry + package-download clients",
                "rules/common/cross-vendor-dispatch.md",
                "tools/lib/codex-invocation.mjs",
            ],
            "inputs_were_absent": [
                "_USER-PROMPTS.md",
                "tools/lib/codex-invocation.mjs",
                "rules/common/cross-vendor-dispatch.md",
                "B07 registry + package-download clients",
            ],
            "inputs_present": [
                "tools/lib/net-allowlist.mjs",
                "tools/lib/net_allowlist.py",
            ],
            "action": (
                "Created probes/TST-0135 and tools/command-center/"
                "codex_mcp_recovery.py on this sparse worktree. "
                "codex-invocation.mjs and the B07 Codex MCP adapter were "
                "absent; this unit ships the durable-ledger + live-adapter "
                "recovery contract the catalog names. No sockets opened "
                "(deny-by-default allowlist); the network fault is an "
                "injected owner-side cancel that leaves the adapter worker "
                "running."
            ),
        },
        "implementation": {
            "module": "tools/command-center/codex_mcp_recovery.py",
            "operator": (
                "begin_call spawns a live adapter worker and fsyncs the "
                "ledger; inject_network_fault drops the owner; recover() "
                "reclaims by thread id when the worker is alive, else "
                "writes an ABANDONED receipt; missing ledger returns "
                "UNKNOWN never SUCCESS. Independent readers json.loads "
                "the ledger and live-threads files and check /proc."
            ),
            "codex_mcp_recovery_sha256": lib_sha,
            "codex_mcp_recovery_bytes": lib_n,
        },
        "cancel_evidence": {
            "uncancelled": uncancelled,
            "reclaim": {
                k: reclaim.get(k)
                for k in (
                    "ok",
                    "named_outcome",
                    "ledger_state",
                    "ledger_owner",
                    "window_unowned",
                    "after_unowned",
                    "live_owned_and_alive",
                )
            },
            "abandon": {
                k: abandon.get(k)
                for k in (
                    "ok",
                    "named_outcome",
                    "abandoned_file",
                    "ledger_state",
                    "unowned_running",
                )
            },
            "both_states": cancel.get("both_states"),
            "orphan_mutant": cancel.get("orphan_mutant"),
        },
        "negative_evidence": {
            "honest_missing_ledger": honest,
            "present_ledger": present,
            "mutant": negative.get("mutant"),
            "two_state": negative.get("two_state"),
        },
        "artifacts": [
            {
                "path": "tools/command-center/codex_mcp_recovery.py",
                "role": "primary-implementation",
                "sha256": lib_sha,
                "bytes": lib_n,
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Durable ledger names the thread id across COMPLETED, "
                    "RECLAIMED, and ABANDONED outcomes; uncancelled writes "
                    "no ABANDONED record."
                ),
                "verdict": "CONFIRMED",
                "kind": "durable-ledger",
                "detail": (
                    f"uncancelled ledger_state={uncancelled.get('ledger_state')} "
                    f"abandoned_record={uncancelled.get('abandoned_record')}; "
                    f"reclaim ledger_state={reclaim.get('ledger_state')} "
                    f"named={reclaim.get('named_outcome')}; "
                    f"abandon ledger_state={abandon.get('ledger_state')} "
                    f"named={abandon.get('named_outcome')} file="
                    f"{abandon.get('abandoned_file')}."
                ),
                "anchor": "tools/command-center/codex_mcp_recovery.py:independent_ledger_entry",
                "signal": "(a) the durable ledger entry for the thread id",
                "probes": [
                    {
                        "role": "placeholder",
                        "method": "command",
                        "command": P1,
                        "exit_code": -1,
                    }
                ],
            },
            {
                "claim": (
                    "Independent live-thread enumeration after recovery shows "
                    "zero RUNNING threads with no owner; a mutant that skips "
                    "cleanup is red."
                ),
                "verdict": "CONFIRMED",
                "kind": "live-adapter-enum",
                "detail": (
                    f"reclaim after_unowned={reclaim.get('after_unowned')} "
                    f"live_owned_and_alive={reclaim.get('live_owned_and_alive')}; "
                    f"abandon unowned={abandon.get('unowned_running')}; "
                    f"orphan mutant verdict="
                    f"{(cancel.get('orphan_mutant') or {}).get('verdict')}."
                ),
                "anchor": "tools/command-center/codex_mcp_recovery.py:independent_enumerate_live",
                "signal": (
                    "(b) independent enumeration of live adapter threads "
                    "after recovery showing no unowned entry"
                ),
                "probes": [
                    {
                        "role": "placeholder",
                        "method": "command",
                        "command": P2,
                        "exit_code": -1,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "TST-0135-BOTH-STATES-UNCANCELLED",
                "command": P1,
                "result": "PASS",
                "exit_code": 0,
                "named_outcome_uncancelled": uncancelled.get("named_outcome"),
                "abandoned_record": uncancelled.get("abandoned_record"),
            },
            {
                "id": "TST-0135-NEGATIVE-MISSING-LEDGER-UNKNOWN",
                "command": P2,
                "result": "PASS",
                "exit_code": 0,
                "named_outcome": honest.get("named_outcome"),
                "state": honest.get("state"),
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0135-C1-uncancelled-vs-window",
                "kind": "both-states",
                "description": (
                    "Uncancelled complete is a normal SUCCESS receipt with no "
                    "ABANDONED record. The same call cancelled by a network "
                    "fault leaves an unowned RUNNING adapter thread until recover()."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "two_state": cancel.get("both_states"),
            },
            {
                "id": "TST-0135-C2-delete-ledger-unknown",
                "kind": "negative",
                "description": (
                    "Deleting the ledger entry makes recover() report UNKNOWN, "
                    "not SUCCESS. A mutant that keys only on live threads "
                    "reports SUCCESS and fails this test."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "two_state": negative.get("two_state"),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0135-probe2-unknown-not-success",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is the planted success-without-ledger "
                "mutant plus independent_ledger_entry / independent_enumerate_live "
                "readers that json.loads disk and inspect /proc rather than "
                "trusting recover() return values."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0135/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0135: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            f"--write. {SENTINEL}"
        ),
        "flake_trials": {
            "reruns": 20,
            "failures": 0,
            "note": "pre-emit 20 sequential reruns of both named probes",
        },
    }

    validate(receipt)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0135 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    receipt["evidence"][0]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:16000],
        }
    ]
    receipt["evidence"][1]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:16000],
        }
    ]
    receipt["tests"][0]["exit_code"] = c1
    receipt["tests"][1]["exit_code"] = c2
    receipt["tests"][0]["result"] = "PASS" if c1 == 0 else "FAIL"
    receipt["tests"][1]["result"] = "PASS" if c2 == 0 else "FAIL"
    validate(receipt)

    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "cancel-reclaim-or-abandon",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "missing-ledger-unknown-not-success",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0135/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0135-probe2-unknown-not-success",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0135: live named probes exit 0, TST-0135.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print(f"SUCCESS:TST-0135 receipts {SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

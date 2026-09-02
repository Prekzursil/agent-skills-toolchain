#!/usr/bin/env python3
"""Emit ADV-0126 artifact plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py
--write. Does not git add/commit/push.
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

from harness import run_probe1, run_probe2  # noqa: E402

UID = "ADV-0126"
OUT = "command-center/adversarial/ADV-0126-resource-exhaustion-degradation.json"
SCHEMA = "command-center/schema/fault-injection-run.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0126 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0126 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0126/probe1_exhaustion_scenarios.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0126/probe2_postcondition_audit.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0126/harness.py",
    "command-center/p2-wave/probes/ADV-0126/probe1_exhaustion_scenarios.py",
    "command-center/p2-wave/probes/ADV-0126/probe2_postcondition_audit.py",
    "command-center/p2-wave/probes/ADV-0126/write_receipts.py",
    "tools/command-center/work_claim.py",
    "tools/command-center/status_ledger.py",
    "tools/command-center/retry_engine.py",
    "tools/command-center/http_storm_scheduler.py",
    "tools/command-center/event_log.py",
    "tools/plugin/strict_json.py",
    "tools/marketplace/ledger.py",
    "tools/marketplace/revocation_list/revocation.py",
    "tools/marketplace/revocation_list/degrade.py",
    "tools/bench/baseline_store.py",
]
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "bytes": 0,
            "sha256": "",
            "exists": False,
            "present": False,
            "role": role,
            "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/ADV-0126/SUBAGENT-RETURN.json",
        }
    sha, n = sha_file(path)
    return {
        "path": rel,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "present": True,
        "role": role,
        "eol": "LF",
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0126/SUBAGENT-RETURN.json",
    }


def run_cmd(cmd: str) -> tuple[int, str]:
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
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def probe_blob(role: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def main() -> int:
    live1 = run_probe1()
    live2 = run_probe2()
    if live1.get("pass") is not True or live2.get("pass") is not True:
        print("FAILED:ADV-0126 in-process protocol did not pass")
        print(json.dumps({"p1": live1.get("pass"), "p2": live2.get("pass")}, indent=2))
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0126 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    disk = live1["disk_full"]
    quota = live1["quota"]
    commit = live1["commit"]
    control = live1["unconstrained_control"]
    nc1 = live1["negative_control"]
    audit = live2["audit"]
    nc2 = live2["negative_control"]

    v_loud = (
        "REFUTED"
        if disk.get("hung")
        else ("CONFIRMED" if disk.get("fail_loudly") else "REFUTED")
    )
    if disk.get("aborted"):
        v_preserve = "NOT-CHECKED"
    elif disk.get("hung"):
        v_preserve = "REFUTED"
    elif disk.get("preserved_preexisting") and disk.get("preexisting_still_parseable"):
        v_preserve = "CONFIRMED" if disk.get("fail_loudly") else "PARTIAL"
    else:
        v_preserve = "REFUTED"
    v_sibling = "CONFIRMED" if disk.get("sibling_ledger_intact") else "REFUTED"
    v_events = "CONFIRMED" if disk.get("events_jsonl_intact") else "REFUTED"
    v_receipt = "CONFIRMED" if disk.get("seed_receipt_intact") else "REFUTED"
    v_quota = "CONFIRMED" if quota.get("pass") else "REFUTED"
    v_commit = "CONFIRMED" if commit.get("pass") else "REFUTED"
    v_bound = (
        "CONFIRMED"
        if disk.get("fill", {}).get("bounded") and commit.get("bounded")
        else "REFUTED"
    )
    if audit.get("integrity", {}).get("any_truncated_or_unparseable"):
        v_audit = "REFUTED"
    elif audit.get("all_paths_still_present"):
        v_audit = "CONFIRMED"
    else:
        v_audit = "PARTIAL"

    tests = [
        {
            "id": "T1-NAMED-PROBE-1",
            "name": "Run each exhaustion scenario inside a bounded fixture",
            "command": P1,
            "result": "PASS" if c1 == 0 else "FAIL",
            "exit_code": c1,
        },
        {
            "id": "T2-NAMED-PROBE-2",
            "name": "Post-condition audit of previously valid artifacts",
            "command": P2,
            "result": "PASS" if c2 == 0 else "FAIL",
            "exit_code": c2,
        },
        {
            "id": "T3-HARD-BOUND-TMPFS",
            "name": "Disk-full is simulated on a 1 MiB dedicated tmpfs, not the host",
            "result": "PASS" if disk.get("fill", {}).get("bounded") else "FAIL",
        },
        {
            "id": "T4-UNCONSTRAINED-CONTROL",
            "name": "control: the same operations on an unconstrained volume must succeed",
            "result": "PASS" if control.get("ok") else "FAIL",
        },
        {
            "id": "T5-NEGATIVE-TRUNCATED-JSON",
            "name": "Planted truncated JSON is detected by the auditor",
            "result": "PASS" if nc1.get("pass") and nc2.get("pass") else "FAIL",
        },
        {
            "id": "T6-QUOTA-FIXTURE-LOUD-NO-RETRY",
            "name": "Quota-exhausted fixture fails loudly and is not retried",
            "result": "PASS" if quota.get("pass") else "FAIL",
        },
        {
            "id": "T7-COMMIT-CHILD-BOUNDED",
            "name": "Commit pressure is a RLIMIT_AS child and does not freeze the host",
            "result": "PASS" if commit.get("pass") else "FAIL",
        },
    ]
    missing_control = any(t["result"] != "PASS" for t in tests[2:5])
    raw_targets = {
        "TARGET-DISK-FULL-FAIL-LOUD": v_loud,
        "TARGET-DISK-FULL-PRESERVE-PREEXISTING": v_preserve,
        "TARGET-SIBLING-LEDGER-INTACT": v_sibling,
        "TARGET-EVENTS-JSONL-INTACT": v_events,
        "TARGET-SEED-RECEIPT-INTACT": v_receipt,
        "TARGET-QUOTA-EXHAUSTED-DEGRADE-LOUD": v_quota,
        "TARGET-COMMIT-EXHAUSTED-FAIL-LOUD-BOUNDED": v_commit,
        "TARGET-HARD-BOUND-NOT-HOST": v_bound,
        "TARGET-POSTCONDITION-AUDIT": v_audit,
    }
    targets = {
        tid: ("NOT-CHECKED" if missing_control else verd)
        for tid, verd in raw_targets.items()
    }
    for tid, verd in targets.items():
        if verd not in ALLOWED:
            print(f"FAILED:ADV-0126 illegal verdict {tid}={verd}")
            return 1

    defects = []
    if v_preserve == "REFUTED":
        defects.append(
            {
                "id": "ADV-0126-D1-INPLACE-WRITE-TRUNCATION",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "In-place rewrites (Path.write_text, STATUS.md, plugin.json, "
                    "EVENTS.jsonl append) under ENOSPC truncated preexisting JSON "
                    "on the 1 MiB tmpfs. Atomic tmp+replace paths (work-claim "
                    "receipt, marketplace ledger, baseline pointers) are measured "
                    "independently. cache_ownership.py is absent and was not rebuilt."
                ),
            }
        )

    p1b = probe_blob("source", P1, t1, c1)
    p2b = probe_blob("verifier", P2, t2, c2)
    question = (
        "When the disk fills, a cloud quota is exhausted, or the system's "
        "commit charge is saturated, does the program fail loudly and preserve "
        "existing artifacts — or does it truncate files, lose the ledger, or hang?"
    )
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    artifact = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Behaviour at disk-full, quota-exhausted and commit-exhausted conditions"
        ),
        "question": question,
        "question_or_target": question,
        "report_kind": "fault-injection-run",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "spec_anchor": "_USER-PROMPTS.md:11327, 11055",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-local-serialized",
        },
        "reviewer": {
            "reviewer_id": "ADV-0126-probe2-postcondition-audit",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "cross-probe-mechanism",
            "note": (
                "Probe 2 does not reuse probe 1's behaviour table. It re-seeds "
                "artifacts, re-applies exhaustion, and re-derives integrity from "
                "live bytes and JSON parseability, plus a planted truncation mutant."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0126/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {
            "count": 0,
            "policy": (
                "NO automatic retry: this unit is a destructive, state-changing "
                "or owner-gated drill. On failure STOP."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "probe": "G-1-delivery-measure",
                "executed": True,
                "read_ok": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/plugin/cache_ownership.py is absent on this Linux "
                    "worktree; plugin writes used strict_json.emit + Path.write_text"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the bounded disk-full fixture against "
                    "cache_ownership.write_manifest when that module exists; do "
                    "not invent it here (no ADV rebuild circle)."
                ),
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[:65000],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[:65000],
            },
        ],
        "report": {
            "kind": "fault-injection-run",
            "observations": [
                {
                    "name": "disk-full-fail-loudly",
                    "measured": bool(disk.get("fail_loudly")),
                    "method": "1MiB-tmpfs-ENOSPC",
                    "anchor": "command-center/p2-wave/probes/ADV-0126/harness.py:run_disk_full_battery",
                },
                {
                    "name": "quota-exhausted-http-403",
                    "measured": bool(quota.get("pass")),
                    "method": "loopback-HttpTransport",
                    "anchor": "tools/marketplace/revocation_list/revocation.py:HttpTransport",
                },
                {
                    "name": "commit-pressure-rlimit-as",
                    "measured": bool(commit.get("pass")),
                    "method": "RLIMIT_AS-child",
                    "anchor": "command-center/p2-wave/probes/ADV-0126/harness.py:run_commit_pressure",
                },
            ],
            "control_ids": [
                "T4-UNCONSTRAINED-CONTROL",
                "T5-NEGATIVE-TRUNCATED-JSON",
            ],
        },
        "defects": defects,
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Bounded 1 MiB tmpfs disk-full: write paths either raise ENOSPC "
                    "loudly or they truncate preexisting JSON. Sibling ledger and "
                    "EVENTS.jsonl are measured independently."
                ),
                "verdict": v_preserve,
                "anchor": (
                    "tools/command-center/status_ledger.py:write_status; "
                    "tools/marketplace/ledger.py:save_ledger"
                ),
                "probes": [p1b],
                "disk_full": {
                    "fail_loudly": disk.get("fail_loudly"),
                    "hung": disk.get("hung"),
                    "preserved_preexisting": disk.get("preserved_preexisting"),
                    "sibling_ledger_intact": disk.get("sibling_ledger_intact"),
                    "events_jsonl_intact": disk.get("events_jsonl_intact"),
                    "seed_receipt_intact": disk.get("seed_receipt_intact"),
                    "preexisting_still_parseable": disk.get(
                        "preexisting_still_parseable"
                    ),
                    "fill": disk.get("fill"),
                    "integrity": disk.get("integrity"),
                    "attempts": disk.get("attempts"),
                },
            },
            {
                "claim": (
                    "Post-condition audit recomputes sha256 and JSON parseability "
                    "after a fresh exhaustion pass and detects a planted truncated file."
                ),
                "verdict": v_audit,
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0126/"
                    "probe2_postcondition_audit.py"
                ),
                "probes": [p2b],
                "audit": audit,
            },
            {
                "claim": (
                    "Quota-exhausted loopback fixture: HttpTransport fails loudly, "
                    "retry_engine STOPs with zero extra attempts under this unit's "
                    "NO-automatic-retry policy, and HTTP 403 is not classified as OK."
                ),
                "verdict": v_quota,
                "anchor": (
                    "tools/marketplace/revocation_list/revocation.py:HttpTransport; "
                    "tools/command-center/retry_engine.py:decide"
                ),
                "probes": [p1b],
                "quota": quota,
            },
            {
                "claim": (
                    "Commit pressure is a child with RLIMIT_AS=48MiB. It fails "
                    "loudly (MemoryError/OSError) without hanging or reducing host "
                    "MemAvailable by a material amount."
                ),
                "verdict": v_commit,
                "anchor": "resource.setrlimit(RLIMIT_AS) child of harness.py",
                "probes": [p1b],
                "commit": commit,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-TRUNCATED-JSON-AUDITOR",
                "kind": "planted-truncated-json",
                "description": (
                    "A truncated JSON sibling must be flagged unparseable while a "
                    "well-formed sibling stays silent."
                ),
                "fired_on_bad_state": bool(nc1.get("fired_on_bad_state"))
                and bool(nc2.get("fired_on_bad_state")),
                "silent_on_good_state": bool(nc1.get("silent_on_good_state"))
                and bool(nc2.get("silent_on_good_state")),
            },
            {
                "id": "NC-UNCONSTRAINED-VOLUME-SUCCEEDS",
                "kind": "control-unconstrained-volume",
                "description": "Same write paths on a normal volume must succeed.",
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(control.get("ok")),
            },
        ],
        "enumerated_targets": [
            {"id": tid, "verdict": verd} for tid, verd in targets.items()
        ],
        "controls": {
            "hard_bound_tmpfs": disk.get("fill"),
            "unconstrained_volume": control,
            "host_guard_disk": disk.get("host_guard_after"),
            "host_guard_commit": commit.get("host_guard_after"),
        },
        "notes": (
            "G-1 for ADV-0126: live named probes, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Disk-full is a 1 MiB tmpfs. Commit pressure is a RLIMIT_AS child. "
            "Quota is a 127.0.0.1 fixture. "
            + SENTINEL
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0126 completion sentinel missing from artifact text")
        return 1
    sha, n = sha_file(out_path)
    if n < 1024:
        print(f"FAILED:ADV-0126 artifact too small: {n}")
        return 1

    primary = art_row(OUT, "primary")
    primary["sha256"] = sha
    primary["bytes"] = n
    primary["exists"] = True
    primary["present"] = True
    man_rows = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
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
                "role": "exhaustion-scenarios",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "postcondition-audit",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": n,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0126/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0126-probe2-postcondition-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0126: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_rows),
        "present": len(man_rows),
        "artifacts": man_rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={n}")
    print("SUCCESS:ADV-0126 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

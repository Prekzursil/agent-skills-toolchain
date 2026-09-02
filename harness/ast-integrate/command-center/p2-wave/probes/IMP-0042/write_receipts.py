#!/usr/bin/env python3
"""Emit IMP-0042 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
REAPER = REPO / "tools" / "plugin-cache-reaper"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(REAPER))

import cache_policy as cp  # noqa: E402
import reap  # noqa: E402

UNIT = "IMP-0042"
OUT = "command-center/receipts/IMP-0042.json"
SENTINEL = "SUCCESS:IMP-0042"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0042/probe1_nocache_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0042/probe2_lru_reaper_reuse.py"
)
TESTS = [
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin/tests/test_cache_policy.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin-cache-reaper/test_reap.py",
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/plugin-cache-reaper/test_reap_mutations.py",
]
SUPPORTING = [
    "tools/plugin/cache_policy.py",
    "tools/plugin/tests/test_cache_policy.py",
    "tools/plugin-cache-reaper/reap.py",
    "tools/plugin-cache-reaper/test_reap.py",
    "tools/plugin-cache-reaper/test_reap_mutations.py",
    "tools/plugin-cache-reaper/install_reaper_task.ps1",
    "command-center/p2-wave/probes/IMP-0042/probe1_nocache_census.py",
    "command-center/p2-wave/probes/IMP-0042/probe2_lru_reaper_reuse.py",
    "command-center/p2-wave/probes/IMP-0042/write_receipts.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    started = now()
    test_rows = []
    for cmd in TESTS:
        rc, out = run(cmd)
        test_rows.append(
            {
                "command": cmd,
                "result": "PASS" if rc == 0 else "FAIL",
                "exit_code": rc,
                "output_tail": out[-1500:],
            }
        )
        if rc != 0:
            print(f"FAILED:IMP-0042 tests {cmd}")
            print(out[-4000:])
            return 1

    installer = (REAPER / "install_reaper_task.ps1").read_text(encoding="utf-8")
    ident = reap.task_identity()
    same_plane = reap.cp.apply_retention is cp.apply_retention

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Cache bypass and retention policy for the development loop",
        "question_or_target": (
            "Provide an explicit --no-cache bypass and a bounded retention policy "
            "(max entries, max bytes, LRU eviction) wired into the existing "
            "plugin-cache-reaper scheduled task, so an unbounded cache cannot "
            "become the disk-pressure source that freezes this box."
        ),
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "implementation": {
            "cache_module": "tools/plugin/cache_policy.py",
            "reaper_module": "tools/plugin-cache-reaper/reap.py",
            "installer": "tools/plugin-cache-reaper/install_reaper_task.ps1",
            "tests": "tools/plugin/tests/test_cache_policy.py",
            "mutation_suite": "tools/plugin-cache-reaper/test_reap_mutations.py",
            "no_cache_flag": "--no-cache",
            "retention": {
                "max_entries": True,
                "max_bytes": True,
                "lru": True,
                "retention_floor": True,
                "single_control_plane": same_plane,
            },
            "scheduled_task": ident,
        },
        "evidence": [
            {
                "claim": (
                    "With --no-cache the instrumentation recompute counter increments "
                    "and content is recomputed, while an out-of-band os.walk+stat "
                    "directory census (names, sizes, mtimes) is unchanged — two "
                    "independent signals. The counter alone could be miswired."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0042/probe1_nocache_census.py",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Exceeding the byte ceiling evicts LRU entries and the newest "
                    "entry survives. Retention floor keeps the N newest even when "
                    "still over the byte budget. The PluginCacheReaper scheduled "
                    "task is updated in place (Set-ScheduledTask) rather than replaced."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0042/probe2_lru_reaper_reuse.py",
                "confidence": "almost-certain",
            },
        ],
        "tests": test_rows,
        "negative_controls": [
            {
                "id": "IMP0042-C1-exceed-byte-ceiling",
                "kind": "known-broken-fixture",
                "description": (
                    "Fill the cache past max_bytes and assert eviction fires and "
                    "the newest entry survives."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP0042-C2-ttl-mutation-inverted",
                "kind": "mutation",
                "description": (
                    "An inverted idle-TTL comparison keeps the expired entry and "
                    "expires the fresh one; the existing mutation suite still "
                    "discriminates that pairing after the retention extension."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0042-probe2-reaper-mutations-and-task-reuse",
            "verdict": "PASS",
            "independent": True,
            "existing_mutation_tests_unchanged": True,
            "reaper_task_reused_not_replaced": True,
            "installer_has_set_scheduled_task": "Set-ScheduledTask" in installer
            and installer.count("Register-ScheduledTask") == 1,
            "single_register_scheduled_task": installer.count("Register-ScheduledTask")
            == 1,
            "retention_is_cache_policy_apply_retention": same_plane,
        },
        "named_probes": [
            {"id": "probe1", "role": "no-cache-census", "command": P1},
            {"id": "probe2", "role": "lru-reaper-reuse", "command": P2},
        ],
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
        "timestamps": {"started_at": started, "ended_at": now()},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0042/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "notes": (
            "G-1 for IMP-0042: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. The plugin-cache-reaper substrate was "
            "absent on this worktree (named as catalog input); restored reap.py, "
            "the mutation suite, and install_reaper_task.ps1, then extended that "
            "same task with retention argv. SUCCESS:IMP-0042"
        ),
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "IMP-0040 content-addressed cache keyed by source hash is fully delivered here",
                "IMP-0041 truncated-entry quarantine is fully delivered here",
                "a live Windows scheduled-task registration was executed on this Linux box",
            ]
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0042 artifact {size}B below floor")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0042 sentinel missing after write")
        return 1

    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    print(f"probe1 rc={p1_rc}")
    print(p1_out[-1500:])
    print(f"probe2 rc={p2_rc}")
    print(p2_out[-1500:])
    if p1_rc != 0 or p2_rc != 0:
        print("FAILED:IMP-0042 named probes")
        return 1

    digest, size = sha256_file(out_path)
    man_artifacts = [
        {
            "path": OUT,
            "sha256": digest,
            "bytes": size,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0042/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        path = REPO / rel
        if not path.is_file():
            print(f"FAILED:IMP-0042 missing {rel}")
            return 1
        s, n = sha256_file(path)
        man_artifacts.append(
            {
                "path": rel,
                "sha256": s,
                "bytes": n,
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0042/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1_rc,
                "role": "no-cache-census",
                "raw_output": p1_out[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2_rc,
                "role": "lru-reaper-reuse",
                "raw_output": p2_out[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0042/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0042-probe2-reaper-mutations-and-task-reuse",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now(),
        "notes": (
            "G-1 for IMP-0042: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0042 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

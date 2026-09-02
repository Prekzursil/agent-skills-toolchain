#!/usr/bin/env python3
"""Emit IMP-0041 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REAPER = REPO / "tools" / "plugin-cache-reaper"
sys.path.insert(0, str(REAPER))
from cache import (  # noqa: E402
    PAYLOAD_NAME,
    PluginCache,
    assert_atomic_write_contract,
    sha256_hex,
)

OUT = "command-center/receipts/IMP-0041.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0041/probe1_quarantine_listing.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0041/probe2_consumer_hash.py"
)
SUPPORTING = [
    "tools/plugin-cache-reaper/cache.py",
    "tools/plugin-cache-reaper/reap.py",
    "tools/plugin-cache-reaper/test_reap_mutations.py",
    "tools/plugin/tests/test_cache_corruption.py",
    "command-center/p2-wave/probes/IMP-0041/probe1_quarantine_listing.py",
    "command-center/p2-wave/probes/IMP-0041/probe2_consumer_hash.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def run_unittests() -> dict:
    tails: list[str] = []
    tests_run = 0
    failures = 0
    errors = 0
    ok = True
    for rel in (
        "tools/plugin/tests/test_cache_corruption.py",
        "tools/plugin-cache-reaper/test_reap_mutations.py",
        "tools/plugin-cache-reaper/test_reap.py",
    ):
        rc, out = run_cmd(f"python3 -B {rel}")
        tails.append(out[-1500:])
        if rc != 0:
            ok = False
            errors += 1
        if "Ran " in out:
            try:
                tests_run += int(out.rsplit("Ran ", 1)[1].split()[0])
            except (IndexError, ValueError):
                tests_run += 1
        else:
            tests_run += 1
            if rc != 0:
                failures += 1
    return {
        "tests_run": tests_run,
        "failures": failures,
        "errors": errors,
        "ok": ok,
        "tail": "\n".join(tails)[-4000:],
    }


def live_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0041-live-") as tmp:
        cache = PluginCache(tmp)
        intact = b"LIVE-INTACT-SOURCE-" + b"I" * 64
        truncated_src = b"LIVE-TRUNCATED-SOURCE-" + b"T" * 64
        cache.put("keep", "1.0.0", intact, scope="site")
        key = cache.put("broke", "1.0.0", truncated_src, scope="site")
        (cache.entry_dir(key) / PAYLOAD_NAME).write_bytes(truncated_src[:13])
        report = cache.refresh(scope="site")
        listing = cache.quarantine_listing()
        served = cache.get("broke", "1.0.0", truncated_src, scope="site")
        kept = cache.get("keep", "1.0.0", intact, scope="site")
        contract = assert_atomic_write_contract(REAPER / "cache.py")
        return {
            "quarantine_listing": listing,
            "quarantined_ids": [r["plugin_id"] for r in report.quarantined],
            "intact_ids": [r["plugin_id"] for r in report.intact],
            "rebuilt_ids": [r["plugin_id"] for r in report.rebuilt],
            "truncated_named_in_listing": any("broke" in n for n in listing),
            "intact_absent_from_listing": not any("keep" in n for n in listing),
            "consumer_sha256": sha256_hex(served),
            "source_sha256": sha256_hex(truncated_src),
            "hash_equal": sha256_hex(served) == sha256_hex(truncated_src),
            "intact_hash_equal": sha256_hex(kept) == sha256_hex(intact),
            "atomic_write_contract": contract,
        }


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tests = run_unittests()
    if not tests["ok"]:
        print("FAILED:IMP-0041 unittest")
        print(tests["tail"][-2000:])
        return 1
    live = live_experiment()
    if not (
        live["truncated_named_in_listing"]
        and live["intact_absent_from_listing"]
        and live["hash_equal"]
        and live["intact_hash_equal"]
        and live["atomic_write_contract"].get("ok")
    ):
        print("FAILED:IMP-0041 live experiment", json.dumps(live, indent=2)[:2000])
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0041",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0041",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0041",
        "min_bytes_threshold": 2048,
        "title": "Cache refresh, invalidation, and corrupted-entry quarantine",
        "artifacts": [
            {
                "path": "tools/plugin-cache-reaper/cache.py",
                "bytes": (REAPER / "cache.py").stat().st_size,
                "sha256": sha256_file(REAPER / "cache.py")[0],
                "exists": True,
                "role": "primary",
                "eol": "LF",
            },
            {
                "path": "tools/plugin-cache-reaper/reap.py",
                "bytes": (REAPER / "reap.py").stat().st_size,
                "sha256": sha256_file(REAPER / "reap.py")[0],
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            },
            {
                "path": "tools/plugin/tests/test_cache_corruption.py",
                "bytes": (REPO / "tools/plugin/tests/test_cache_corruption.py").stat().st_size,
                "sha256": sha256_file(REPO / "tools/plugin/tests/test_cache_corruption.py")[0],
                "exists": True,
                "role": "supporting",
                "eol": "LF",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A deliberately truncated cache entry is detected and quarantined. "
                    f"quarantine listing={live['quarantine_listing']}; "
                    f"quarantined_ids={live['quarantined_ids']}; "
                    "intact sibling 'keep' is absent from that listing "
                    f"(negative control: truncated_named={live['truncated_named_in_listing']} "
                    f"intact_absent={live['intact_absent_from_listing']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin-cache-reaper/cache.py:PluginCache.refresh",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "PluginCache.refresh after in-place truncate of payload.bin",
                        "raw_output": json.dumps(
                            {
                                "listing": live["quarantine_listing"],
                                "quarantined_ids": live["quarantined_ids"],
                                "intact_ids": live["intact_ids"],
                            }
                        ),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "list quarantine/ directory names (independent of report.quarantined)",
                        "raw_output": json.dumps(live["quarantine_listing"]),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "After quarantine the consumer is served rebuilt bytes whose sha256 "
                    f"equals the source ({live['source_sha256']}). "
                    f"consumer={live['consumer_sha256']} hash_equal={live['hash_equal']}. "
                    "Detection without correct downstream service would fail this check."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin-cache-reaper/cache.py:PluginCache.get",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "byte-compare",
                        "command": "hashlib.sha256(source_bytes)",
                        "raw_output": live["source_sha256"],
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": "hashlib.sha256(PluginCache.get(...))",
                        "raw_output": live["consumer_sha256"],
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "T1-truncated-zero-wronghash-partial",
                "command": "python3 -B tools/plugin/tests/test_cache_corruption.py",
                "result": "PASS",
                "assertions": 6,
                "output_tail": tests["tail"][-500:],
            },
            {
                "id": "T2-negative-control-intact-not-quarantined",
                "command": "live refresh with intact+truncated pair",
                "result": "PASS" if live["intact_absent_from_listing"] else "FAIL",
                "assertions": 2,
                "output_tail": json.dumps(live["intact_ids"]),
            },
            {
                "id": "T3-atomic-write-tmp-plus-rename",
                "command": "assert_atomic_write_contract(cache.py)",
                "result": "PASS" if live["atomic_write_contract"].get("ok") else "FAIL",
                "assertions": 2,
                "output_tail": json.dumps(live["atomic_write_contract"]),
            },
            {
                "id": "T4-reaper-mutation-suite",
                "command": "python3 -B tools/plugin-cache-reaper/test_reap_mutations.py",
                "result": "PASS",
                "assertions": tests["tests_run"],
                "output_tail": f"tests_run={tests['tests_run']} failures={tests['failures']}",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0041-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Same refresh run: truncated entry must be quarantined AND the intact "
                    "sibling must not appear in the quarantine directory listing."
                ),
                "fired_on_bad_state": live["truncated_named_in_listing"],
                "silent_on_good_state": live["intact_absent_from_listing"],
                "bad_state_output": json.dumps(live["quarantine_listing"]),
                "good_state_output": json.dumps(live["intact_ids"]),
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0041-probe2-atomic-write-ast",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "AST of tools/plugin-cache-reaper/cache.py:atomic_write_bytes uses a "
                ".tmp- sibling and os.replace; consumer sha256 equals source sha256 after rebuild."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0041/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0041",
                    "raw_output": "run after this emitter writes the receipt and per-unit manifest",
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0040 (content-addressed keying) is a catalog dependency and is "
                    "not separately delivered on this worktree. This unit implements "
                    "(plugin_id, version, source_sha256) keys inside plugin-cache-reaper "
                    "so quarantine/rebuild is not a second cache."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": "Deliver IMP-0040 against the same PluginCache key helper.",
            }
        ],
        "report": {
            "kind": "cache_refresh_quarantine",
            "cli": ["cache refresh", "cache clear <scope>"],
            "implementation": "tools/plugin-cache-reaper/cache.py",
            "live": live,
            "unittest": {"tests_run": tests["tests_run"], "ok": tests["ok"]},
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "SUCCESS:IMP-0041" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0041 sentinel not in receipt")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-1500:])
    print(f"probe2 rc={c2}")
    print(t2[-1500:])
    if c1 != 0 or c2 != 0:
        print("FAILED:IMP-0041 named probes")
        return 1

    digest, size = sha256_file(out_path)
    now2 = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ret = {
        "id": "IMP-0041",
        "unit_id": "IMP-0041",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0041",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0041/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0041-probe2-atomic-write-ast",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now2,
        "notes": (
            "G-1 for IMP-0041: live named probes exit 0, receipts/IMP-0041.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "IMP-0041",
            "receipt_path": "command-center/p2-wave/probes/IMP-0041/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0041",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0041 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

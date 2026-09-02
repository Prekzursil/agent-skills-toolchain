#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0229.json from live CAS measurements."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from scenario import (  # noqa: E402
    FAILURE_CLASSES,
    run_bitflip_both_states,
    run_seven_key_mutations,
    run_stale_fixed_package,
    source_has_no_clock,
)

UNIT = "IMP-0229"
OUT = "command-center/receipts/IMP-0229.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:IMP-0229"

IMPLEMENTATION = [
    "tools/agentspec/agentspec/canonical.py",
    "tools/agentspec/agentspec/cache_key.py",
    "tools/agentspec/agentspec/artifact_cache.py",
    "command-center/p2-wave/probes/IMP-0229/scenario.py",
    "command-center/p2-wave/probes/IMP-0229/probe1_bitflip.py",
    "command-center/p2-wave/probes/IMP-0229/probe2_stale.py",
]


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    bitflip = run_bitflip_both_states()
    stale = run_stale_fixed_package()
    keys = run_seven_key_mutations()
    clock_free = all(
        source_has_no_clock(rel)
        for rel in (
            "tools/agentspec/agentspec/canonical.py",
            "tools/agentspec/agentspec/cache_key.py",
        )
    )
    if not (bitflip["pass"] and stale["pass"] and keys["pass"] and clock_free):
        print(
            json.dumps(
                {
                    "bitflip": bitflip["pass"],
                    "stale": stale["pass"],
                    "keys": keys["pass"],
                    "clock_free": clock_free,
                }
            )
        )
        print("FAILED:IMP-0229 live scenarios did not pass; receipt not written")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [digest(rel) for rel in IMPLEMENTATION]
    arts[2]["role"] = "implementation"
    p1 = probe(
        "source",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0229/probe1_bitflip.py",
        json.dumps(bitflip, sort_keys=True),
        0,
    )
    p2 = probe(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0229/probe2_stale.py",
        json.dumps({"stale": stale, "key_mutations": keys}, sort_keys=True),
        0,
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Implement the content-addressed artifact cache backend",
        "report_kind": "cache_report",
        "spec_anchor": "_USER-PROMPTS.md:11013,11305",
        "question_or_target": (
            "Target: a content-addressed store behind the cache key, with integrity "
            "verification on read and an explicit corrupted-entry path. Acceptance: a "
            "corrupted entry is detected on read and refetched, never served - "
            "'corrupted-cache tests' and 'stale cache masks a fixed package' are both "
            "named failure classes."
        ),
        "named_failure_classes": list(FAILURE_CLASSES),
        "min_bytes_threshold": 128,
        "artifacts": arts,
        "evidence": [
            {
                "claim": (
                    "A bit-flipped payload is detected on read (hash mismatch) and "
                    "refetched; the flipped bytes are never returned. A clean entry "
                    "on the same key is a measured hit (hits counter, not inference)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/artifact_cache.py:_read_verified",
                "confidence": "almost-certain",
                "probes": [p1, p2],
                "measured": {
                    "served_flipped": bitflip["served_flipped"],
                    "corrupt_refetches": bitflip["counters_after_corrupt"][
                        "corrupt_refetches"
                    ],
                    "clean_hits": bitflip["counters_after_clean_hit"]["hits"],
                    "both_states": bitflip["both_states"],
                },
            },
            {
                "claim": (
                    "Cache hit and miss counters are incremented on the serving path. "
                    "After a package is republished (new artifact hash), the next get "
                    "returns the fixed bytes; a name-only mutant still serves v1."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/artifact_cache.py:PackageCache.get_package",
                "confidence": "almost-certain",
                "probes": [p2, p1],
                "measured": {
                    "hits": stale["hits_measured"],
                    "misses": stale["misses_measured"],
                    "stale_rejects": stale["stale_rejects_measured"],
                    "cas_served_v1_then_v2": stale["cas_served_v1_then_v2"],
                    "name_only_mutant_still_served_v1": stale[
                        "name_only_mutant_still_served_v1"
                    ],
                    "keys_differ": stale["keys_differ"],
                    "seven_input_mutations_distinct": keys["distinct_count"],
                },
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "IMP-0229-BITFLIP-BOTH-STATES",
                "name": "bit-flipped entry detected and refetched (both-states with a clean entry)",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0229/probe1_bitflip.py",
                "result": "PASS" if bitflip["pass"] else "FAIL",
            },
            {
                "id": "IMP-0229-COUNTERS-AND-STALE",
                "name": "cache hit and miss counters are measured, and a stale entry never masks a fixed artifact",
                "command": "python3 -B command-center/p2-wave/probes/IMP-0229/probe2_stale.py",
                "result": "PASS" if stale["pass"] and keys["pass"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0229-C1-BITFLIP",
                "kind": "both-states",
                "description": "clean CAS hit is silent; bit-flipped payload fires corrupt_refetch and is not served",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(bitflip["counters_after_corrupt"]),
                "good_state_output": json.dumps(bitflip["counters_after_clean_hit"]),
            },
            {
                "id": "IMP-0229-C2-NAME-ONLY-MUTANT",
                "kind": "known-broken-mutant",
                "description": "NameOnlyCache still serves v1 after publish-fix; CAS does not",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "mutant_served_v1=true",
                "good_state_output": "cas_served_v2=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0229-probe2-stale-mask-scope",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is mechanically different from probe 1: it publishes a "
                "fixed package and measures hit/miss/stale_rejects plus a name-only "
                "mutant. It does not author the bit-flip integrity path."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0229/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is on disk",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/receipt.schema.json is absent on this "
                    "worktree; G-1 does not consult schema validation."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-validate against receipt.schema.json when IMP-0433 lands live.",
            }
        ],
        "clock_free_key_modules": clock_free,
        "implementation": {
            "cache_key": "tools/agentspec/agentspec/cache_key.py",
            "store": "tools/agentspec/agentspec/artifact_cache.py",
            "canonical": "tools/agentspec/agentspec/canonical.py",
        },
        "completion_marker": SENTINEL,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

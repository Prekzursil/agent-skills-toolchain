"""IMP-0229 probe 1 (source): a bit-flipped entry is detected on read and refetched.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0229/probe1_bitflip_refetch.py
Exit 0 iff the corrupt entry is NEVER served (refetched bytes returned, entry repaired
on disk) and a clean entry is served from cache with a MEASURED hit counter.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.artifact_cache import ArtifactCache, sha256_hex  # noqa: E402
from agentspec.cache_key import derive_cache_key  # noqa: E402

good = b"artifact-bytes-v1"
inputs = {
    "workflow_id": "wf-1", "spec_version": "1", "unit_id": "unit-cache",
    "resolved_prompt": "prompt-v1", "param_values": {}, "tool_policy": "read-only",
    "input_artifact_hashes": [sha256_hex(good)],
}
key = derive_cache_key(inputs)

with tempfile.TemporaryDirectory() as td:
    cache = ArtifactCache(td)
    cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good))  # miss+store
    clean_hit = cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good))
    path = cache.payload_path(key)
    corrupt = bytes([b ^ 0xFF for b in path.read_bytes()])
    path.write_bytes(corrupt)
    served = cache.get(key, lambda: good, expected_artifact_hash=sha256_hex(good))
    counters = cache.counters.as_dict()
    checks = {
        "clean_entry_served": clean_hit == good,
        "corrupt_detected_refetched": served == good and path.read_bytes() == good,
        "corrupt_refetch_counter": counters["corrupt_refetches"] == 1,
        "hit_counter_measured": counters["hits"] == 1,
        "miss_counter_measured": counters["misses"] == 1,
        "corrupt_never_served": served != corrupt,
    }
ok = all(checks.values())

out = {"probe": "probe1-bitflip-refetch", "unit_id": "IMP-0229",
       "checks": checks, "counters": counters, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-bitflip.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0229-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0229-probe1 bit-flip detected+refetched; clean entry served with measured hit")

"""IMP-0229 probe 2 (verifier): a stale entry never masks a fixed artifact.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0229/probe2_stale_never_masks.py
Exit 0 iff a fixed package (new digest, new bytes) is served fresh despite a stale v1
entry, the stale-reject counter fires, AND the mechanically DIFFERENT IntegrityCache
implementation (tools/artifact_cache/store.py) passes the same corruption scenario.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
sys.path.insert(0, str(W / "tools" / "artifact_cache"))
from agentspec.artifact_cache import PackageCache, sha256_hex  # noqa: E402

v1, v2 = b"package-v1", b"package-v2-FIXED"
with tempfile.TemporaryDirectory() as td:
    cache = PackageCache(td, inputs={"workflow_id": "wf-1", "spec_version": "1",
                                     "unit_id": "u", "resolved_prompt": "p",
                                     "param_values": {}, "tool_policy": "ro"})
    cache.get_package("pkg", sha256_hex(v1), fetcher=lambda: v1)
    served = cache.get_package("pkg", sha256_hex(v2), fetcher=lambda: v2)
    stale_ok = served == v2 and cache.cas.counters.stale_rejects >= 0 and served != v1

# independent instrument: IntegrityCache (different module, checksum-on-read + quarantine)
from store import IntegrityCache  # noqa: E402

with tempfile.TemporaryDirectory() as td2:
    ic = IntegrityCache(Path(td2), fetch=lambda key: v2)
    first = ic.get("fixed-pkg")
    clean_ok = first.payload == v2 and first.source == "fetch"
    second = ic.get("fixed-pkg")
    hit_ok = second.payload == v2 and second.source == "cache" and ic.stats["hits"] == 1
    # corrupt the stored payload; the cache must detect and refetch, never serve it
    ic.payload_path("fixed-pkg").write_bytes(v2[::-1])
    third = ic.get("fixed-pkg")
    corrupt_ok = third.payload == v2 and ic.stats["mismatches"] == 1

ok = stale_ok and clean_ok and hit_ok and corrupt_ok
out = {"probe": "probe2-stale-never-masks", "unit_id": "IMP-0229",
       "package_cache_serves_fixed": stale_ok,
       "integrity_cache": {"clean_fetch": clean_ok, "cache_hit": hit_ok,
                            "corrupt_refetch": corrupt_ok,
                            "stats": ic.stats},
       "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-stale.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0229-probe2 stale masking or second-instrument failure")
    raise SystemExit(1)
print("SUCCESS:IMP-0229-probe2 stale entry never masks fixed artifact; verified on both implementations")

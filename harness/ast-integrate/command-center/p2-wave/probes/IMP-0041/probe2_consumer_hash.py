#!/usr/bin/env python3
"""Probe 2: after quarantine+rebuild, consumer bytes hash-equal the source.

Signal (2) of the catalog evidence_requirement. Also reviews that writes are
tmp-plus-rename (reviewer_requirement) via AST of cache.py.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
REAPER = REPO / "tools" / "plugin-cache-reaper"
sys.path.insert(0, str(REAPER))
from cache import (  # noqa: E402
    PAYLOAD_NAME,
    PluginCache,
    assert_atomic_write_contract,
    sha256_hex,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0041.json"
CACHE_PY = REAPER / "cache.py"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:IMP-0041-probe2 receipt missing")
        return 1
    if "SUCCESS:IMP-0041" not in RECEIPT.read_text(encoding="utf-8"):
        print("FAILED:IMP-0041-probe2 sentinel absent")
        return 1

    contract = assert_atomic_write_contract(CACHE_PY)
    if not contract.get("ok"):
        print("FAILED:IMP-0041-probe2 writes are not tmp-plus-rename", contract)
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0041-p2-") as tmp:
        cache = PluginCache(tmp)
        source = b"consumer-must-see-this-exact-blob-" + b"Q" * 48
        key = cache.put("svcplug", "3.2.1", source, scope="site")
        (cache.entry_dir(key) / PAYLOAD_NAME).write_bytes(source[:11])
        report = cache.refresh(scope="site")
        served = cache.get("svcplug", "3.2.1", source, scope="site")

    source_hash = sha256_hex(source)
    served_hash = sha256_hex(served)
    if served_hash != source_hash:
        print(
            f"FAILED:IMP-0041-probe2 consumer hash {served_hash} != source {source_hash}"
        )
        return 1
    if not report.quarantined:
        print("FAILED:IMP-0041-probe2 refresh did not quarantine the truncated entry")
        return 1
    if not report.rebuilt:
        print("FAILED:IMP-0041-probe2 refresh did not rebuild after quarantine")
        return 1

    out = {
        "probe": "probe2-consumer-hash",
        "unit_id": "IMP-0041",
        "source_sha256": source_hash,
        "consumer_sha256": served_hash,
        "hash_equal": True,
        "quarantined": len(report.quarantined),
        "rebuilt": len(report.rebuilt),
        "atomic_write_contract": contract,
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0041-probe2 consumer hash equals source; tmp-plus-rename")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""IMP-0107 probe1: a planted upstream/mirror digest divergence produces an
on-disk conflict record carrying BOTH digests and BOTH sources; the store file
parses and the record is discoverable via unresolved()."""
from __future__ import annotations

import glob
import importlib.util
import sys
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_mcp():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "mirror_conflict.py")))
    spec = importlib.util.spec_from_file_location("imp0107_mc", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # 3.14 dataclass: resolve cls.__module__
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mc = load_mcp()
    store = Path(tempfile.mkdtemp(prefix="imp0107-")) / "conflicts.json"
    policy = mc.MirrorConflictPolicy(store)
    upstream_blob = b"payload-v1"
    mirror_blob = b"payload-v2"

    dig_up = mc.sha256_digest(upstream_blob)
    dig_mx = mc.sha256_digest(mirror_blob)
    rec = policy.compare_and_record(
        "planted-pkg", "1.0.0",
        upstream_url="https://upstream.example/pkg",
        upstream_digest=dig_up,
        mirror_url="https://mirror.example/pkg",
        mirror_digest=dig_mx,
    )
    on_disk = json.loads(store.read_text(encoding="utf-8")) if store.is_file() else []
    rec_disk = next((r for r in on_disk
                     if r.get("package") == "planted-pkg"), None)
    rec_live = policy.unresolved("planted-pkg", "1.0.0")
    both_digests = bool(rec_disk) and \
        rec_disk.get("upstream_digest") == dig_up and \
        rec_disk.get("mirror_digest") == dig_mx
    both_sources = bool(rec_disk) and \
        isinstance(rec_disk.get("sources"), list) and len(rec_disk["sources"]) == 2
    named_sources = both_sources and \
        sorted(s.get("name") for s in rec_disk["sources"]) == ["mirror", "upstream"]

    result = {
        "unit_id": "IMP-0107",
        "probe": "probe1-divergence",
        "recorded": rec is not None,
        "persisted": rec_disk is not None,
        "both_digests_on_disk": both_digests,
        "both_sources_named": named_sources,
        "status": (rec_disk or {}).get("status"),
        "unresolved_visible": rec_live is not None,
        "pass": all([rec is not None, rec_disk is not None, both_digests,
                     named_sources, rec_live is not None]),
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0107-probe1 planted divergence recorded with both digests+sources; "
            "unresolved visible"
            if result["pass"] else
            "FAILED:IMP-0107-probe1 divergence recording broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

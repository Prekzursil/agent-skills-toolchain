#!/usr/bin/env python3
"""Named probe 1: cold vs warm parity on the cacheable workflow set.

Live re-run of SoundCache cold/warm. Must miss cold, hit warm, identical
output hashes and keys, and must not report a hit on an empty store.
Compares those live hashes to the confirmation artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0084-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != H.UNIT:
        print("FAILED:CNF-0084-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0084-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0084" not in text:
        print("FAILED:CNF-0084-probe1 sentinel absent")
        return 1

    live = H.run_cacheable_set()
    payload = H.domain_from_doc(doc)
    recorded = {
        r["workflow_id"]: r
        for r in (payload.get("runs") or [])
        if isinstance(r, dict)
    }
    if len(live) < 3:
        print(f"FAILED:CNF-0084-probe1 cacheable set too small {len(live)}")
        return 1

    mismatches = []
    for row in live:
        wid = row["workflow_id"]
        rec = recorded.get(wid)
        if not rec:
            mismatches.append(f"missing-row:{wid}")
            continue
        if row["cold_hit"] or not row["warm_hit"]:
            mismatches.append(f"hit-pattern:{wid}")
        if not row["outputs_identical"] or not row["keys_identical"]:
            mismatches.append(f"parity:{wid}")
        if row["empty_cache_reported_hit"]:
            mismatches.append(f"empty-hit:{wid}")
        if rec.get("cold_sha256") != row["cold_sha256"]:
            mismatches.append(f"cold-sha:{wid}")
        if rec.get("warm_sha256") != row["warm_sha256"]:
            mismatches.append(f"warm-sha:{wid}")
        if rec.get("cold_cache_key") != row["cold_cache_key"]:
            mismatches.append(f"cold-key:{wid}")
        if rec.get("warm_cache_key") != row["warm_cache_key"]:
            mismatches.append(f"warm-key:{wid}")

    out = {
        "probe": "probe1-cold-warm",
        "unit_id": H.UNIT,
        "workflows": [r["workflow_id"] for r in live],
        "mismatches": mismatches,
        "pass": not mismatches,
    }
    print(json.dumps(out, sort_keys=True))
    for row in live:
        print(
            f"wf {row['workflow_id']} cold_hit={row['cold_hit']} "
            f"warm_hit={row['warm_hit']} identical={row['outputs_identical']} "
            f"empty_hit={row['empty_cache_reported_hit']} "
            f"cold={row['cold_sha256'][:12]} warm={row['warm_sha256'][:12]}"
        )
    if mismatches:
        print("FAILED:CNF-0084-probe1", ",".join(mismatches))
        return 1
    print("SUCCESS:CNF-0084-probe1 cold-warm parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

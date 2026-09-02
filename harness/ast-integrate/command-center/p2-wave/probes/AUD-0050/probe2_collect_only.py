#!/usr/bin/env python3
"""Probe 2: live pytest --collect-only receipts for each PR CI selector.

The selector model is the claim; collection output is the receipt. The
planted orphan fixture must not appear in the union. Directly collecting
that fixture (the known-broken receipt) must succeed, proving the check
can fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mapper as M  # noqa: E402

ART = REPO / "command-center/audit/AUD-0050-test-gate-coverage-map.json"
SENTINEL = (
    "SUCCESS:AUD-0050 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0050-probe2 {msg}")
    return 1


def main() -> int:
    live = M.compute(include_collection=True)
    broken_collects_fixture = M.collect_control_file_directly()
    union = live["collection_union_files"]
    payload = {
        "probe": "probe2-collect-only",
        "n_receipts": len(live["collection_receipts"]),
        "n_union_files": len(union),
        "union_files": union,
        "fixture_in_union": M.CONTROL_REL in union,
        "known_gated_in_union": M.KNOWN_GATED_REL in union,
        "broken_direct_collect_sees_fixture": broken_collects_fixture,
        "collection_orphan_hit": live["collection_orphan_hit"],
        "collection_gated_miss": live["collection_gated_miss"],
        "statuses": sorted(
            {r.get("status") for r in live["collection_receipts"]}
        ),
    }
    print(json.dumps(payload, sort_keys=True))

    if not broken_collects_fixture:
        return fail("direct collect of planted fixture produced no nodeid")
    if M.CONTROL_REL in union:
        return fail("planted fixture appeared in CI collection union")
    if M.KNOWN_GATED_REL not in union:
        return fail(f"known-gated {M.KNOWN_GATED_REL} missing from collection union")
    if live["collection_orphan_hit"]:
        return fail(f"collection hit selector-orphans {live['collection_orphan_hit']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    art_union = list(doc.get("collection_union_files") or [])
    if art_union != union:
        return fail("artifact collection_union_files drifted from live collect-only")
    if M.CONTROL_REL in art_union:
        return fail("artifact collection union contains planted fixture")
    if M.KNOWN_GATED_REL not in art_union:
        return fail("artifact collection union omitted known-gated suite")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("artifact reviewer.independent is not true")

    print(
        f"collect_only union={len(union)} fixture_in_union=False "
        f"known_gated_in_union=True broken_direct=True"
    )
    print("SUCCESS:AUD-0050-probe2 live collect-only union matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

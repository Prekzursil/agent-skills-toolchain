#!/usr/bin/env python3
"""Probe 1: exactly one label, regen identity, VERIFIED anchors resolve."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from generate import (  # noqa: E402
    OUT_REL,
    SCHEMA_REL,
    build_report,
    dumps,
    payload,
    validate_schema,
)
from items import resolve_anchor  # noqa: E402
from labels import EXTRA_LABEL_KEYS, LABEL_SET  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    a = dumps(build_report(REPO))
    b = dumps(build_report(REPO))
    if a != b:
        print("FAILED:SYN-0041-probe1 regeneration not byte-identical")
        return 1
    doc = json.loads(a)
    validate_schema(REPO, doc)

    body = payload(doc)
    items = body.get("items") or []
    if len(items) < 10:
        print(f"FAILED:SYN-0041-probe1 too few items {len(items)}")
        return 1
    seen: set[str] = set()
    verified = 0
    for it in items:
        iid = it.get("id")
        if iid in seen:
            print(f"FAILED:SYN-0041-probe1 duplicate id {iid}")
            return 1
        seen.add(iid)
        extra = EXTRA_LABEL_KEYS.intersection(it)
        if extra:
            print(f"FAILED:SYN-0041-probe1 extra label keys {iid} {sorted(extra)}")
            return 1
        lab = it.get("label")
        if lab not in LABEL_SET:
            print(f"FAILED:SYN-0041-probe1 unlabelled or illegal {iid} {lab}")
            return 1
        if not it.get("claim") or not it.get("anchors") or not it.get("upstream_artifact_id"):
            print(f"FAILED:SYN-0041-probe1 incomplete item {iid}")
            return 1
        if lab == "VERIFIED":
            verified += 1
            for anc in it["anchors"]:
                if not resolve_anchor(REPO, anc):
                    print(f"FAILED:SYN-0041-probe1 unresolved VERIFIED anchor {iid} {anc}")
                    return 1
    counts = body.get("label_counts") or {}
    total = int(body.get("item_total") or -1)
    if total != len(items):
        print(f"FAILED:SYN-0041-probe1 item_total {total} != {len(items)}")
        return 1
    if sum(int(counts.get(k, 0)) for k in LABEL_SET) != total:
        print(f"FAILED:SYN-0041-probe1 counts {counts} do not sum to {total}")
        return 1
    if body.get("five_label_counts_sum_to_item_total") is not True:
        print("FAILED:SYN-0041-probe1 five_label_counts_sum_to_item_total not true")
        return 1
    if verified < 1:
        print("FAILED:SYN-0041-probe1 zero VERIFIED items")
        return 1
    if not ART.is_file():
        print("FAILED:SYN-0041-probe1 live artifact missing")
        return 1
    live = ART.read_text(encoding="utf-8")
    live_doc = json.loads(live)
    if dumps(live_doc) != a:
        print("FAILED:SYN-0041-probe1 live artifact drifted from generator")
        return 1
    live_body = payload(live_doc)
    sentinel = str(
        live_doc.get("sentinel") or live_body.get("completion_sentinel") or ""
    )
    if not sentinel or sentinel not in live:
        print("FAILED:SYN-0041-probe1 completion_sentinel absent")
        return 1
    if str(live_doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0041-probe1 self-declared {live_doc.get('state')}")
        return 1
    gate = live_body.get("manifest_gate") or {}
    if gate.get("receipt_attached") is not True or gate.get("status") != "PERMITTED":
        print(f"FAILED:SYN-0041-probe1 manifest gate not attached/permitted {gate}")
        return 1
    if not (REPO / SCHEMA_REL).is_file():
        print("FAILED:SYN-0041-probe1 schema missing")
        return 1
    print(f"items={total} counts={counts} verified={verified}")
    print("SUCCESS:SYN-0041-probe1 labels regen verified-anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: Signal B planted search + no-delete-on-zero.

Mechanically different from probe 1: never recomputes a classification
histogram. Reads does/mechanisms/notes only. Plants are labelled ADOPT-AS-IS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from adjudicate import KEEP_UNEXERCISED, KEEP_SHOULD_CARRY, may_delete  # noqa: E402
from fixtures import DECOY_ID, plant_id_for, planted_records  # noqa: E402
from search import blob, matches_rule, search_records  # noqa: E402
from sources import live_registry  # noqa: E402
from vocabulary import UNUSED_VALUES  # noqa: E402

ART = HERE.parents[3] / "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0005-probe2 {msg}")
    return 1


def main() -> int:
    plants = planted_records()
    by_id = {str(r["id"]): r for r in plants}
    hits = search_records(plants)
    missing = [v for v in UNUSED_VALUES if not hits[v]]
    if missing:
        return fail(f"planted-did-not-fire:{missing}")
    for value in UNUSED_VALUES:
        rec = by_id[plant_id_for(value)]
        if rec.get("classification") == value:
            return fail(f"plant-classified-as-target:{value}")
        if value.lower() in blob(rec) and not matches_rule(rec, value):
            return fail(f"tokens-in-blob-but-rule-miss:{value}")
        others = [h["id"] for h in hits[value] if h["id"] != rec["id"]]
        if DECOY_ID in {h["id"] for h in hits[value]}:
            return fail(f"decoy-matched:{value}")
        if others:
            # plants must not cross-fire
            return fail(f"cross-fire:{value}->{others}")

    decoy = by_id[DECOY_ID]
    decoy_hits = [v for v in UNUSED_VALUES if matches_rule(decoy, v)]
    if decoy_hits:
        return fail(f"decoy-fired:{decoy_hits}")

    blocked = may_delete(
        "TRANSLATE",
        count=0,
        written_argument=None,
        owner_visible_note=None,
    )
    if blocked["allowed"]:
        return fail("zero-count-deletion-allowed")
    if blocked["reason"] != "zero-count-is-not-deletion-grounds":
        return fail(f"wrong-block-reason:{blocked['reason']}")

    spec_block = may_delete(
        "REJECT",
        count=0,
        written_argument="I feel like deleting it",
        owner_visible_note=None,
    )
    if spec_block["allowed"]:
        return fail("spec-named-deleted-without-owner-note")

    live = live_registry()
    live_hits = search_records(live["candidates"]) if live["candidates"] else {}
    live_fired = {v: len(live_hits.get(v) or []) for v in UNUSED_VALUES}

    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:WFA-0005" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")

    adjudications = doc.get("adjudications") or []
    if len(adjudications) != 6:
        return fail(f"adjudication-count:{len(adjudications)}")
    for row in adjudications:
        if row.get("deleted") is True:
            return fail(f"deleted-without-grounds:{row.get('value')}")
        if row.get("verdict") not in {KEEP_UNEXERCISED, KEEP_SHOULD_CARRY}:
            return fail(f"bad-verdict:{row}")
        if not row.get("keep_argument"):
            return fail(f"missing-keep-argument:{row.get('value')}")
        if not row.get("planted_fired"):
            return fail(f"artifact-planted-miss:{row.get('value')}")

    vocab_deleted = doc.get("vocabulary_deletions") or []
    if vocab_deleted:
        return fail(f"deletions-emitted:{vocab_deleted}")

    report = {
        "planted_fired": {v: [h["id"] for h in hits[v]] for v in UNUSED_VALUES},
        "decoy_hits": decoy_hits,
        "zero_count_delete_allowed": blocked["allowed"],
        "spec_named_without_owner_allowed": spec_block["allowed"],
        "live_present": live["source"]["present"],
        "live_n": len(live["candidates"]),
        "live_fired": live_fired,
        "fields_used": ["does", "mechanisms", "notes"],
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:WFA-0005-probe2 planted-search-fires "
        "decoy=0 zero-count-cannot-delete"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

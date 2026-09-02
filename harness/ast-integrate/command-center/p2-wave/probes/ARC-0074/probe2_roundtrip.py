#!/usr/bin/env python3
"""Probe 2: decomposition round-trip, both-states, live recompose.

Good: union of per-source buckets equals the fusion id set.
Bad: dropping one id from a decomposed bucket makes recompose miss it.
Live WINNING-ARCHITECTURE.json is decomposed and matched to live extracts
without consulting emit's slot policy (never-authored-dossier reviewer).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import compose as C  # noqa: E402

ART = REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0074-probe2 {msg}")
    return 1


def main() -> int:
    good, good_src = C.fixture_fusion_good()
    rt = C.roundtrip(good)
    if not rt["ok"]:
        return fail(f"good-fixture roundtrip {rt}")
    unmatched = C.match_decomposed_to_sources(rt["decomposed"], good_src)
    if unmatched:
        return fail(f"good-fixture unmatched {unmatched}")

    dropped = dict(rt["decomposed"])
    sa_ids = list(dropped.get("SA") or [])
    if not sa_ids:
        return fail("good-fixture has no SA bucket to drop")
    victim = sa_ids[0]
    dropped["SA"] = [i for i in sa_ids if i != victim]
    mutated = C.recompose(dropped)
    original = set(rt["original"])
    if mutated == original:
        return fail("drop-one recompose still equal (silent)")
    if victim not in (original - mutated):
        return fail(f"dropped {victim} not reported missing")

    extra = dict(rt["decomposed"])
    extra = {k: list(v) for k, v in extra.items()}
    extra.setdefault("SA", [])
    extra["SA"] = list(extra["SA"]) + ["SA:ghost-not-extracted"]
    extra_set = C.recompose(extra)
    if extra_set == original:
        return fail("extra-id recompose still equal (silent)")
    if "SA:ghost-not-extracted" not in (extra_set - original):
        return fail("extra id not reported")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("winning architecture missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0074":
        return fail(f"unit_id {doc.get('unit_id')}")
    fusion = doc.get("mechanisms") or []
    live_rt = C.roundtrip(fusion)
    if not live_rt["ok"]:
        return fail(f"live roundtrip {live_rt}")

    live = C.load_live_dossiers()
    sources = C.source_rows_from_live(live)
    live_unmatched = C.match_decomposed_to_sources(live_rt["decomposed"], sources)
    if live_unmatched:
        return fail(f"live unmatched {live_unmatched}")

    recorded = doc.get("decomposition") or {}
    rec_ids = set(recorded.get("recomposed") or live_rt["recomposed"])
    if rec_ids != set(live_rt["original"]):
        # Artifact may store the executed decomposition; it must match live recompute.
        art_orig = set(recorded.get("original") or [])
        if art_orig and art_orig != set(live_rt["original"]):
            return fail("artifact decomposition drifted from live recompute")

    print(
        json.dumps(
            {
                "good_roundtrip": True,
                "drop_one_fires": True,
                "extra_id_fires": True,
                "live_roundtrip": True,
                "live_unmatched": 0,
                "live_count": len(live_rt["original"]),
                "decomposed_sources": sorted(live_rt["decomposed"]),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"good_roundtrip=True drop_one_fires=True extra_id_fires=True "
        f"live_count={len(live_rt['original'])} unmatched=0"
    )
    print("SUCCESS:ARC-0074-probe2 decomposition-roundtrip both-states live-recompose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

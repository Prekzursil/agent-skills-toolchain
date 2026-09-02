#!/usr/bin/env python3
"""Probe 2: UNDECIDABLE side-by-side candidates; guessing is banned."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import resolver as R  # noqa: E402
from constants import (  # noqa: E402
    CATALOG_SENTINEL,
    CLASS_MANY,
    CLASS_NONE,
    CLASS_UNDECIDABLE,
    EXPECTED_UNSETTLED,
    LIVE_SOURCE_PATHS,
    OUTPUT_REL,
    UNIT_ID,
    UNSETTLED_DOCS,
)

ART = REPO / OUTPUT_REL


def payload(doc: dict) -> dict:
    """Domain tables live in extensions on a receipt_core document."""
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        merged = dict(doc)
        merged.update(ext)
        return merged
    return doc


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if CATALOG_SENTINEL not in text:
        return fail("catalog sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    estate = C.materialize()
    hits = R.scan_tree(estate)
    undec = [h for h in hits if h["classification"] == CLASS_UNDECIDABLE]
    if not undec:
        return fail("zero UNDECIDABLE (guessed everything)")

    for h in undec:
        cands = h.get("candidates") or []
        if len(cands) < 2:
            return fail(
                f"UNDECIDABLE {h['id']} at {h['artifact']}:{h['line']} "
                "lacks two candidate meanings"
            )
        meanings = {c.get("meaning") for c in cands}
        if len(meanings) < 2:
            return fail(f"UNDECIDABLE {h['id']} candidates are not distinct")
        flags = h.get("discriminators") or {}
        if any(
            flags.get(k) for k in ("mech", "option", "harness", "mission_grade")
        ):
            return fail(
                f"UNDECIDABLE {h['id']} at {h['artifact']}:{h['line']} "
                "still carries a discriminating token (resolver under-powered)"
            )

    names = set(UNSETTLED_DOCS)
    unsettled = [h for h in undec if Path(h["artifact"]).name in names]
    if len(unsettled) != EXPECTED_UNSETTLED:
        return fail(f"unsettled docs {len(unsettled)} want {EXPECTED_UNSETTLED}")

    stored = payload(doc).get("docs_16_18_19_undecidable") or []
    if len(stored) != EXPECTED_UNSETTLED:
        return fail(f"artifact unsettled {len(stored)} want {EXPECTED_UNSETTLED}")

    synth = [h for h in undec if h["role"] == "synthetic" and h["id"] == "M-12"]
    if not synth:
        return fail("synthetic no-token M-12 not UNDECIDABLE")

    none = [
        h for h in hits if h["classification"] == CLASS_NONE and h["id"] == "M-99"
    ]
    if not none:
        return fail("planted M-99 was not RESOLVES-NONE")

    many = [
        h for h in hits if h["classification"] == CLASS_MANY and h["id"] == "M-8"
    ]
    if not many:
        return fail("planted dual-token M-8 was not RESOLVES-MANY")

    sample = unsettled[:10]
    if len(sample) < 10:
        return fail("reviewer sample short")
    for h in sample:
        flags = R.token_hits_in_window(h.get("window") or h["snippet"])
        if any(flags.values()):
            return fail(f"reviewer found discriminator on {h['id']} {h['artifact']}")

    live = (payload(doc).get("corpus") or {}).get("live_cited_inputs") or []
    source_set = {p.replace("\\", "/") for p in LIVE_SOURCE_PATHS}
    unexpected = [
        row
        for row in live
        if row.get("present")
        and str(row.get("path") or "").replace("\\", "/") in source_set
    ]
    if unexpected:
        return fail(
            "unexpected live cited source present: "
            + ",".join(str(r.get("path")) for r in unexpected)
        )

    print(
        json.dumps(
            {
                "probe": "probe2-undecidable-side-by-side",
                "unit_id": UNIT_ID,
                "undecidable": len(undec),
                "unsettled_16_18_19": len(unsettled),
                "reviewer_sample": len(sample),
                "synthetic_undecidable": True,
                "resolves_none_m99": True,
                "resolves_many_m8": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT_ID}-probe2 UNDECIDABLE side-by-side and no-guess")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

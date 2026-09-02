"""Named detector controls required by SYN-0024."""
from __future__ import annotations

from typing import Any

import audit as A
import extract as E
from paths import PIN_REFUTED_ID


def known_present() -> dict[str, Any]:
    source = E.fixture_source()
    hits = [
        r
        for r in source
        if r.id == PIN_REFUTED_ID and r.raw == "REFUTED" and r.polarity == "negative"
    ]
    found = len(hits) == 1
    return {
        "ok": found,
        "found": found,
        "id": PIN_REFUTED_ID,
        "hit_raw": hits[0].raw if hits else None,
        "source_negative_ids": [r.id for r in source if r.polarity == "negative"],
        "source_count": sum(1 for r in source if r.polarity == "negative"),
    }


def planted_drop() -> dict[str, Any]:
    source = E.fixture_source()
    synth = E.fixture_synthesis()
    base = A.survive(source, synth)
    mutant_synth = [r for r in synth if r.id != PIN_REFUTED_ID]
    mutant = A.survive(source, mutant_synth)
    base_ids = {d.id for d in base.dropped}
    mut_ids = {d.id for d in mutant.dropped}
    silent_on_full = PIN_REFUTED_ID not in base_ids
    fired_on_drop = PIN_REFUTED_ID in mut_ids
    reason = next(
        (d.reason for d in mutant.dropped if d.id == PIN_REFUTED_ID),
        "",
    )
    return {
        "ok": silent_on_full and fired_on_drop and bool(reason),
        "silent_on_full": silent_on_full,
        "fired_on_drop": fired_on_drop,
        "mutant_reason": reason,
        "base_surviving": base.surviving_count,
        "mutant_surviving": mutant.surviving_count,
        "base_dropped": sorted(base_ids),
        "mutant_dropped": sorted(mut_ids),
    }


def ratio_units() -> dict[str, Any]:
    source = E.fixture_source()
    synth = E.fixture_synthesis()
    rat = A.ratios(source, synth)
    used_records = rat.unit == "record"
    diverges = bool(rat.diverges_from_bytes)
    nonzero = rat.corpus_negative > 0 and rat.corpus_positive > 0
    return {
        "ok": used_records and diverges and nonzero and rat.byte_weighted_refused,
        "unit": rat.unit,
        "diverges_from_bytes": diverges,
        "corpus_ratio": rat.corpus_ratio,
        "byte_corpus_ratio": rat.byte_corpus_ratio,
        "synthesis_ratio": rat.synthesis_ratio,
        "ratios": rat.as_dict(),
    }


def all_controls() -> dict[str, Any]:
    parts = {
        "known_present": known_present(),
        "planted_drop": planted_drop(),
        "ratio_units": ratio_units(),
    }
    return {"ok": all(p.get("ok") for p in parts.values()), "parts": parts}

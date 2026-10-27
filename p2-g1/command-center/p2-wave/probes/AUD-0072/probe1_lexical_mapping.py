#!/usr/bin/env python3
"""Probe 1: lexical mapping of each extracted phrase onto a Sherman-Kent band or UNMAPPED.

Mechanically different from probe 2 (residue listing). Recomputes the map live;
does not trust the artifact's headline counts without a re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0072-probe1 {msg}")
    return 1


def main() -> int:
    live = E.normalize()
    planted = [
        e
        for e in live["expressions"]
        if "AUD-0072/fixtures/planted-expressions.json" in str(e.get("path") or "")
    ]
    if not planted:
        return fail("planted-corpus-absent")

    band_ok = {
        "almost-certain": False,
        "likely": False,
        "roughly-even": False,
        "unlikely": False,
        "remote": False,
    }
    should_mapped_to_likely = False
    should_seen = False
    likely_fine_mapped = False
    for e in planted:
        phrase = str(e.get("phrase") or "")
        if e.get("band") in band_ok:
            band_ok[str(e["band"])] = True
        if E.lock_key(phrase) == "should work":
            should_seen = True
            if e.get("mapped") or e.get("band") == "likely":
                should_mapped_to_likely = True
        if E.lock_key(phrase) == "likely fine" and e.get("mapped"):
            likely_fine_mapped = True

    if not should_seen:
        return fail("planted-should-work-not-extracted")
    if should_mapped_to_likely:
        return fail("should-work-mapped-to-band")
    if likely_fine_mapped:
        return fail("likely-fine-mapped")
    missing_bands = [b for b, ok in band_ok.items() if not ok]
    if missing_bands:
        return fail(f"planted-canonical-bands-unmapped:{missing_bands}")

    # Artifact, if present, must match live unique-mapped set.
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        art_mapped = {
            str(r.get("phrase"))
            for r in (doc.get("lexical_mapping") or [])
            if isinstance(r, dict) and r.get("mapped")
        }
        live_mapped = {p for p in live["unique_mapped_phrases"]}
        if art_mapped != live_mapped:
            only_art = sorted(art_mapped - live_mapped)[:8]
            only_live = sorted(live_mapped - art_mapped)[:8]
            return fail(
                f"artifact-mapping-drift art_only={only_art} live_only={only_live}"
            )

    sample = [
        {
            "phrase": e["phrase"],
            "band": e.get("band"),
            "status": e.get("status"),
            "mapped": e.get("mapped"),
            "path": e.get("path"),
        }
        for e in planted
        if e.get("mapped")
    ][:12]
    print(
        json.dumps(
            {
                "probe": "probe1-lexical-mapping",
                "mapped_count": live["mapped_count"],
                "expression_count": live["expression_count"],
                "band_counts": live["band_counts"],
                "status_counts": live["status_counts"],
                "planted_mapped_sample": sample,
                "should_work_not_assigned_likely": should_seen and not should_mapped_to_likely,
                "canonical_bands_mapped": band_ok,
            },
            sort_keys=True,
        )
    )
    print(
        f"mapped={live['mapped_count']} residue={live['residue_count']} "
        f"should_work_unmapped=True bands={band_ok}"
    )
    print("SUCCESS:AUD-0072-probe1 lexical mapping of each phrase to a band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

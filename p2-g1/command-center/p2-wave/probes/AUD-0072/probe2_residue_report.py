#!/usr/bin/env python3
"""Probe 2: unmapped-residue report.

A normalizer that maps everything has almost certainly guessed. Residue is the
honest output. Control: bare "should work" lands here, not as likely.

Mechanically different from probe 1 (which emits the phrase→band map).
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
    print(f"FAILED:AUD-0072-probe2 {msg}")
    return 1


def main() -> int:
    live = E.normalize()
    residue_phrases = [E.lock_key(p) for p in live["unique_residue_phrases"]]
    if not residue_phrases:
        return fail("empty-residue-normalizer-guessed")
    if "should work" not in residue_phrases:
        return fail("should-work-absent-from-residue")
    if "looks fine" not in residue_phrases:
        return fail("looks-fine-absent-from-residue")
    if "likely fine" not in residue_phrases:
        return fail("likely-fine-absent-from-residue")

    for e in live["expressions"]:
        if E.lock_key(e.get("phrase") or "") == "should work":
            if e.get("mapped") or e.get("band") == "likely":
                return fail("should-work-silently-assigned-likely")
            greedy = E.greedy_wrong_map(e["phrase"])
            if greedy != "likely":
                return fail("detector-control-greedy-mapper-did-not-fire")
            if E.map_band(e["phrase"]) is not None:
                return fail("locked-hedge-mapped")

    # Numeric and nonstandard bands must remain residue, not coerced.
    numeric_ok = any(
        e.get("residue_reason") == "numeric-not-a-band"
        for e in live["expressions"]
    )
    nonstandard = any(
        "high-on-this-deterministic-step" in str(e.get("phrase") or "")
        and not e.get("mapped")
        for e in live["expressions"]
    )
    if not numeric_ok:
        return fail("numeric-confidence-not-in-residue")
    if not nonstandard:
        return fail("nonstandard-band-not-in-residue")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        art_res = {
            E.lock_key(str(r.get("phrase") or ""))
            for r in (doc.get("unmapped_residue") or [])
            if isinstance(r, dict)
        }
        if "should work" not in art_res:
            return fail("artifact-residue-missing-should-work")
        live_res = {E.lock_key(p) for p in live["unique_residue_phrases"]}
        if art_res != live_res:
            only_art = sorted(art_res - live_res)[:8]
            only_live = sorted(live_res - art_res)[:8]
            return fail(
                f"artifact-residue-drift art_only={only_art} live_only={only_live}"
            )

    print(
        json.dumps(
            {
                "probe": "probe2-unmapped-residue",
                "residue_count": live["residue_count"],
                "unique_residue": live["unique_residue_phrases"],
                "should_work_in_residue": True,
                "looks_fine_in_residue": True,
                "likely_fine_in_residue": True,
                "greedy_wrong_mapper_assigns_should_work_likely": True,
                "our_mapper_refuses_that_guess": True,
                "numeric_in_residue": True,
                "nonstandard_band_in_residue": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"residue_unique={len(live['unique_residue_phrases'])} "
        f"should_work=True empty={False}"
    )
    print("SUCCESS:AUD-0072-probe2 unmapped-residue report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

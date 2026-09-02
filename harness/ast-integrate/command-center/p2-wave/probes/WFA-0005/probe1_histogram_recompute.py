#!/usr/bin/env python3
"""Probe 1: Signal A histogram from candidates[].classification.

Both-states:
  * lying counts block (TRANSLATE=99) is ignored; candidate recount stays 0
  * mutating one classification to an unused value turns that unused count 1
Independent accumulator (Counter vs loop) must agree.
Does not read Signal B search hits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import lying_counts_registry, mutate_classification  # noqa: E402
from histogram import (  # noqa: E402
    counts_block_of,
    disagreement,
    recompute_from_candidates,
    tally_loop,
    unused_counts,
)
from sources import live_registry  # noqa: E402
from vocabulary import UNUSED_VALUES, VOCABULARY_15  # noqa: E402

ART = HERE.parents[3] / "command-center/wfa/WFA-0005-classification-vocabulary-audit.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0005-probe1 {msg}")
    return 1


def main() -> int:
    if len(VOCABULARY_15) != 15:
        return fail(f"vocabulary-len:{len(VOCABULARY_15)}")
    if len(UNUSED_VALUES) != 6:
        return fail(f"unused-len:{len(UNUSED_VALUES)}")

    fixture = lying_counts_registry()
    cands = fixture["candidates"]
    recomputed = recompute_from_candidates(cands)
    looped = tally_loop(cands)
    if recomputed != looped:
        return fail(f"counter-vs-loop {recomputed} {looped}")
    block = counts_block_of(fixture)
    diffs = disagreement(recomputed, block)
    unused = unused_counts(recomputed, UNUSED_VALUES)
    if unused.get("TRANSLATE") != 0:
        return fail(f"fixture-translate-not-zero {unused}")
    if not any(d["value"] == "TRANSLATE" for d in diffs):
        return fail("lying-counts-block-not-detected")
    if recomputed.get("TRANSLATE"):
        return fail("trusted-counts-block")

    mutated = mutate_classification(cands, cands[0]["id"], "TRANSLATE")
    after = recompute_from_candidates(mutated)
    if after.get("TRANSLATE") != 1:
        return fail(f"mutation-did-not-move-histogram {after}")
    if unused_counts(after, UNUSED_VALUES)["TRANSLATE"] != 1:
        return fail("unused-counts-missed-mutation")
    if recompute_from_candidates(cands).get("TRANSLATE"):
        return fail("mutation-leaked-into-original")

    live = live_registry()
    live_hist = recompute_from_candidates(live["candidates"])
    live_unused = unused_counts(live_hist, UNUSED_VALUES) if live["candidates"] else None

    if ART.is_file():
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
        art_a = doc.get("signal_a") or {}
        art_re = art_a.get("recomputed_from_candidates")
        if live["source"]["present"]:
            if art_re != live_hist:
                return fail("artifact-histogram-drift")
        else:
            if art_a.get("live_rows_loaded") not in (0, None):
                return fail("artifact-claimed-live-rows-without-registry")

    report = {
        "vocabulary_n": len(VOCABULARY_15),
        "fixture_n": len(cands),
        "fixture_recomputed": recomputed,
        "counts_block": block,
        "disagreement_n": len(diffs),
        "unused_before": unused,
        "unused_after_translate_mutation": unused_counts(after, UNUSED_VALUES),
        "live_present": live["source"]["present"],
        "live_n": len(live["candidates"]),
        "live_unused": live_unused,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:WFA-0005-probe1 histogram-from-candidates "
        f"lying-block-diffs={len(diffs)} mutate-TRANSLATE=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 1: same-seed replay identity + stage-localized divergence.

Recomputes replay from fixtures (does not trust the artifact's claimed numbers).
A planted vote flip must name stage 'vote', not a whole-run mismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0086-council-replay.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0086"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0086-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if SENTINEL_PREFIX not in blob:
        return fail("sentinel absent")
    if doc.get("unit_id") != "CNF-0086":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    t_maj = R.load_transcript("majority.json")
    t_tied = R.load_transcript("tied.json")
    maj = R.replay(t_maj, 42)
    tied = R.replay(t_tied, 7)
    maj_orig = R.recorded_original(t_maj)
    tied_orig = R.recorded_original(t_tied)
    c_maj = R.compare(maj_orig, R.public_decision(maj))
    c_tied = R.compare(tied_orig, R.public_decision(tied))
    print(
        json.dumps(
            {
                "majority": {
                    "recommendation": maj["recommendation"],
                    "tally": maj["tally"],
                    "recommendation_identical": c_maj["recommendation_identical"],
                    "tally_identical": c_maj["tally_identical"],
                    "first_divergent_stage": c_maj["first_divergent_stage"],
                },
                "tied": {
                    "recommendation": tied["recommendation"],
                    "tally": tied["tally"],
                    "recommendation_identical": c_tied["recommendation_identical"],
                    "tally_identical": c_tied["tally_identical"],
                    "first_divergent_stage": c_tied["first_divergent_stage"],
                },
            },
            sort_keys=True,
        )
    )
    if not c_maj["recommendation_identical"] or not c_maj["tally_identical"]:
        return fail("majority identity broken")
    if c_maj["first_divergent_stage"] is not None:
        return fail("majority should have no divergent stage")
    if not c_tied["recommendation_identical"] or not c_tied["tally_identical"]:
        return fail("tied identity broken")
    if c_maj["whole_run_mismatch_without_stage"] or c_tied["whole_run_mismatch_without_stage"]:
        return fail("whole-run mismatch without a stage")

    loc = R.planted_stage_divergence(t_maj, "vote")
    print(
        f"planted_stage={loc['planted_stage']} reported={loc['reported_stage']} "
        f"not_whole_run_only={loc['not_whole_run_only']}"
    )
    if loc["reported_stage"] != "vote":
        return fail(f"divergence not localized to vote: {loc['reported_stage']}")
    if not loc["not_whole_run_only"]:
        return fail("divergence reported as whole-run only")

    runs = {r["run_id"]: r for r in doc.get("runs") or [] if isinstance(r, dict)}
    art_maj = runs.get("cnf-0086-majority") or {}
    if art_maj.get("replayed_decision", {}).get("outcome_sha256") != maj["outcome_sha256"]:
        return fail("artifact majority outcome_sha256 != live replay")
    if art_maj.get("first_divergent_stage") is not None:
        return fail("artifact majority first_divergent_stage not null")
    loc_art = doc.get("stage_localization") or {}
    if loc_art.get("reported_stage") != "vote" or loc_art.get("not_whole_run_only") is not True:
        return fail("artifact stage_localization mismatch")

    print("SUCCESS:CNF-0086-probe1 replay identity and stage localization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

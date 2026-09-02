#!/usr/bin/env python3
"""Probe 2: schema discrimination, decoy contrast, independent both-states re-run.

The real detector must FIRE on independently-GENERATED shared-source briefs
(ADV-0135 #4) while a generation-independence decoy is SILENT, and must stay
SILENT on genuine convergence while a vote-agreement decoy FIREs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402
import spec_view as SV  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0086-echo-chamber-measuring-independence-loss.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"

GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0086-probe2 {msg}")
    return 1


def main() -> int:
    planted = F.planted_bad_shared_source()
    good = F.known_good_genuine_convergence()
    seq = F.planted_bad_sequential()
    real_bad = D.detect(planted)
    real_good = D.detect(good)
    real_seq = D.detect(seq)
    gen = D.decoy_generation_independence(planted)
    vote = D.decoy_vote_agreement(good)

    print(
        f"real_shared_source fired={real_bad['fired']} "
        f"s1={real_bad.get('s1_shared_retrieval')} "
        f"s2={real_bad.get('s2_sequential_copy')} "
        f"gen_decoy_fired={gen['fired']}"
    )
    print(
        f"real_known_good fired={real_good['fired']} vote_decoy_fired={vote['fired']}"
    )
    print(
        f"real_sequential fired={real_seq['fired']} "
        f"s1={real_seq.get('s1_shared_retrieval')} "
        f"s2={real_seq.get('s2_sequential_copy')}"
    )

    if not real_bad["fired"] or gen["fired"]:
        return fail("shared-source: real must FIRE, generation decoy must be SILENT")
    if real_good["fired"] or not vote["fired"]:
        return fail("known-good: real must be SILENT, vote decoy must FIRE")
    if (
        not real_seq["fired"]
        or real_seq.get("s1_shared_retrieval")
        or not real_seq.get("s2_sequential_copy")
    ):
        return fail("sequential must be S2-only FIRE")
    if not real_bad.get("s1_shared_retrieval") or real_bad.get("s2_sequential_copy"):
        return fail("shared-source must be S1-only FIRE (no later turns)")

    if not SCHEMA.is_file():
        return fail("schema missing")
    rejected = 0
    for g in GARBAGE:
        errs = SV.schema_errors(g)
        print(f"garbage_rejected={bool(errs)} n_err={len(errs)}")
        if errs:
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage ({rejected}/3 rejected)")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0086" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    errs = SV.schema_errors(doc)
    if errs:
        print("schema_errors=" + "; ".join(errs[:8]))
        return fail("artifact schema-invalid")
    print("schema_valid=True")

    spec = SV.detector_spec(doc)
    impl = str(spec.get("detector_implementation") or "")
    if not impl or not (REPO / impl).is_file():
        return fail(f"detector_implementation missing on disk: {impl}")

    bs = spec.get("both_states") or {}
    if bs.get("planted_bad", {}).get("fired") is not True:
        return fail("artifact planted_bad.fired")
    if bs.get("known_good", {}).get("fired") is not False:
        return fail("artifact known_good.fired")

    rev = R.review()
    print(
        f"reviewer_verdict={rev['verdict']} "
        f"executed_both_states={rev['executed_both_states']} "
        f"independent={rev['independent']}"
    )
    if rev["verdict"] != "PASS" or not rev["executed_both_states"]:
        return fail("reviewer did not re-run both-states to PASS")
    exec_ok = (spec.get("reviewer_execution") or {}).get("executed_both_states")
    if exec_ok is not True:
        return fail("artifact reviewer.executed_both_states")

    print("SUCCESS:CNL-0086-probe2 schema-decoy S1/S2 split reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1: planted competency hole, named gap, recruitment efficacy.

Also drives the rubberstamp negative control: a recruited seat that only
concurs must be classified cosmetic-recruitment, not counted as efficacy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import cosmetic_verdict, hole_verdict, synonym_verdict  # noqa: E402
from fixtures import UNIQUE_CLAIM_ID, UNIQUE_CLAIM_TEXT  # noqa: E402
from simulate import hole_run, synonym_run  # noqa: E402

ART = REPO / "command-center/receipts/TST-0277.json"
UNIT = "TST-0277"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:TST-0277" not in blob:
        return fail("sentinel absent")

    live = hole_run(recruited_mode="substantive")
    verdict = hole_verdict(live)
    if not verdict["pass"] or not live.get("completed"):
        return fail("live hole run", verdict)

    rubber = hole_run(recruited_mode="rubberstamp")
    cosmetic = cosmetic_verdict(rubber)
    if not cosmetic["pass"]:
        return fail("rubberstamp cosmetic control silent", cosmetic)

    syn = synonym_run()
    syn_v = synonym_verdict(syn)
    if not syn_v["pass"]:
        return fail("synonym panel treated as covered", syn_v)

    runs = {r.get("id"): r for r in (doc.get("runs") or []) if isinstance(r, dict)}
    art_hole = runs.get("competency-hole")
    if not art_hole or not art_hole.get("completed"):
        return fail("artifact competency-hole run missing")
    if art_hole.get("transcript") != live["transcript"]:
        return fail("artifact transcript != live hole re-run")
    if UNIQUE_CLAIM_TEXT not in art_hole["transcript"]:
        return fail("artifact lost exclusive claim text")
    if art_hole.get("uncovered_competency") != "cryptography":
        return fail("artifact did not name cryptography", art_hole.get("uncovered_competency"))
    if art_hole.get("recruitment_trigger") != "missing-expertise":
        return fail("artifact trigger", art_hole.get("recruitment_trigger"))
    if art_hole.get("exclusive_claim_id") != UNIQUE_CLAIM_ID:
        return fail("artifact exclusive_claim_id", art_hole.get("exclusive_claim_id"))

    named = doc.get("named_evidence") or {}
    if named.get("uncovered_competency") != "cryptography":
        return fail("named_evidence uncovered_competency")
    if named.get("recruitment_trigger") != "missing-expertise":
        return fail("named_evidence trigger")
    if named.get("exclusive_claim_id") != UNIQUE_CLAIM_ID:
        return fail("named_evidence exclusive_claim_id")
    if named.get("exclusive_claim_author") != "recruited-crypto-critic":
        return fail("named_evidence author")

    out = {
        "probe": "probe1-competency-hole",
        "unit_id": UNIT,
        "pass": True,
        "uncovered_competency": "cryptography",
        "named_gap": verdict["named_gap"],
        "recruitment_trigger": "missing-expertise",
        "exclusive_claim_id": UNIQUE_CLAIM_ID,
        "exclusive_claim_author": "recruited-crypto-critic",
        "exclusive_claim_in_transcript": True,
        "rubberstamp_classified_cosmetic": True,
        "synonym_panel_still_uncovered": True,
        "artifact_matches_live": True,
    }
    (HERE / "probe1-competency-hole.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0277-probe1 competency hole named and recruitment efficacious")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

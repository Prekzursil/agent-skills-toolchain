#!/usr/bin/env python3
"""Probe 2: volume-vs-substance census on 20 recorded councils + manual read.

Independent of probe 1. Recomputes both measures, publishes the disagreement
count, and reads the top-disagreement transcript to decide which measure
matched the actual contribution.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.antifail.participation import (  # noqa: E402
    analyze_council,
    analyze_many,
    excerpts_for,
    is_filler_sentence,
    split_sentences,
    substance_units,
)
from corpus import dump_recorded, load_recorded  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0321.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0321-probe2 {msg}")
    return 1


def _claim_count(text: str) -> int:
    return sum(1 for s in split_sentences(text) if not is_filler_sentence(s) and substance_units(s) > 0)


def manual_read(council: dict, analysis: dict) -> dict:
    vol = analysis["disagreement"]["volume_loudest"]
    sub = analysis["disagreement"]["substance_loudest"]
    seats = [s for s in (vol, sub) if s]
    texts = excerpts_for(council, seats, limit=4)
    vol_text = " ".join(texts.get(vol or "", []))
    sub_text = " ".join(texts.get(sub or "", []))
    vol_filler = sum(1 for s in split_sentences(vol_text) if is_filler_sentence(s))
    vol_claim = _claim_count(vol_text)
    sub_claim = _claim_count(sub_text)
    # Substance is right when the volume-loudest seat's extra tokens are filler
    # and the substance-loudest seat actually carries claims/evidence.
    substance_right = bool(
        vol
        and sub
        and vol != sub
        and vol_claim < sub_claim
        and vol_filler >= 3
    )
    return {
        "council_id": analysis["council_id"],
        "volume_loudest": vol,
        "substance_loudest": sub,
        "volume_loudest_filler_sentences": vol_filler,
        "volume_loudest_claim_sentences": vol_claim,
        "substance_loudest_claim_sentences": sub_claim,
        "volume_share_of_volume_loudest": analysis["seats"][vol]["volume_share"] if vol else None,
        "substance_share_of_volume_loudest": analysis["seats"][vol]["substance_share"] if vol else None,
        "substance_share_of_substance_loudest": analysis["seats"][sub]["substance_share"] if sub else None,
        "excerpts": {k: v[:2] for k, v in texts.items()},
        "which_measure_was_right": "substance" if substance_right else "unresolved",
        "rationale": (
            "The volume-loudest seat's sampled turns are mostly filler acknowledgements "
            "with fewer claim-bearing sentences than the substance-loudest seat. "
            "Token volume over-credits padding; substance matches the read."
            if substance_right
            else "Could not confirm from excerpts that filler explains the gap."
        ),
    }


def main() -> int:
    dump_recorded()
    councils = load_recorded()
    if len(councils) != 20:
        return _fail(f"corpus size {len(councils)}")
    census = analyze_many(councils)
    if census["n_councils"] != 20:
        return _fail(f"n_councils {census['n_councils']}")
    if census["n_disagreements"] < 1:
        return _fail("zero disagreements; falsifiable question unanswered")

    rec01 = next(c for c in councils if c["council_id"] == "rec-01")
    even = analyze_council(rec01)
    if even["flagged_volume"] or even["flagged_substance"]:
        return _fail("recorded even council rec-01 flagged")

    top = census["top_disagreement"]
    if top is None:
        return _fail("top_disagreement missing")
    top_council = next(c for c in councils if c["council_id"] == top["council_id"])
    top_analysis = next(r for r in census["rows"] if r["council_id"] == top["council_id"])
    read = manual_read(top_council, top_analysis)
    if read["which_measure_was_right"] != "substance":
        return _fail(f"manual read unresolved {json.dumps(read, sort_keys=True)[:800]}")
    if top["volume_loudest"] == top["substance_loudest"]:
        return _fail("top disagreement loudest seats identical")

    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        published = None
        for block in doc.get("evidence") or []:
            if isinstance(block, dict) and "disagreement_count" in block:
                published = block["disagreement_count"]
        if published is None:
            published = (doc.get("evidence_requirement_records") or {}).get(
                "disagreement_count"
            )
        if published is not None and int(published) != census["n_disagreements"]:
            return _fail(
                f"receipt overclaim disagreement_count={published} live={census['n_disagreements']}"
            )

    table = []
    for row in census["rows"]:
        table.append(
            {
                "council_id": row["council_id"],
                "label": row["label"],
                "measures_disagree": row["measures_disagree"],
                "volume_loudest": row["disagreement"]["volume_loudest"],
                "substance_loudest": row["disagreement"]["substance_loudest"],
                "volume_dominant": row["volume_dominant"],
                "substance_dominant": row["substance_dominant"],
                "volume_silent": row["volume_silent"],
                "substance_silent": row["substance_silent"],
                "even": row["even"],
            }
        )
    summary = {
        "pass": True,
        "probe": "probe2-volume-vs-substance",
        "n_councils": 20,
        "disagreement_count": census["n_disagreements"],
        "disagreement_ids": census["disagreement_ids"],
        "even_rec01_unflagged": True,
        "top_disagreement": {
            "council_id": top["council_id"],
            "gap": top["gap"],
            "volume_loudest": top["volume_loudest"],
            "substance_loudest": top["substance_loudest"],
        },
        "manual_read": read,
        "table": table,
        "unit_id": "IMP-0321",
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    print(
        f"disagreement_count={census['n_disagreements']} "
        f"top={top['council_id']} volume_loudest={top['volume_loudest']} "
        f"substance_loudest={top['substance_loudest']} "
        f"manual={read['which_measure_was_right']}"
    )
    print("SUCCESS:IMP-0321-probe2 volume-vs-substance disagreement published; even council unflagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

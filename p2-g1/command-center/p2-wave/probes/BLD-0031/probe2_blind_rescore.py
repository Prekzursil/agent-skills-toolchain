#!/usr/bin/env python3
"""Probe 2: independent modality rescore of twenty sampled claims.

Reviewer requirement: re-score twenty sampled claims blind and agree
within two on the flagged count. Lexicon labels in the fixture file are
stripped before scoring; the modality scorer never reads them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

SAMPLE = HERE / "fixtures" / "sample20.md"
RECEIPT = REPO / "command-center" / "receipts" / "BLD-0031.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0031-probe2 {msg}")
    return 1


def main() -> int:
    rows = A.load_sample20(SAMPLE)
    if len(rows) != 20:
        return fail(f"sample20 count={len(rows)} want 20")

    lexicon_flagged = 0
    modality_flagged = 0
    paired = []
    for row in rows:
        text = row["text"]
        lex = A.classify_lexicon(text)
        mod = A.classify_modality(text)
        lf = A.flagged(lex)
        mf = A.flagged(mod)
        lexicon_flagged += int(lf)
        modality_flagged += int(mf)
        paired.append(
            {
                "id": row["id"],
                "lexicon": lex["class"],
                "modality": mod["class"],
                "lexicon_flagged": lf,
                "modality_flagged": mf,
            }
        )

    delta = abs(lexicon_flagged - modality_flagged)
    print(
        json.dumps(
            {
                "sampled_n": 20,
                "lexicon_flagged": lexicon_flagged,
                "modality_flagged": modality_flagged,
                "abs_delta": delta,
                "must_agree_within": 2,
                "pairs": paired,
            },
            indent=2,
        )
    )
    if delta > 2:
        return fail(f"flagged-count delta {delta} exceeds 2")

    if not RECEIPT.is_file():
        return fail("receipt absent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def rget(d: dict, key: str, default=None):
        """Reviewer-fact reader, profile-legal transport (2026-10-26 envelope
        repair): the fact is read from the reviewer object itself, or from its
        verbatim copy in extensions.reviewer_extra_fields. platform/schema/
        receipt.schema.json forbids extra keys under reviewer
        (additionalProperties: false), so sampled_n moved there verbatim.
        Check semantics unchanged: the blind rescore below still must run live
        and the receipt still must record the fact and the PASS closure."""
        rev_ = d.get("reviewer") or {}
        if key in rev_:
            return rev_.get(key)
        return (d.get("extensions") or {}).get("reviewer_extra_fields", {}).get(
            key, default
        )

    if rget(doc, "independent") is not True:
        return fail("reviewer.independent is not true")
    if int(rget(doc, "sampled_n") or 0) != 20:
        return fail("reviewer.sampled_n is not 20")
    if str(rget(doc, "verdict") or "").upper() != "PASS":
        return fail("reviewer.verdict is not PASS")

    print(
        f"sampled=20 lexicon_flagged={lexicon_flagged} "
        f"modality_flagged={modality_flagged} delta={delta} agree_within_two=True"
    )
    print("SUCCESS:BLD-0031-probe2 modality blind rescore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

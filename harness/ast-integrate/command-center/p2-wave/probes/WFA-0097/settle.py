"""Named settling experiments for undetectable duplicate classes."""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import methods as M  # noqa: E402

CIPHER = "ciphertext-opaque-payload"
ISOMORPH = "behavioral-isomorph-divergent-ir"
XLANG = "cross-language-divergent-ir"


def settle_ciphertext() -> dict:
    recs = C.records()
    seed, cipher = recs["seed"], recs[CIPHER]
    before = M.compare(seed, cipher)
    raw = base64.b64decode(cipher["payload_b64"]).decode("utf-8")
    decoded = {
        "id": "wf-cipher-decoded",
        "name": seed["name"],
        "does": raw,
        "mechanisms": list(seed["mechanisms"]),
        "ir": dict(seed["ir"]),
    }
    after = M.compare(seed, decoded)
    return {
        "class_id": CIPHER,
        "before_combined_hit": before["combined_hit"],
        "before_lexical_hit": before["lexical-jaccard"]["hit"],
        "after_decode_lexical_hit": after["lexical-jaccard"]["hit"],
        "after_decode_combined_hit": after["combined_hit"],
        "after_decode_lexical_score": after["lexical-jaccard"]["score"],
        "settled": (not before["combined_hit"]) and after["lexical-jaccard"]["hit"],
    }


def settle_isomorph() -> dict:
    recs = C.records()
    cmp = M.compare(recs["seed"], recs[ISOMORPH])
    return {
        "class_id": ISOMORPH,
        "combined_hit": cmp["combined_hit"],
        "trace_oracle_implemented": False,
        "would_settle_by": (
            "execute both records on a shared fixture suite and compare "
            "canonical traces; a match would confirm a behavioral duplicate "
            "this stack cannot see"
        ),
        "note": (
            "This tree has no shared runtime fixture suite for these two IRs; "
            "the experiment is named, not executed. Combined detectors miss, "
            "which is the measured hole."
        ),
        "miss_confirmed": not cmp["combined_hit"],
    }


def settle_cross_language() -> dict:
    recs = C.records()
    cmp = M.compare(recs["seed"], recs[XLANG])
    return {
        "class_id": XLANG,
        "combined_hit": cmp["combined_hit"],
        "translator_implemented": False,
        "would_settle_by": (
            "round-trip translate into a pivot language or apply a multilingual "
            "encoder, then re-run lexical+embedding"
        ),
        "note": (
            "No translator or multilingual encoder is wired into this stack; "
            "the experiment is named, not executed. Combined detectors miss."
        ),
        "miss_confirmed": not cmp["combined_hit"],
    }


HANDLERS = {
    CIPHER: settle_ciphertext,
    ISOMORPH: settle_isomorph,
    XLANG: settle_cross_language,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--class", dest="cls", required=True, choices=sorted(HANDLERS))
    args = parser.parse_args()
    doc = HANDLERS[args.cls]()
    print(json.dumps(doc, sort_keys=True))
    if args.cls == CIPHER:
        return 0 if doc.get("settled") else 1
    return 0 if doc.get("miss_confirmed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: dispositions are drawn from the spec's closed 15-value vocabulary.

Checks membership and closed-world refusal. A truncated ADOPT token, a
marketing synonym, and a 16th invented value must all be rejected. Every
disposition the live stage emits on the planted fixtures must be one of the 15.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCOUT = REPO / "command-center" / "foundry" / "scout"
sys.path.insert(0, str(SCOUT))

from licence_stage import verify_candidates  # noqa: E402
from vocabulary import (  # noqa: E402
    ClosedVocabularyError,
    DISPOSITION_VOCABULARY,
    FORBIDDEN_ALIASES,
    assert_disposition,
    vocabulary_size,
)

FIX = HERE / "fixtures" / "twins.json"

# The 9 used + 6 unused named by WFA-0005 in the catalog. Must equal the module.
CATALOG_USED = frozenset(
    {
        "ADOPT-AS-IS",
        "ADOPT-WITH-WRAPPER",
        "DISTILL",
        "EXTEND",
        "MERGE",
        "REPAIR",
        "RETIRE",
        "SPECIALIZE",
        "UNKNOWN-NEEDS-PROBE",
    }
)
CATALOG_UNUSED = frozenset(
    {
        "CLEAN-ROOM-REIMPLEMENT",
        "COMPOSE",
        "GENERALIZE",
        "REBUILD-FROM-SPEC",
        "REJECT",
        "TRANSLATE",
    }
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0210-probe2 {msg}")
    return 1


def main() -> int:
    if vocabulary_size() != 15 or len(DISPOSITION_VOCABULARY) != 15:
        return fail(f"vocabulary_size={vocabulary_size()} want 15")
    if len(set(DISPOSITION_VOCABULARY)) != 15:
        return fail("vocabulary has duplicates")
    live = set(DISPOSITION_VOCABULARY)
    if live != CATALOG_USED | CATALOG_UNUSED:
        missing = (CATALOG_USED | CATALOG_UNUSED) - live
        extra = live - (CATALOG_USED | CATALOG_UNUSED)
        return fail(f"vocab mismatch missing={sorted(missing)} extra={sorted(extra)}")
    if CATALOG_USED & CATALOG_UNUSED:
        return fail("used/unused partition overlap")

    for token in DISPOSITION_VOCABULARY:
        if assert_disposition(token) != token:
            return fail(f"assert_disposition dropped {token}")

    refused = []
    for bad in sorted(FORBIDDEN_ALIASES | {"PERMISSIVE-OK", "ADOPT", "OK", "CUSTOM-16"}):
        try:
            assert_disposition(bad)
        except ClosedVocabularyError:
            refused.append(bad)
            continue
        return fail(f"out-of-vocab {bad!r} was accepted")
    if "ADOPT" not in refused:
        return fail("truncated ADOPT was not refused")

    doc = json.loads(FIX.read_text(encoding="utf-8"))
    batch = [
        doc["twins"]["unlicensed_permissive_blurb"],
        doc["twins"]["licensed_mit"],
        doc["extra"]["gpl_into_permissive_target"],
        doc["extra"]["marketing_only_permissive_word"],
        doc["extra"]["mit_with_no_ml_rider"],
    ]
    report = verify_candidates(batch, target_spdx=doc["target_spdx"])
    emitted = {h["disposition"] for h in report["hits"]}
    if not emitted <= set(DISPOSITION_VOCABULARY):
        return fail(f"stage emitted out-of-vocab {emitted - set(DISPOSITION_VOCABULARY)}")
    if "CLEAN-ROOM-REIMPLEMENT" not in emitted or "ADOPT-AS-IS" not in emitted:
        return fail(f"stage did not exercise both required tokens: {emitted}")

    out = {
        "probe": "probe2-vocabulary",
        "unit_id": "IMP-0210",
        "vocabulary_size": vocabulary_size(),
        "vocabulary": list(DISPOSITION_VOCABULARY),
        "refused_aliases": refused,
        "emitted": sorted(emitted),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "vocab=15 refused_aliases="
        + str(len(refused))
        + " emitted="
        + ",".join(sorted(emitted))
    )
    print("SUCCESS:IMP-0210-probe2 closed 15-value disposition vocabulary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

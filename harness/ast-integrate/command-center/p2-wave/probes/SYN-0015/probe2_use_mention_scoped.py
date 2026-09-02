#!/usr/bin/env python3
"""Probe 2: independent reviewer — use-vs-mention and already-scoped both-states.

Does not read probe 1's verdict. Re-derives from fixtures and the artifact on
disk. A quoted plant must be silent; the same plant unmasked must fire (the
mention mask is load-bearing). A sentence already scoped to 12 of 103 must
not fire. Bound schema must reject a flagged sentence with an empty rewrite.
Catalog output_schema is also required (disk-resolved $ref, no network).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0015.json"
SENTINEL = "SUCCESS:SYN-0015"


def _empty_rewrite_mutant(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    rows = None
    if isinstance(mutant.get("report"), dict):
        cand = mutant["report"].get("flagged_sentences")
        if isinstance(cand, list) and cand:
            rows = cand
    if rows is None:
        cand = mutant.get("flagged_sentences")
        if isinstance(cand, list) and cand:
            rows = cand
    if not rows or not isinstance(rows[0], dict):
        raise SystemExit("FAILED:SYN-0015-probe2 mutant has no flagged_sentences")
    rows[0]["corrected_sentence"] = ""
    return mutant


def main() -> int:
    qm = C.quoted_mention()
    sc = C.already_scoped()
    print(
        json.dumps(
            {
                "quoted_ok": qm["ok"],
                "masked_flags": qm["masked_flags"],
                "masked_plant_hits": qm["masked_plant_hits"],
                "unmasked_plant_hits": qm["unmasked_plant_hits"],
                "mention_mask_is_load_bearing": qm["mention_mask_is_load_bearing"],
                "scoped_ok": sc["ok"],
                "scoped_overclaims": sc["overclaim_count"],
                "scoped_kinds": sc["kinds"],
            },
            sort_keys=True,
        )
    )
    if not qm["ok"]:
        print("FAILED:SYN-0015-probe2 quoted mention leaked or mask not load-bearing")
        return 1
    if not sc["ok"]:
        print("FAILED:SYN-0015-probe2 already-scoped sentence fired or was not classified")
        return 1

    if not ART.is_file():
        print("FAILED:SYN-0015-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:SYN-0015-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    honest, why = C.artifact_honesty(doc)
    print(f"artifact_honesty={honest} {why}")
    if not honest:
        print("FAILED:SYN-0015-probe2 artifact honesty")
        return 1

    payload = C.domain(doc)
    live = payload.get("live_corpus") or {}
    verdict = str(payload.get("verdict") or doc.get("verdict") or "")
    if int(live.get("files_scanned") or 0) == 0 and verdict == "CONFIRMED":
        print("FAILED:SYN-0015-probe2 live empty claimed CONFIRMED")
        return 1

    catalog_errs = SL.catalog_errors(doc)
    if catalog_errs:
        print(f"FAILED:SYN-0015-probe2 catalog-schema {catalog_errs[0]}")
        return 1
    bound_errs = SL.bound_errors(doc)
    if bound_errs:
        print(f"FAILED:SYN-0015-probe2 bound-schema {bound_errs[0]}")
        return 1

    mutant = _empty_rewrite_mutant(doc)
    mutant_errors = SL.bound_errors(mutant)
    if not mutant_errors:
        print("FAILED:SYN-0015-probe2 schema accepted empty rewrite")
        return 1
    print(f"schema_empty_rewrite_rejected={len(mutant_errors)}")

    garbage = {"unit_id": "SYN-0015", "state": "SUCCESS"}
    garbage_errors = SL.bound_errors(garbage) + SL.catalog_errors(garbage)
    if not garbage_errors:
        print("FAILED:SYN-0015-probe2 schema accepted garbage")
        return 1
    print(f"schema_garbage_rejected={len(garbage_errors)}")

    reviewers = payload.get("reviewers") or doc.get("reviewers") or []
    if len(reviewers) < 2:
        print("FAILED:SYN-0015-probe2 two independent reviewers not filed")
        return 1
    if any(r.get("saw_other_verdict_before_filing") is not False for r in reviewers):
        print("FAILED:SYN-0015-probe2 reviewer saw the other verdict first")
        return 1
    if any(r.get("independent") is not True for r in reviewers):
        print("FAILED:SYN-0015-probe2 reviewer not independent")
        return 1

    print("SUCCESS:SYN-0015-probe2 use-vs-mention already-scoped schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

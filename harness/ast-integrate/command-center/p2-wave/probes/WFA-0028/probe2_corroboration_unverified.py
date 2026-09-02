#!/usr/bin/env python3
"""Probe 2: corroboration is independent; niche-only claims stay UNVERIFIED.

Signal A: token search over the mainstream index (different URL than the niche
source). Signal B: stripping that index must flip a previously corroborated
finding to UNVERIFIED. A proposal-only archival claim must not promote.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import catalog as C  # noqa: E402
import sweep as S  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0028-sweep-niche-archival.json"
LOOP_ID = "create-execute-prioritize-loop"
PROPOSAL_ID = "parallel-task-execution-proposal"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0028-probe2 {msg}")
    return 1


def by_id(report: dict, mid: str) -> dict | None:
    for row in report.get("findings") or []:
        if row.get("mechanism_id") == mid:
            return row
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0028" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail("self-declared-blocked")

    full = S.run()
    loop = by_id(full, LOOP_ID)
    prop = by_id(full, PROPOSAL_ID)
    if loop is None:
        return fail("loop-finding-missing")
    if loop["grade"] != "CORROBORATED":
        return fail(f"loop-not-corroborated {loop['grade']}")
    if loop["source"]["url"] in {h["url"] for h in loop["evidence_b"]["hits"]}:
        return fail("corroboration-used-same-url")
    if prop is None:
        return fail("proposal-finding-missing")
    if prop["grade"] != "UNVERIFIED":
        return fail(f"proposal-promoted {prop['grade']}")
    promo = S.promote(prop)
    if promo["promoted"]:
        return fail("proposal-promote-true")

    stripped = S.run(mainstream=[])
    loop_stripped = by_id(stripped, LOOP_ID)
    if loop_stripped is None or loop_stripped["grade"] != "UNVERIFIED":
        return fail("stripped-index-did-not-unverify")
    if S.promote(loop_stripped)["promoted"]:
        return fail("unverified-loop-promoted")

    planted = copy.deepcopy(C.MAINSTREAM)
    planted.append(
        {
            "id": "ms-planted-parallel",
            "surface": "planted-control",
            "url": "https://example.invalid/planted-parallel",
            "retrieved_at": "2026-08-24T00:00:00Z",
            "text": (
                "running parallel tasks and task serialization as shipped features"
            ),
        }
    )
    planted_run = S.run(mainstream=planted)
    planted_prop = by_id(planted_run, PROPOSAL_ID)
    if planted_prop is None or planted_prop["grade"] != "CORROBORATED":
        return fail("planted-mainstream-did-not-hit-proposal")
    restored = S.run(mainstream=C.MAINSTREAM)
    restored_prop = by_id(restored, PROPOSAL_ID)
    if restored_prop is None or restored_prop["grade"] != "UNVERIFIED":
        return fail("restored-index-still-corroborated-proposal")

    art_rows = list(doc.get("unverified") or []) + [
        r
        for r in (doc.get("findings") or [])
        if r.get("grade") == "UNVERIFIED"
    ]
    if not any(r.get("mechanism_id") == PROPOSAL_ID for r in art_rows):
        return fail("artifact-missing-unverified-proposal")

    for row in full["corroborated"]:
        a = row["evidence_a"]
        if not a.get("original_quote") or not a.get("translation"):
            return fail(f"missing-quote-or-translation {row['mechanism_id']}")
        if not row["source"].get("retrieved_at") and not row["source"].get(
            "archive_timestamp"
        ):
            return fail(f"missing-timestamp {row['mechanism_id']}")

    if not full["legal_review"].get("consume_allowed"):
        return fail("legal-review-forbids-consume-on-clean-run")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-corroboration-unverified",
                "unit_id": "WFA-0028",
                "loop_corroborated": True,
                "proposal_unverified": True,
                "stripped_index_unverified": True,
                "planted_then_restored": True,
                "promotion_refused_for_unverified": True,
                "n_corroborated": full["counts"]["corroborated"],
                "n_unverified": full["counts"]["unverified"],
            }
        )
    )
    print("SUCCESS:WFA-0028-probe2 independent corroboration and UNVERIFIED hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

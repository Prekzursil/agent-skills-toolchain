#!/usr/bin/env python3
"""Probe 2: human vs LLM evidence rails stay disjoint.

Both-states: the live record must pass; swapping a human paper onto the LLM
rail or merging reviewer paper_ids must fail the same checker.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    ARTIFACT,
    UNIT,
    check_record,
    load_artifact,
    mutant_merge_reviewers,
    mutant_swap_species,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ARTIFACT.is_file():
        return fail(f"artifact missing {ARTIFACT}")
    doc = load_artifact()
    errs = check_record(doc)
    if errs:
        return fail("live record: " + "; ".join(errs[:8]))

    human_ids = {r["paper_id"] for r in doc["human_evidence"]}
    llm_ids = {r["paper_id"] for r in doc["llm_evidence"]}
    if human_ids & llm_ids:
        return fail(f"species overlap {sorted(human_ids & llm_ids)}")
    if not all(r.get("species") == "human" for r in doc["human_evidence"]):
        return fail("human rail contains a non-human row")
    if not all(r.get("species") == "llm" for r in doc["llm_evidence"]):
        return fail("llm rail contains a non-llm row")

    swap_errs = check_record(mutant_swap_species(doc))
    if not swap_errs:
        return fail("control: species-swap still passed")
    merge_errs = check_record(mutant_merge_reviewers(doc))
    if not merge_errs:
        return fail("control: merged reviewers still passed")

    payload = {
        "pass": True,
        "probe": "probe2-human-llm-rails",
        "unit_id": UNIT,
        "human_paper_ids": sorted(human_ids),
        "llm_paper_ids": sorted(llm_ids),
        "reviewer_rails": [r.get("rail") for r in doc["reviewers"]],
        "swap_species_errors": swap_errs[:4],
        "merge_reviewer_errors": merge_errs[:4],
        "independent": True,
        "reviewer_id": "RES-0082-llm-rail",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "both-states: live disjoint rails PASS; "
        f"species-swap FAIL ({swap_errs[0]}); "
        f"reviewer-merge FAIL ({merge_errs[0]})"
    )
    print(f"SUCCESS:{UNIT}-probe2 human and LLM evidence reported separately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 2: a gap-derived workflow closes the cited gap on re-measure.

Both-states:
  good — adding the generated candidate removes the cited gap
  bad  — prose-only and wrong-category twins leave the cited gap in place
Also: taxonomy size is parsed from spec text; deleting a leaf changes the sum.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.gap_finder import (  # noqa: E402
    covering_stubs,
    find_gaps,
    load_taxonomy,
    parse_taxonomy,
)
from workflow_foundry.generate import as_candidate, from_gap  # noqa: E402
from workflow_foundry.sample import OMITTED_GAP  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0194-probe2 {msg}")
    return 1


def main() -> int:
    tax = load_taxonomy()
    finder_src = (REPO / "tools/workflow_foundry/gap_finder.py").read_text(encoding="utf-8")
    library = covering_stubs(tax, omit=[OMITTED_GAP])
    before = find_gaps(tax, library)
    generated = from_gap(OMITTED_GAP, tax)
    after = find_gaps(tax, library + [as_candidate(generated)])
    prose = {
        "id": "prose-only-twin",
        "description": f"covers {OMITTED_GAP} in prose only",
    }
    prose_report = find_gaps(tax, library + [prose])
    other = next(cid for cid in tax.leaves if cid != OMITTED_GAP)
    wrong = from_gap(other, tax)
    wrong_report = find_gaps(tax, library + [as_candidate(wrong)])

    spec_text = Path(tax.source_path or "").read_text(encoding="utf-8")
    stripped = "\n".join(
        ln for ln in spec_text.splitlines() if not ln.startswith("- stop-rule:")
    )
    smaller = parse_taxonomy(stripped + "\n")

    payload = {
        "probe": "probe2-gap-remeasure",
        "unit_id": "IMP-0194",
        "cited_gap": OMITTED_GAP,
        "taxonomy_size": tax.size,
        "family_count_sum": sum(len(v) for v in tax.by_family.values()),
        "hardcoded_96_in_finder": ("= 96" in finder_src or "=96" in finder_src),
        "gap_present_before": OMITTED_GAP in before["gaps"],
        "gap_present_after_generated": OMITTED_GAP in after["gaps"],
        "gap_present_after_prose": OMITTED_GAP in prose_report["gaps"],
        "gap_present_after_wrong_category": OMITTED_GAP in wrong_report["gaps"],
        "before_gap_count": before["gap_count"],
        "after_gap_count": after["gap_count"],
        "spec_delete_leaf_size": smaller.size,
        "spec_size_dropped_by_one": smaller.size == tax.size - 1,
        "generated_workflow_id": generated["id"],
    }
    payload["pass"] = bool(
        payload["taxonomy_size"] == payload["family_count_sum"]
        and not payload["hardcoded_96_in_finder"]
        and payload["gap_present_before"]
        and not payload["gap_present_after_generated"]
        and payload["gap_present_after_prose"]
        and payload["gap_present_after_wrong_category"]
        and payload["before_gap_count"] == 1
        and payload["after_gap_count"] == 0
        and payload["spec_size_dropped_by_one"]
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["hardcoded_96_in_finder"]:
        return fail("gap finder hardcodes 96 instead of parsing the spec")
    if payload["taxonomy_size"] != payload["family_count_sum"]:
        return fail("family counts do not sum to parsed taxonomy size")
    if not payload["gap_present_before"]:
        return fail("cited gap absent before generation (fixture broken)")
    if payload["gap_present_after_generated"]:
        return fail("cited gap still present after adding generated workflow")
    if not payload["gap_present_after_prose"]:
        return fail("prose-only twin closed the gap (scanner overclaimed)")
    if not payload["gap_present_after_wrong_category"]:
        return fail("wrong-category twin closed the cited gap")
    if not payload["spec_size_dropped_by_one"]:
        return fail("deleting a spec leaf did not change the parsed total")
    print("SUCCESS:IMP-0194-probe2 gap-derived workflow closes cited gap on remeasure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

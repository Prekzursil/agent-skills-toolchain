"""IMP-0194 probe 2 (verifier, re-measured): the workflow compiled from the cited
coverage gap typed-covers the category; after adding it to the library and
re-running the gap finder the cited gap is ABSENT - re-measured, not asserted.
A prose-only twin and a wrong-category twin each leave the gap in place.
Taxonomy size is parsed from spec text (deleting a leaf drops it by one).

Exit 0 iff all five states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools"))
from workflow_foundry.sample import OMITTED_GAP  # noqa: E402
from workflow_foundry.gap_finder import (find_gaps, covering_stubs,  # noqa: E402
                                         load_taxonomy, parse_taxonomy)
from workflow_foundry.generate import from_gap, as_candidate  # noqa: E402

RAW = HERE / "probe2-gap-remeasure.raw.txt"

tax = load_taxonomy()
lib_before = covering_stubs(tax, omit=[OMITTED_GAP])
before = find_gaps(tax, lib_before)
gap_present_before = OMITTED_GAP in before["gaps"]

wf = from_gap(OMITTED_GAP, tax)
cand = as_candidate(wf)
after = find_gaps(tax, lib_before + [cand])
gap_present_after = OMITTED_GAP in after["gaps"]

prose_twin = {"id": "wf-prose-twin", "category": OMITTED_GAP.split(":")[0],
              "covers": [], "description": f"prose mentions {OMITTED_GAP} without typed cover"}
wrong_twin = {"id": "wf-wrong-cat", "category": "replay",
              "covers": [OMITTED_GAP]}
after_prose = find_gaps(tax, lib_before + [prose_twin])
after_wrong = find_gaps(tax, lib_before + [wrong_twin])
gap_present_after_prose = OMITTED_GAP in after_prose["gaps"]
gap_present_after_wrong = OMITTED_GAP in after_wrong["gaps"]

# Size is parsed, not hardcoded: removing one leaf from the spec text drops the
# parsed size by exactly one, and the finder carries no literal size constant.
spec_path = Path(tax.source_path)
spec_text = spec_path.read_text(encoding="utf-8")
shorter = parse_taxonomy(spec_text.replace("- token-budget\n", "", 1))
size_dropped = shorter.size == tax.size - 1
finder_src = (Path(W / "tools" / "workflow_foundry" / "gap_finder.py")).read_text(encoding="utf-8")
hardcoded = str(tax.size) in finder_src and "size=len(leaves)" not in finder_src

lines = [json.dumps({"probe": "probe2-gap-remeasure", "unit_id": "IMP-0194",
                     "cited_gap": OMITTED_GAP,
                     "generated_workflow_id": wf["id"],
                     "taxonomy_size": tax.size,
                     "family_count_sum": sum(len(v) for v in tax.by_family.values()),
                     "before_gap_count": before["gap_count"],
                     "after_gap_count": after["gap_count"],
                     "gap_present_before": gap_present_before,
                     "gap_present_after_generated": gap_present_after,
                     "gap_present_after_prose": gap_present_after_prose,
                     "gap_present_after_wrong_category": gap_present_after_wrong,
                     "spec_delete_leaf_size": shorter.size,
                     "spec_size_dropped_by_one": size_dropped,
                     "hardcoded_size_in_finder": hardcoded,
                     "pass": True})]
assert gap_present_before, "cited gap absent before generation"
assert not gap_present_after, "generated workflow did not close the cited gap on re-measure"
assert gap_present_after_prose, "prose-only twin closed the gap (untyped cover counted)"
assert gap_present_after_wrong, "wrong-category twin closed the gap (untyped cover counted)"
assert size_dropped, "taxonomy size not parsed from spec text"
assert not hardcoded, "finder appears to hardcode the taxonomy size"
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"cited_gap": OMITTED_GAP, "before": before["gap_count"],
                              "after": after["gap_count"], "taxonomy_size": tax.size,
                              "typed_cover_closes": True,
                              "prose_and_wrong_category_stay_open": True,
                              "size_parsed": True}))
print("SUCCESS:IMP-0194-probe2 gap-derived workflow closes the cited gap on re-measure")

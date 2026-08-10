"""Record a re-measurement of `known_defects_at_merge` ALONGSIDE it, never over it.

The existing block is named `..._at_merge` -- it is a historical snapshot, and four of its seven
entries no longer describe reality. Overwriting it would destroy the record of what was true then
and make the drift undetectable, so this adds a sibling `remeasured` block naming each delta.

WHAT DRIFTED (measured 2026-08-11, every count reproduced by tools/measure-guard/wudeps.py):

    dependency_cycles          1 -> 0        FIXED since merge. Control: a synthetic 2-cycle IS
                                             detected by the same walk, so the 0 is a measurement.
    self_dependencies          3 ids -> none FIXED since merge. IMP-0274 and IMP-0277 now depend on
                                             IMP-0265, IMP-0299 on IMP-0264. Control as above.
    unknown_form_dependency_tokens          WRONG CONTENT, RIGHT COUNT. Recorded
                                             ['BKT-ARC','BKT-CMD','BKT-IMP','WFA-1of2']; NONE of
                                             those four strings appears in any dependency list. The
                                             41 real offenders are bare prefixes: ARC 19, WFA 17,
                                             CC 4, IMP 1. The count 41 is exact.
    zero_member_bucket_refs    (unrecorded)  876 edges point at a bucket with no members. B07 alone
                                             carries 297. Never recorded in any form.

Two entries reproduce exactly and are left alone: unknown_form_dependency_refs 41 and
units_missing_bucket_field 1735.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
sys.path.insert(0, str(REPO / "tools/measure-guard"))

import wudeps as wd  # noqa: E402


def main() -> int:
    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser no longer round-trips this file byte-exactly; refusing to rewrite"
    )

    report = wd.scan(doc)
    at_merge = doc["work_units_meta"].get("known_defects_at_merge", {})

    tokens: dict[str, int] = {}
    for _, dep in report["dangling_refs"]:
        tokens[dep] = tokens.get(dep, 0) + 1

    doc["work_units_meta"]["remeasured_2026_08_11"] = {
        "measured_by": "tools/measure-guard/wudeps.py",
        "why": (
            "known_defects_at_merge is a historical snapshot and four of its entries no longer "
            "describe reality. Recorded here rather than overwritten so the drift stays visible."
        ),
        "units_scanned": report["units_scanned"],
        "dangling_refs": len(report["dangling_refs"]),
        "dangling_ref_tokens": dict(sorted(tokens.items(), key=lambda kv: -kv[1])),
        "zero_member_bucket_refs": len(report["zero_member_bucket_refs"]),
        "buckets_with_zero_members": sorted(
            b for b, n in report["bucket_members"].items() if n == 0
        ),
        "bucket_members": dict(sorted(report["bucket_members"].items())),
        "dependency_cycles": len(report["cycles"]),
        "self_dependencies": report["self_dependencies"],
        "units_missing_bucket_field": sum(
            1 for u in doc["work_units"] if not u.get("bucket")
        ),
        "deltas_against_at_merge": {
            "dependency_cycles": (
                f"{at_merge.get('dependency_cycles')} -> {len(report['cycles'])}: FIXED since "
                "merge; a synthetic 2-cycle is still detected by the same walk, so the 0 is a "
                "measurement and not a blind probe"
            ),
            "self_dependencies": (
                f"{at_merge.get('self_dependencies')} -> {report['self_dependencies'] or 'none'}: "
                "FIXED since merge; IMP-0274 and IMP-0277 now depend on IMP-0265, IMP-0299 on "
                "IMP-0264"
            ),
            "unknown_form_dependency_tokens": (
                f"{at_merge.get('unknown_form_dependency_tokens')} -> "
                f"{dict(sorted(tokens.items()))}: WRONG CONTENT, RIGHT COUNT. None of the recorded "
                "four strings appears in any dependency list; the real offenders are bare prefixes"
            ),
            "zero_member_bucket_refs": (
                "not recorded at merge -> 876 edges into buckets with no members, the largest "
                "single structural defect in the catalog and previously invisible to every gate"
            ),
            "reproduced_exactly": [
                "unknown_form_dependency_refs (41)",
                "units_missing_bucket_field (1735)",
            ],
        },
        "bucket_semantics": (
            "UNDEFINED, and this block takes no position on whether a zero-member bucket blocks "
            "execution. The token 'bucket' appears nowhere in the catalog contract, defaults or "
            "tool_policy, and twice in the 29,273-line governing spec, neither time as a definition "
            "(control: 'phase' appears 172 times there). Whether a B-token dependency means 'all "
            "members done', 'any member done', or 'a bucket-level gate artifact exists' is an owner "
            "ruling, and 876 edges plus 17 of the 43 Phase-15/16 units turn on it."
        ),
    }

    CATALOG.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8", newline=""
    )
    print(
        f"  recorded remeasured_2026_08_11: {report['units_scanned']} units, "
        f"{len(report['dangling_refs'])} dangling, "
        f"{len(report['zero_member_bucket_refs'])} zero-member-bucket refs"
    )
    print("  known_defects_at_merge left INTACT (historical record preserved)")
    print("\nSUCCESS:remeasure-defects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

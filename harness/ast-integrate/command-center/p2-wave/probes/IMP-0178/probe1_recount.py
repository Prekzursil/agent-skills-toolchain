#!/usr/bin/env python3
"""Probe 1: category counts derived from spec text, not a hardcoded total.

Independent dual parse: production state-machine vs probe-local regex.
AST walk refuses an integer total constant in the detector modules.
Gap-finder both-states: covering a planted gap removes it.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gap_finder import Candidate, find_gaps, load_vectors  # noqa: E402
from taxonomy import load_spec  # noqa: E402

SPEC = HERE / "fixtures" / "spec_taxonomy.md"
DETECTORS = (HERE / "taxonomy.py", HERE / "gap_finder.py")
# Catalog oracle lives in the probe, never in the detector.
CATALOG_FAMILY_COUNTS = {
    "research/evidence": 15,
    "engineering/reliability": 21,
    "security/governance": 12,
    "product/design": 15,
    "data/science": 16,
    "collective-intelligence/meta": 17,
}


def independent_parse(text: str) -> tuple[dict[str, int], list[str]]:
    """Different extraction path: header regex + dash-slug regex, no shared helpers."""
    headers = {
        m.group(1): int(m.group(2))
        for m in re.finditer(
            r"^([a-z0-9-]+/[a-z0-9-]+)\s+(\d+)\s*$", text, re.M
        )
    }
    # Split on headings so leaves are not taken from prose.
    leaves: list[str] = []
    current = None
    for line in text.splitlines():
        hm = re.match(r"^###\s+([a-z0-9-]+/[a-z0-9-]+)\s*$", line)
        if hm:
            current = hm.group(1)
            continue
        lm = re.match(r"^-\s+([a-z0-9][a-z0-9-]*)\s*$", line)
        if lm and current:
            leaves.append(lm.group(1))
    return headers, leaves


def forbid_hardcoded_total(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    catalog_sum = sum(CATALOG_FAMILY_COUNTS.values())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == catalog_sum:
            raise SystemExit(
                f"FAILED:IMP-0178-probe1 hardcoded total {catalog_sum} in {path.name}"
            )


def main() -> int:
    text = SPEC.read_text(encoding="utf-8")
    tax = load_spec(SPEC)
    headers, leaves = independent_parse(text)

    if tax.inconsistencies:
        print("FAILED:IMP-0178-probe1 taxonomy inconsistent", tax.inconsistencies)
        return 1
    if headers != {f.id: f.declared_count for f in tax.families}:
        print("FAILED:IMP-0178-probe1 header dual-parse mismatch")
        print(" indep", headers)
        print(" prod", {f.id: f.declared_count for f in tax.families})
        return 1
    if tuple(leaves) != tax.ids:
        print("FAILED:IMP-0178-probe1 leaf dual-parse mismatch")
        return 1
    if headers != CATALOG_FAMILY_COUNTS:
        print("FAILED:IMP-0178-probe1 family counts != catalog oracle", headers)
        return 1

    leaf_total = len(leaves)
    header_sum = sum(headers.values())
    catalog_sum = sum(CATALOG_FAMILY_COUNTS.values())
    if leaf_total != header_sum:
        print(
            f"FAILED:IMP-0178-probe1 leaf_total={leaf_total} != header_sum={header_sum}"
        )
        return 1
    if leaf_total != catalog_sum:
        print(
            f"FAILED:IMP-0178-probe1 leaf_total={leaf_total} != catalog_sum={catalog_sum}"
        )
        return 1
    if tax.leaf_total != leaf_total or tax.declared_total != header_sum:
        print("FAILED:IMP-0178-probe1 production totals disagree with independent parse")
        return 1

    for path in DETECTORS:
        forbid_hardcoded_total(path)

    gaps = find_gaps(tax, load_vectors())
    if gaps["unknown_category_refs"]:
        print("FAILED:IMP-0178-probe1 unknown category refs", gaps["unknown_category_refs"])
        return 1
    if not gaps["gap_set"]:
        print("FAILED:IMP-0178-probe1 fixture has no gaps; both-states control is vacuous")
        return 1
    planted = gaps["gap_set"][0]
    closed = find_gaps(tax, list(load_vectors()) + [Candidate("cand.plant-cover", (planted,))])
    if planted in closed["gap_set"]:
        print(f"FAILED:IMP-0178-probe1 covering {planted} did not close the gap")
        return 1
    if closed["gap_count"] != gaps["gap_count"] - 1:
        print("FAILED:IMP-0178-probe1 gap count did not drop by one after cover")
        return 1

    print(
        json.dumps(
            {
                "leaf_total": leaf_total,
                "header_sum": header_sum,
                "catalog_sum": catalog_sum,
                "families": headers,
                "hardcoded_total_absent": True,
                "gap_count": gaps["gap_count"],
                "gap_set": gaps["gap_set"],
                "planted_closed": planted,
            },
            indent=2,
        )
    )
    print(
        f"leaf_total={leaf_total} header_sum={header_sum} "
        f"gaps={gaps['gap_count']} planted_closed={planted}"
    )
    print("SUCCESS:IMP-0178-probe1 spec recount without hardcoded total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

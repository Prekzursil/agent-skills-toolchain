#!/usr/bin/env python3
"""_r4_table_scan.py -- report how many markdown tables in docs/hook-audit publish a
MEASUREMENT, and how each one satisfies the round-4 rule (inline cite / reasoned waiver /
violation).

WHY IT EXISTS. This ran BEFORE the rule in `check_citations.py` was chosen, to size it
against the real corpus rather than adopt it and discover the blast radius afterwards. At
that moment it counted 6 measurement tables, 3 already carrying inline markers, so the rule
would flag 3 -- a floor the corpus could actually meet. A gate that fires on everything
trains the reader to ignore it, which is one of this audit's own findings.

IT DOES NOT REIMPLEMENT THE CLASSIFIER. The first version did, and immediately produced the
failure this program keeps paying for: it reported "WOULD FLAG: 3" while the gate reported
"0 uncited", because the standalone copy predated the waiver mechanism. Two detectors
disagreeing about the same corpus is a detector failure, not a finding -- so this now imports
`measurement_tables` from the gate itself. One classifier, one truth, no drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DOCS = REPO / "docs" / "hook-audit"

sys.path.insert(0, str(HERE))
from check_citations import (  # noqa: E402  (path must be set before the import)
    CITE,
    MEASURE,
    classifier_selfcheck,
    measurement_tables,
)


def main() -> int:
    fires, silent = classifier_selfcheck()
    if not (fires and silent):
        print(
            f"FAILED:r4-table-scan the shared classifier failed its own both-states control "
            f"(fires={fires}, silent={silent}) -- no counts published"
        )
        return 1

    total = violations = 0
    for md in sorted(DOCS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        viol, n_meas = measurement_tables(text)
        total += n_meas
        violations += len(viol)
        for v in viol:
            print(f"  FLAG {md.name}:{v['line']}  {v['why']}")
    satisfied = total - violations
    print(
        f"\n== measurement tables: {total}  satisfied (cited or reasoned waiver): "
        f"{satisfied}  violations: {violations}"
    )
    print(f"== regexes in use: MEASURE={MEASURE.pattern!r} CITE={CITE.pattern!r}")
    if total == 0:
        print(
            "FAILED:r4-table-scan zero tables found -- the parser is broken, not the corpus"
        )
        return 1
    print("SUCCESS:r4-table-scan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

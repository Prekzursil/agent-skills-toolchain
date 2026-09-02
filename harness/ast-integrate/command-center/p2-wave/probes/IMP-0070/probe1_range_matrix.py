#!/usr/bin/env python3
"""IMP-0070 probe 1: 30-case range matrix vs vendored node-semver.

Signal 1: this resolver's selection.
Signal 2: node-semver 7.6.3 maxSatisfying on the same cases.
Divergences are listed per case; a pass rate is not a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.evaluate import evaluate_matrix  # noqa: E402


def main() -> int:
    report = evaluate_matrix()
    print(json.dumps({k: report[k] for k in ("case_count", "agreements", "all_agree", "reference", "divergences")}, indent=2))
    for row in report["rows"]:
        mark = "AGREE" if row["agree"] else "DIVERGE"
        print(
            f"{row['id']} {mark} range={row['range']!r} ours={row['ours']!r} ref={row['reference']!r}"
        )
    if not report["all_agree"] or report["agreements"] != 30:
        print(
            f"FAILED:IMP-0070-probe1 divergences={len(report['divergences'])} agreements={report['agreements']}/30"
        )
        return 1
    print("SUCCESS:IMP-0070-probe1 30/30 selections identical to node-semver maxSatisfying")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

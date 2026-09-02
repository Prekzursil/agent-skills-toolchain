#!/usr/bin/env python3
"""Probe 1: every artifact kind has a named consumer cell; none silently omitted."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

REPORT = REPO / M.OUT_REL


def main() -> int:
    catalog = M.load_catalog()
    live = M.build_matrix(catalog)
    counts = live["counts"]
    kinds = live["kinds"]
    cells = live["cells"]
    consumers = set(M.CONSUMERS)

    if not live["matrix_complete"]:
        print(f"FAILED:TST-0012-probe1 omitted={live['omitted_kind_ids'][:10]}")
        return 1
    if counts["cells"] != counts["kinds"] * counts["consumers"]:
        print(
            "FAILED:TST-0012-probe1 cell arithmetic "
            f"{counts['cells']} != {counts['kinds']}*{counts['consumers']}"
        )
        return 1
    if counts["kinds"] < 2 or counts["consumers"] != 3:
        print(f"FAILED:TST-0012-probe1 kinds={counts['kinds']} consumers={counts['consumers']}")
        return 1

    unnamed = []
    omitted_status = []
    for kind in kinds:
        group = [c for c in cells if c["kind_id"] == kind["kind_id"]]
        names = [c.get("consumer_id") for c in group]
        if set(names) != consumers or len(names) != 3:
            unnamed.append(kind["kind_id"])
        for cell in group:
            if not cell.get("status"):
                omitted_status.append(kind["kind_id"])
            if cell["status"] not in {
                "UNCONSUMED",
                "READ_OK",
                "INSTANCE_ABSENT",
                "PARSE_FAIL",
                "FIELD_MISSING",
            }:
                omitted_status.append(kind["kind_id"])
    if unnamed:
        print(f"FAILED:TST-0012-probe1 kinds missing named consumers {unnamed[:8]}")
        return 1
    if omitted_status:
        print(f"FAILED:TST-0012-probe1 cells without status {omitted_status[:8]}")
        return 1

    # UNCONSUMED must appear rather than kinds being dropped.
    if counts["unconsumed_kinds"] <= 0:
        print("FAILED:TST-0012-probe1 expected some UNCONSUMED kinds on this tree")
        return 1
    if counts["unconsumed_cells"] <= 0:
        print("FAILED:TST-0012-probe1 UNCONSUMED cells omitted")
        return 1
    if "contracted:PHASE-GRAPH.json" not in [k["kind_id"] for k in kinds]:
        print("FAILED:TST-0012-probe1 PHASE-GRAPH kind omitted from matrix")
        return 1
    if "contracted:WORK-UNIT-CATALOG.json" not in [k["kind_id"] for k in kinds]:
        print("FAILED:TST-0012-probe1 catalog kind omitted")
        return 1

    if REPORT.is_file():
        doc = json.loads(REPORT.read_text(encoding="utf-8"))
        reported = (doc.get("consumer_artifact_matrix") or {}).get("counts") or {}
        if int(reported.get("kinds") or -1) != counts["kinds"]:
            print(
                "FAILED:TST-0012-probe1 report kinds "
                f"{reported.get('kinds')} != live {counts['kinds']}"
            )
            return 1
        if int(reported.get("cells") or -1) != counts["cells"]:
            print(
                "FAILED:TST-0012-probe1 report cells "
                f"{reported.get('cells')} != live {counts['cells']}"
            )
            return 1
        tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
        row = tests.get("test_each_artifact_kind_has_a_named_consumer")
        if not row or row.get("result") != "PASS":
            print("FAILED:TST-0012-probe1 receipt test row missing or not PASS")
            return 1

    print(
        "kinds={kinds} cells={cells} named_consumer_kinds={named} "
        "unconsumed_kinds={un} unconsumed_cells={uc} complete={ok}".format(
            kinds=counts["kinds"],
            cells=counts["cells"],
            named=counts["kinds_with_named_consumer"],
            un=counts["unconsumed_kinds"],
            uc=counts["unconsumed_cells"],
            ok=live["matrix_complete"],
        )
    )
    print(
        "SUCCESS:TST-0012-probe1 every kind has three named consumer cells; "
        "UNCONSUMED is reported rather than omitted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

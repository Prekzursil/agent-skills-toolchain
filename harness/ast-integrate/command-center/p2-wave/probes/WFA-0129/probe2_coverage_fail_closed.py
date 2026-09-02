#!/usr/bin/env python3
"""Probe 2: coverage row count is computed and fail-closed at != 30.

Independent of probe 1: rebuilds the executable map, recounts rows from the
returned matrix (does not trust a stored integer), and confirms 29 and 31
units are refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

RAW = HERE / "probe2-coverage-fail-closed.raw.json"
ART = (
    HERE.parents[3]
    / "command-center/foundry/WFA-0129-matched-case-benchmark-corpus-for-fusion-evaluation.json"
)


def main() -> int:
    estate = C.executable_estate()
    built = C.build_corpus(
        estate["merge_units"], estate["registry"], estate["blueprints"]
    )
    recounted = C.recount_rows(built["coverage_matrix"])
    c29 = C.fail_closed_wrong_n(29)
    c31 = C.fail_closed_wrong_n(31)
    c30 = C.fail_closed_wrong_n(30)

    artifact_recount = None
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        artifact_recount = C.recount_rows(doc.get("coverage_matrix") or {})

    payload = {
        "builder_row_count": built["coverage_row_count"],
        "recounted_row_count": recounted["row_count"],
        "recounted_benchmarkable": recounted["benchmarkable_count"],
        "recounted_excluded": recounted["excluded_count"],
        "fail_closed_29": c29,
        "fail_closed_31": c31,
        "fail_closed_30_refused": c30["refused"],
        "artifact_recount": artifact_recount,
        "n_merge_units": len(estate["merge_units"]),
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "rows_stored={0} rows_recounted={1} benchmarkable={2} excluded={3}".format(
            built["coverage_row_count"],
            recounted["row_count"],
            recounted["benchmarkable_count"],
            recounted["excluded_count"],
        )
    )
    print(
        "fail_closed_29={0}/{1} fail_closed_31={2}/{3} n30_refused={4}".format(
            c29["refused"],
            c29["code"],
            c31["refused"],
            c31["code"],
            c30["refused"],
        )
    )
    if recounted["row_count"] != C.EXPECTED_N:
        print("FAILED:WFA-0129-probe2 recounted rows != 30")
        return 1
    if built["coverage_row_count"] != recounted["row_count"]:
        print("FAILED:WFA-0129-probe2 stored row_count disagrees with len(rows)")
        return 1
    if len(estate["merge_units"]) != C.EXPECTED_N:
        print("FAILED:WFA-0129-probe2 executable map is not 30 units")
        return 1
    if not c29["refused"] or c29["code"] != "merge-unit-count":
        print(f"FAILED:WFA-0129-probe2 29 units not fail-closed: {c29}")
        return 1
    if not c31["refused"] or c31["code"] != "merge-unit-count":
        print(f"FAILED:WFA-0129-probe2 31 units not fail-closed: {c31}")
        return 1
    if c30["refused"]:
        print("FAILED:WFA-0129-probe2 30 units were refused")
        return 1
    if artifact_recount is not None and artifact_recount["row_count"] != C.EXPECTED_N:
        print("FAILED:WFA-0129-probe2 artifact coverage rows != 30")
        return 1
    print(
        "NEGATIVE-CONTROL: build_corpus(n=29) raises FailClosed "
        "merge-unit-count; coverage is not padded to 30"
    )
    print("SUCCESS:WFA-0129-probe2 coverage-row-count fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

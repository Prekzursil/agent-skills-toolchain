#!/usr/bin/env python3
"""Probe 1: vN → vN+1 → vN preserves semantics; lossy step fails that test.

Signal 1 of IMP-0073. Method: migrate() round-trip plus the catalog
test_round_trip_preserves_semantics. Negative control: lossy_migrate_1_to_2
must change the semantic digest. Distinct from probe 2 (old-parser refuse).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.index_migrate import (  # noqa: E402
    COMPATIBILITY_WINDOW_VERSIONS,
    CURRENT_SCHEMA_VERSION,
    file_record_count,
    lossy_migrate_1_to_2,
    migrate,
    schema_version_of,
    semantics,
)
from tools.marketplace.tests import test_index_migrate as T  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0073.json"


def _receipt_ok() -> str | None:
    if not ART.is_file():
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0073" not in text:
        return "sentinel absent"
    return None


def main() -> int:
    T.test_round_trip_preserves_semantics()
    T.test_lossy_migration_fails_round_trip()
    T.test_compatibility_window_is_a_number_of_versions()

    v1 = T.sample_v1_index()
    v2 = migrate(v1, 2)
    back = migrate(v2, 1)
    honest_match = semantics(v1) == semantics(v2) == semantics(back)
    lossy = lossy_migrate_1_to_2(v1)
    lossy_back = migrate(lossy, 1)
    lossy_diverges = semantics(v1) != semantics(lossy_back)

    report = {
        "probe": "probe1-round-trip",
        "unit_id": "IMP-0073",
        "current_schema_version": CURRENT_SCHEMA_VERSION,
        "compatibility_window_versions": COMPATIBILITY_WINDOW_VERSIONS,
        "window_is_int": isinstance(COMPATIBILITY_WINDOW_VERSIONS, int),
        "v1_schema_version": schema_version_of(v1),
        "v2_schema_version": schema_version_of(v2),
        "v1_file_record_count": file_record_count(v1),
        "v2_file_record_count": file_record_count(v2),
        "v2_compatibility_window": v2.get("compatibility_window"),
        "honest_round_trip_semantics_equal": honest_match,
        "lossy_negative_control_diverges": lossy_diverges,
        "lossy_dropped_records": file_record_count(v1) - file_record_count(lossy),
        "pass": honest_match and lossy_diverges,
    }
    print(json.dumps(report, sort_keys=True))
    if not honest_match:
        print("FAILED:IMP-0073-probe1 honest round-trip lost semantics")
        return 1
    if not lossy_diverges:
        print("FAILED:IMP-0073-probe1 lossy control did not fail round-trip")
        return 1
    err = _receipt_ok()
    if err:
        print(f"FAILED:IMP-0073-probe1 {err}")
        return 1
    print("SUCCESS:IMP-0073-probe1 round-trip preserves semantics; lossy control fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Floor-recall control: all nine named floors must extract before coverage."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

REPO = HERE.parents[3]
ARTIFACT = REPO / "command-center" / "receipts" / "CC-0024.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0024-probe1 {msg}")
    return 1


def main() -> int:
    units = X.catalog_units()
    path, kind, lines = X.locate_spec(units)
    live = X.extract_from_lines(lines, units)
    recall = live["floor_recall"]
    print(f"spec kind={kind} path={path}")
    print(f"required={recall['required_ids']}")
    print(f"found={recall['found_ids']}")
    print(f"missing={recall['missing_ids']}")
    if not recall["passed"]:
        return fail("floor-recall-miss " + ",".join(recall["missing_ids"]))
    if len(recall["found_ids"]) != 9:
        return fail(f"floor-count-{len(recall['found_ids'])}")
    if "coverage" not in live:
        return fail("coverage-withheld-despite-recall")

    mutant = list(lines)
    target = next(r for r in live["requirements"] if r.get("floor_id") == "FLOOR-2048-UNITS")
    mutant = X.delete_requirement_text(mutant, target)
    broken = X.extract_from_lines(mutant, units)
    if broken["floor_recall"]["passed"]:
        return fail("mutant-still-recalls-2048")
    if "FLOOR-2048-UNITS" not in broken["floor_recall"]["missing_ids"]:
        return fail("mutant-missing-ids-wrong")
    if "coverage" in broken:
        return fail("coverage-emitted-after-failed-recall")

    if not ARTIFACT.is_file():
        return fail("artifact-absent")
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if "SUCCESS:CC-0024" not in json.dumps(doc):
        return fail("sentinel-absent")
    if not doc.get("floor_recall", {}).get("passed"):
        return fail("artifact-recall-false")
    if "coverage" not in doc:
        return fail("artifact-coverage-absent")
    if doc["coverage"].get("emitted_after_floor_recall") is not True:
        return fail("artifact-coverage-not-gated")
    art_found = set(doc["floor_recall"]["found_ids"])
    if art_found != set(X.FLOOR_IDS):
        return fail("artifact-floors-mismatch")

    print("mutant_recall_failed=True coverage_withheld_on_mutant=True")
    print("SUCCESS:CC-0024-probe1 floor-recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

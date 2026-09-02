#!/usr/bin/env python3
"""Named probe 2: ambient-dependent tests are enumerated test-by-test."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from lane import (  # noqa: E402
    EXPECTED_AMBIENT_ONLY,
    EXPECTED_CLEAN_ONLY,
    FORBIDDEN_IDS,
    check_ambient_enumeration,
    run_lane,
)

ART = REPO / "command-center/receipts/TST-0024.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0024-p2-lane-") as tmp:
        lane = run_lane(Path(tmp))
        check = check_ambient_enumeration(lane)
        print(json.dumps(check, indent=2, sort_keys=True, default=str)[:4000])
        if not check["pass"]:
            print("FAILED:TST-0024-probe2 ambient-dependent enumeration")
            return 1
        rows = {r["id"]: r for r in check["rows"]}
        print(
            f"ambient_only={EXPECTED_AMBIENT_ONLY} "
            f"kind={rows[EXPECTED_AMBIENT_ONLY]['kind']}"
        )
        print(
            f"clean_only={EXPECTED_CLEAN_ONLY} "
            f"kind={rows[EXPECTED_CLEAN_ONLY]['kind']}"
        )
        print(f"forbidden_absent={all(tid not in rows for tid in FORBIDDEN_IDS)}")

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0024-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:TST-0024" not in text:
        print("FAILED:TST-0024-probe2 sentinel absent")
        return 1
    recorded = doc.get("ambient_dependent") or []
    rec_ids = {r.get("id") for r in recorded if isinstance(r, dict)}
    live_ids = set(rows)
    if rec_ids != live_ids:
        print(
            "FAILED:TST-0024-probe2 receipt delta != live enumeration "
            f"receipt={sorted(rec_ids)} live={sorted(live_ids)}"
        )
        return 1
    print("SUCCESS:TST-0024-probe2 ambient-dependent tests enumerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""CC-0008 probe 1: run merge tests + live slice measure; write raw + summary."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import catalog_slice_merge as m  # noqa: E402


def main() -> int:
    PROBE.mkdir(parents=True, exist_ok=True)
    tests = REPO / "tools/command-center/tests/test_catalog_slice_merge.py"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests), "-q", "--tb=line"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    pytest_out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE / "pytest-merge.out").write_text(pytest_out, encoding="utf-8")

    # Live measure (read-back counts; never invent)
    units, sources = m.load_slices(m.DEFAULT_SLICES)
    counts = m.per_bucket_counts(units)
    floor = 2048
    summary = {
        "probe": "CC-0008-probe1-merge",
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pytest_rc": proc.returncode,
        "work_unit_count_read_back": len(units),
        "floor": floor,
        "shortfall": floor - len(units),
        "meets_floor": len(units) >= floor,
        "per_bucket_counts": counts,
        "collision_free": all(len(v) == 1 for v in sources.values()),
        "allocation_path": "command-center/ID-NAMESPACE-ALLOCATION.json",
        "merger": "tools/command-center/catalog_slice_merge.py",
    }
    (PROBE / "probe1-merge-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = [
        "PROBE=CC-0008-probe1-merge",
        f"PYTEST_RC={proc.returncode}",
        f"WORK_UNIT_COUNT_READ_BACK={len(units)}",
        f"FLOOR={floor}",
        f"SHORTFALL={floor - len(units)}",
        f"PER_BUCKET={json.dumps(counts, sort_keys=True)}",
        f"COLLISION_FREE={summary['collision_free']}",
        "PYTEST_TAIL_BEGIN",
        pytest_out[-4000:],
        "PYTEST_TAIL_END",
        f"VERDICT={'PASS' if proc.returncode == 0 else 'FAIL'}",
    ]
    (PROBE / "probe1-merge.raw.txt").write_text("\n".join(raw) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())

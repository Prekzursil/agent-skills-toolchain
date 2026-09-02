#!/usr/bin/env python3
"""Probe 2: dirty-migration double-run fires; N-2→N completes or refuses; partial fails."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drill as D  # noqa: E402
import upgrade as U  # noqa: E402


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="rel0005-probe2-"))
    try:
        dirty = D.drill_dirty_control(base / "dirty")
        skip_ok = D.drill_skip_complete(base / "skip-ok")
        skip_no = D.drill_skip_refuse(base / "skip-no")
        partial = D.drill_partial_fails(base / "partial")
        iso = D.drill_isolation_control()
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)

    checks = {
        "dirty_second_run_measured": dirty["second_run_measured"] is True,
        "dirty_double_run_check_fired": dirty["double_run_check_fired"] is True,
        "dirty_second_mutations_nonzero": dirty["second_mutation_count"] > 0,
        "skip_n2_to_n_completed_fully": (
            skip_ok["outcome"] == "completed"
            and skip_ok["partial_apply"] is False
            and skip_ok["version"] == U.N
            and skip_ok["all_four_once"] is True
        ),
        "skip_gap_refused": (
            skip_no["outcome"] == "refused" and skip_no["version_unchanged"] is True
        ),
        "partial_chain_fails_drill": partial["partial_chain_fails_drill"] is True,
        "isolation_control_fired": iso["isolation_control_fired"] is True,
        "skip_skill_survived": skip_ok["skill_identical"] is True,
    }
    payload = {
        "probe": "probe2-controls",
        "unit_id": "REL-0005",
        "dirty": {
            "second_mutation_count": dirty["second_mutation_count"],
            "fired": dirty["double_run_check_fired"],
            "id": dirty["dirty_id"],
        },
        "skip_complete": {
            "outcome": skip_ok["outcome"],
            "version": skip_ok["version"],
            "execution_counts": skip_ok["execution_counts"],
        },
        "skip_refuse": {
            "outcome": skip_no["outcome"],
            "reason": skip_no.get("reason"),
            "version_unchanged": skip_no["version_unchanged"],
        },
        "partial_chain_status": partial["broken"]["chain_status"],
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    for name, ok in checks.items():
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:REL-0005-probe2 {name}")
            return 1
    print("SUCCESS:REL-0005-probe2 dirty-control fires; skip-version complete-or-refuse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

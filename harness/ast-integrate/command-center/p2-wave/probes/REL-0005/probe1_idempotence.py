#!/usr/bin/env python3
"""Probe 1: N-1 to N twice; second run mutation_count is measured zero; skill sha256 identical."""
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
    base = Path(tempfile.mkdtemp(prefix="rel0005-probe1-"))
    try:
        n1 = D.drill_n1_to_n(base)
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)

    checks = {
        "isolated": n1["isolation"]["isolated"] is True,
        "owner_home_untouched": n1["isolation"]["owner_home_touched"] is False,
        "second_run_measured": n1["second_run_measured"] is True,
        "second_run_mutation_count_zero": n1["second_run_mutation_count"] == 0,
        "each_migration_once": n1["each_migration_once"] is True,
        "skill_sha256_identical": n1["skill_identical"] is True,
        "owner_canary_preserved": n1["owner_canary_preserved"] is True,
        "version_is_n": n1["version"] == U.N,
        "undeclared_skill_not_mutated": n1["first"]["undeclared_user_mutations"] == [],
    }
    payload = {
        "probe": "probe1-idempotence",
        "unit_id": "REL-0005",
        "second_run_mutation_count": n1["second_run_mutation_count"],
        "execution_counts": n1["execution_counts"],
        "skill_sha256_before": n1["skill_sha256_before"],
        "skill_sha256_after": n1["skill_sha256_after"],
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks.items():
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:REL-0005-probe1 {name}")
            return 1
    print("SUCCESS:REL-0005-probe1 second-run mutation_count=0 skill sha256 identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

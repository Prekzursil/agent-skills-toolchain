#!/usr/bin/env python3
"""Named probe 2: skip-migration control + identical health check.

Mechanically different from probe 1 (no field flatten). Re-runs:
  * clean v2 install through health_check(strict=True)
  * upgraded install through the same function
  * overlay-current without migrate -> strict health MUST fail
  * the same skip profile through health_check(strict=False) MUST pass
    (weaker check that cannot see a bad upgrade)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import HEALTH_PROBE_IDS, run_scenario  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0099-upgrade-path.json"


def payload(doc: dict) -> dict:
    report = doc.get("report")
    if isinstance(report, dict) and "skip_migration_control" in report:
        return report
    return doc


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0099-probe2 upgrade artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0099":
        print("FAILED:CNF-0099-probe2 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0099-p2-") as tmp:
        result = run_scenario(Path(tmp))

    if not result["clean_ok"]:
        print("FAILED:CNF-0099-probe2 clean health failed", result["clean_health"]["failed_ids"])
        return 1
    if not result["upgraded_ok"]:
        print("FAILED:CNF-0099-probe2 upgraded health failed", result["upgraded_health"]["failed_ids"])
        return 1
    if result["clean_health"]["probe_ids"] != HEALTH_PROBE_IDS:
        print("FAILED:CNF-0099-probe2 clean probe set drifted")
        return 1
    if result["upgraded_health"]["probe_ids"] != result["clean_health"]["probe_ids"]:
        print("FAILED:CNF-0099-probe2 upgraded used a different probe set (weaker-health-check)")
        return 1
    if result["skip_strict"]["ok"]:
        print("FAILED:CNF-0099-probe2 skip-migration health was green")
        print(json.dumps(result["skip_strict"], indent=2, default=str)[:2000])
        return 1
    if not result["skip_weak"]["ok"]:
        print("FAILED:CNF-0099-probe2 weaker check did not pass skip profile")
        print(json.dumps(result["skip_weak"], indent=2, default=str)[:2000])
        return 1

    required_fail = {"schema_version", "custom_absent", "locale_object"}
    failed = set(result["skip_strict"]["failed_ids"])
    missing = required_fail - failed
    if missing:
        print("FAILED:CNF-0099-probe2 skip control missed probes", sorted(missing))
        return 1

    body = payload(doc)
    recorded = body.get("skip_migration_control") or {}
    if recorded.get("health_check_failed") is not True:
        print("FAILED:CNF-0099-probe2 artifact skip control not failed")
        return 1
    rec_failed = set(recorded.get("failed_probe_ids") or [])
    if rec_failed != failed:
        print("FAILED:CNF-0099-probe2 artifact skip failed-id drift")
        print("live", sorted(failed), "art", sorted(rec_failed))
        return 1
    hc = body.get("health_check") or {}
    if hc.get("identical_implementation") is not True or hc.get("identical_probe_set") is not True:
        print("FAILED:CNF-0099-probe2 artifact missing identical-health claim")
        return 1
    if not (hc.get("clean_install") or {}).get("ok") or not (hc.get("upgraded") or {}).get("ok"):
        print("FAILED:CNF-0099-probe2 artifact health rows not both ok")
        return 1

    out = {
        "probe": "probe2-skip-migration",
        "unit_id": "CNF-0099",
        "clean_ok": True,
        "upgraded_ok": True,
        "identical_probe_set": True,
        "skip_health_failed": True,
        "failed_probe_ids": sorted(failed),
        "weaker_check_would_pass": True,
        "discriminates": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "clean=True upgraded=True skip_failed=True weaker_pass=True "
        f"failed={sorted(failed)}"
    )
    print("SUCCESS:CNF-0099-probe2 skip-migration health control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

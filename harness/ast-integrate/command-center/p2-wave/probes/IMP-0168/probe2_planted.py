#!/usr/bin/env python3
"""Named probe 2: planted inexpressible construct appears in the ledger.

Both-states:
  clean twin -> empty ledger AND 100% preserved
  planted twin -> ledger row for the planted kind, load_bearing True
Silent-drop mutant of the planted fixture must fail accounting (detector fires).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures_table import FIXTURE_ROWS, fixture_path  # noqa: E402
from inventory import inventory  # noqa: E402
from ledger import ledger_from_import  # noqa: E402


def main() -> int:
    findings = []
    failed = False
    for adapter, name, planted, expect_empty in FIXTURE_ROWS:
        path = fixture_path(name)
        source = inventory(path, adapter)
        preserved, losses, acc = ledger_from_import(source)
        kinds_lost = {e.construct for e in losses}
        load_bearing_lost = {
            e.construct: e.load_bearing for e in losses if e.load_bearing
        }
        rec = {
            "fixture": name,
            "adapter": adapter,
            "planted": sorted(planted),
            "lost_kinds": sorted(kinds_lost),
            "coverage_pct": acc.coverage_pct,
            "empty_ledger": acc.lost_count == 0,
            "empty_justified": acc.empty_ledger_justified,
        }
        if expect_empty:
            if not acc.empty_ledger_justified or planted:
                failed = True
                rec["error"] = "clean-fixture-not-empty-justified"
        else:
            missing = sorted(planted - kinds_lost)
            if missing:
                failed = True
                rec["error"] = f"planted-not-in-ledger:{missing}"
            for kind in planted:
                if not load_bearing_lost.get(kind, False):
                    failed = True
                    rec["error"] = f"planted-{kind}-not-load-bearing"
            # Silent-drop mutant: same source, no ledger rows for losses.
            _p2, _l2, acc_drop = ledger_from_import(source, silent_drop=True)
            rec["silent_drop_ok"] = acc_drop.ok
            rec["silent_drop_unaccounted"] = list(acc_drop.unaccounted_ids)
            rec["silent_drop_failures"] = list(acc_drop.failures)
            if acc_drop.ok or not acc_drop.unaccounted_ids:
                failed = True
                rec["error"] = "silent-drop-mutant-not-caught"
            if acc.coverage_pct != 100.0:
                failed = True
                rec["error"] = "honest-import-coverage-not-100"
        findings.append(rec)

    payload = {"failed": failed, "findings": findings}
    print(json.dumps(payload, sort_keys=True))
    if failed:
        print("FAILED:IMP-0168-probe2 planted-inexpressible")
        return 1
    print(
        "SUCCESS:IMP-0168-probe2 planted inexpressible appears in ledger "
        "with load-bearing flag; silent-drop mutant caught"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Named probe 1: construct accounting == 100% on every fixture (computed).

Empty ledger is accepted only when preserved == source and unaccounted == 0.
A silent-drop of any construct fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures_table import FIXTURE_ROWS, fixture_path  # noqa: E402
from inventory import inventory  # noqa: E402
from ledger import ledger_from_import, require_ledger_shape  # noqa: E402


def main() -> int:
    rows = []
    failed = False
    for adapter, name, _planted, expect_empty in FIXTURE_ROWS:
        path = fixture_path(name)
        source = inventory(path, adapter)
        _preserved, losses, acc = ledger_from_import(source)
        shape_err = require_ledger_shape(losses)
        row = {
            "fixture": name,
            "adapter": adapter,
            "source_count": acc.source_count,
            "preserved_count": acc.preserved_count,
            "lost_count": acc.lost_count,
            "unaccounted": list(acc.unaccounted_ids),
            "coverage_pct": acc.coverage_pct,
            "empty_ledger_justified": acc.empty_ledger_justified,
            "ok": acc.ok,
            "failures": list(acc.failures),
            "shape_err": shape_err,
        }
        rows.append(row)
        if not acc.ok or acc.coverage_pct != 100.0 or acc.source_count < 1:
            failed = True
        if expect_empty and not acc.empty_ledger_justified:
            failed = True
            row["failures"] = list(acc.failures) + ["expected-empty-ledger"]
        if (not expect_empty) and acc.lost_count < 1:
            failed = True
            row["failures"] = list(acc.failures) + ["expected-losses"]
        if shape_err:
            failed = True

    # Vacuity control: empty source must not report 100%.
    from ledger import account as account_fn  # noqa: WPS433

    vacuous = account_fn([], [], [])
    if vacuous.ok or vacuous.coverage_pct == 100.0:
        failed = True
        rows.append(
            {
                "fixture": "<empty-source>",
                "ok": False,
                "failures": ["vacuous-100-not-rejected"],
                "coverage_pct": vacuous.coverage_pct,
            }
        )
    else:
        rows.append(
            {
                "fixture": "<empty-source>",
                "ok": True,
                "failures": list(vacuous.failures),
                "coverage_pct": vacuous.coverage_pct,
            }
        )

    payload = {"failed": failed, "rows": rows}
    print(json.dumps(payload, sort_keys=True))
    if failed:
        print("FAILED:IMP-0168-probe1 construct-accounting")
        return 1
    print("SUCCESS:IMP-0168-probe1 construct accounting == 100% on all fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""IMP-0168 probe1: construct accounting sums to 100 percent on ALL fixtures
(computed); a clean fixture justifies its empty ledger; an inexpressible one does
not; and the silent-drop mutant fails accounting (detector fires on the broken
state, both-states discipline).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import inventory_file  # noqa: E402
from ledger import account, translate, translate_silent_drop  # noqa: E402

FIXTURES = HERE / "fixtures"
CLEAN = {"claude_clean.mjs", "codex_clean.json", "dag_clean.json"}


def main() -> int:
    checks = {}
    rows = []
    for path in sorted(FIXTURES.iterdir()):
        if path.suffix not in {".mjs", ".json"}:
            continue
        inv = inventory_file(path)
        t = translate(inv)
        a = account(inv, t)
        clean = path.name in CLEAN
        rows.append({
            "fixture": path.name,
            "coverage_pct": a["coverage_pct"],
            "source_count": a["source_count"],
            "preserved_count": a["preserved_count"],
            "lost_count": a["lost_count"],
            "unaccounted_ids": a["unaccounted_ids"],
            "empty_ledger_justified": a["empty_ledger_justified"],
            "accounting_ok": a["ok"],
        })
        checks["coverage100_" + path.stem] = abs(a["coverage_pct"] - 100.0) < 1e-9
        checks["ok_" + path.stem] = a["ok"]
        if clean:
            checks["empty_justified_" + path.stem] = (
                a["empty_ledger_justified"] and a["lost_count"] == 0
            )
        else:
            checks["lost_loud_" + path.stem] = a["lost_count"] >= 1
            checks["not_justified_empty_" + path.stem] = a["empty_ledger_justified"] is False

        # both-states: the silent-drop mutant must FAIL accounting on lossy sources
        mut = account(inv, translate_silent_drop(inv))
        if clean:
            checks["mutant_harmless_on_clean_" + path.stem] = mut["ok"] is True
        else:
            checks["mutant_fails_on_lossy_" + path.stem] = (
                mut["ok"] is False and len(mut["unaccounted_ids"]) == a["lost_count"]
            )

    out = {
        "unit_id": "IMP-0168",
        "probe": "probe1-accounting",
        "fixtures": rows,
        "all_coverage_100": all(abs(r["coverage_pct"] - 100.0) < 1e-9 for r in rows),
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0168-probe1 construct accounting is 100 percent on all six fixtures; clean ledgers justified empty; silent-drop mutant fails accounting on every lossy fixture")
        return 0
    print("FAILED:IMP-0168-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

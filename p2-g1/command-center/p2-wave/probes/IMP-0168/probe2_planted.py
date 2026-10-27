"""IMP-0168 probe2 (separate process, mechanically different): the detector fires on
the broken state. A PLANTED inexpressible construct appears in the ledger with
load_bearing True; the clean twin yields a justified EMPTY ledger; the silent-drop
mutant of translate() fails account(); and an ast scan confirms production
translate() carries no silent-drop branch.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from inventory import Construct, Inventory, inventory_file  # noqa: E402
from ledger import account, translate, translate_silent_drop  # noqa: E402

CLEAN = HERE / "fixtures" / "claude_clean.mjs"


def main() -> int:
    checks = {}

    # clean twin: EMPTY ledger, justified
    inv_clean = inventory_file(CLEAN)
    t_clean = translate(inv_clean)
    a_clean = account(inv_clean, t_clean)
    checks["clean_twin_empty_ledger"] = len(t_clean.lost) == 0
    checks["clean_twin_justified_empty"] = a_clean["empty_ledger_justified"] is True

    # planted inexpressible construct on top of the clean twin
    planted = Construct(
        id="claude_clean:planted-raw-escape",
        kind="raw-escape",
        span="planted:99",
        construct="runRaw('rm -rf target')",
    )
    inv_planted = Inventory(
        adapter_shape=inv_clean.adapter_shape,
        source=inv_clean.source,
        constructs=inv_clean.constructs + (planted,),
    )
    t = translate(inv_planted)
    a = account(inv_planted, t)
    planted_rows = [r for r in t.lost if r.construct_id == planted.id]
    checks["planted_in_ledger"] = len(planted_rows) == 1
    checks["planted_load_bearing_true"] = bool(
        planted_rows and planted_rows[0].load_bearing is True
    )
    checks["planted_has_reason_and_span"] = bool(
        planted_rows
        and planted_rows[0].reason
        and planted_rows[0].span == "planted:99"
    )
    checks["planted_accounting_still_100"] = abs(a["coverage_pct"] - 100.0) < 1e-9
    checks["empty_ledger_refused_when_lossy"] = a["empty_ledger_justified"] is False

    # silent-drop mutant of translate() must fail account() on the planted source
    mut = account(inv_planted, translate_silent_drop(inv_planted))
    checks["mutant_fails_account"] = (
        mut["ok"] is False and planted.id in mut["unaccounted_ids"]
    )

    # ast scan: production translate() has no drop-only branch (every non-preserved
    # construct reaches a lost.append)
    src = (HERE / "ledger.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "translate")
    calls_append = any(
        isinstance(n, ast.Attribute) and n.attr == "append" and isinstance(n.value, ast.Attribute) and n.value.attr == "lost"
        for n in ast.walk(fn)
    )
    checks["ast_translate_writes_ledger"] = calls_append

    out = {
        "unit_id": "IMP-0168",
        "probe": "probe2-planted",
        "clean_twin": {"lost": 0, "justified_empty": a_clean["empty_ledger_justified"]},
        "planted_row": {
            "construct_id": planted.id,
            "kind": planted.kind,
            "span": "planted:99",
            "load_bearing": planted_rows[0].load_bearing if planted_rows else None,
            "reason": planted_rows[0].reason if planted_rows else None,
        },
        "mutant_unaccounted": mut["unaccounted_ids"],
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0168-probe2 planted inexpressible construct lands in the ledger with load_bearing true; clean twin justifies an empty ledger; silent-drop mutant fails accounting")
        return 0
    print("FAILED:IMP-0168-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

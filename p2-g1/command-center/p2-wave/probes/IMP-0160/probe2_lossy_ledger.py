#!/usr/bin/env python3
"""IMP-0160 probe2: constructs the agentspec target language cannot express
(wall-clock Date.now, fire-and-forget agent()) are RECORDED in the import
ledger as load_bearing and expressed=False - never silently dropped.

Fixtures live beside this probe under fixtures/; the clean baseline
(rt-vp-pdr.js, no such constructs) imports with an empty ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
for p in ("tools/agentspec", "tools/import-adapters"):
    sys.path.insert(0, str(REPO / p))

from claude_saved_workflow import import_path  # noqa: E402

CLEAN = REPO / "workflows" / "rtv-pdr.js"


def main() -> int:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "inexpressible-date-now.js").write_text(
        "// inexpressible: wall-clock dependency\n"
        "export const meta = { name: 'date-now' };\n"
        "const stamp = Date.now();\n"
        "export const run = () => stamp;\n",
        encoding="utf-8",
    )
    (FIX / "inexpressible-fire-and-forget.js").write_text(
        "// inexpressible: unawaited fan-out\n"
        "export const meta = { name: 'fire-and-forget' };\n"
        "const agent = () => ({ promised: true });\n"
        "export const run = () => { agent('rollout'); };\n",
        encoding="utf-8",
    )

    def ledger_kinds(src: Path) -> list[str]:
        res = import_path(src)
        return sorted(e.kind for e in (res.ledger or []) if e.load_bearing and not e.expressed)

    clean = ledger_kinds(CLEAN)
    d1 = ledger_kinds(FIX / "inexpressible-date-now.js")
    d2 = ledger_kinds(FIX / "inexpressible-fire-and-forget.js")

    result = {
        "unit_id": "IMP-0160",
        "probe": "probe2-lossy-ledger",
        "clean_baseline_ledger": clean,
        "date_now_recorded": "date-now" in d1,
        "fire_forget_recorded": "fire-forget" in d2,
        "inexpressible_ledgers": {"date-now": d1, "fire-and-forget": d2},
        "pass": clean == [] and "date-now" in d1 and "fire-forget" in d2,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0160-probe2 inexpressible constructs recorded load-bearing/expressed=False; "
            "clean baseline ledger empty"
            if result["pass"] else
            "FAILED:IMP-0160-probe2 lossy-ledger contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

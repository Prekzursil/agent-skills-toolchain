#!/usr/bin/env python3
"""Probe 2: per-session budget REFUSES the next activation.

Both-states: production enforce_budget=True refuses the second MCP mount
and does not spawn it; a warn-only mutant materializes it. Under-budget
skill activation still succeeds. Resident set is unchanged across the
refusal.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gateway as G  # noqa: E402

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT", str(HERE.parents[3])))
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def main() -> int:
    result = G.check_budget_refuse()
    print(json.dumps(result, indent=2, sort_keys=True))
    if DESIGN.is_file():
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        on_exh = (
            ((design.get("budget") or {}).get("on_exhaustion"))
            or ((design.get("per_session_budget") or {}).get("on_exhaustion"))
        )
        if str(on_exh).upper() != "REFUSE":
            print(f"FAILED:ARC-0024-probe2 DESIGN on_exhaustion={on_exh!r} not REFUSE")
            return 1
        print("design on_exhaustion=REFUSE")
    if not result.get("ok"):
        print("FAILED:ARC-0024-probe2 budget refuse")
        return 1
    print("SUCCESS:ARC-0024-probe2 budget REFUSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

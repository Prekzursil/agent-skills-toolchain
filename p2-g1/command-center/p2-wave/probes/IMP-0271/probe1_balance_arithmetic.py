"""IMP-0271 probe 1: balance arithmetic across the five mixes.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0271/probe1_balance_arithmetic.py
Exit 0 iff the live tools/council/participants/select_stakeholder seats each
mix to its hand-computed target census (including the Hamilton leftover and
alphabetical tie-break cases), and the unfillable regulator mix reports the
shortfall in unfilled_report (shortfall=2) instead of proceeding silently.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "participants"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixtures import MIXES  # type: ignore  # noqa: E402
from select_stakeholder import select  # type: ignore  # noqa: E402

rows = []
for mix in MIXES:
    run = select(mix["pool"], **mix["select"])
    census = {c: run["census"].get(c, 0) for c in ("operator", "end_user", "domain_expert", "adversary", "regulator")}
    unf = [
        {"stakeholder_class": u["stakeholder_class"], "requested": u["requested"],
         "seated": u["seated"], "shortfall": u["shortfall"]}
        for u in run["unfilled_report"]
    ]
    ok = (
        census == mix["expected_seats"]
        and unf == mix["expected_unfilled"]
        and run["unfilled_report_emitted"] is True
        and run["under_represented"] == bool(mix["expected_unfilled"])
    )
    rows.append({"id": mix["id"], "census": census, "unfilled_report": unf, "pass": ok})

checks = {
    "all_mix_censuses_match": all(r["pass"] for r in rows),
    "mix4_shortfall_named": any(
        r["id"] == "MIX-4-unfillable-regulator"
        and any(u["stakeholder_class"] == "regulator" and u["shortfall"] == 2 for u in r["unfilled_report"])
        for r in rows
    ),
    "mix3_tie_break_adversary_before_regulator": next(
        r["census"]["adversary"] == 1 and r["census"]["regulator"] == 1
        for r in rows if r["id"] == "MIX-3-hamilton-double-tie"
    ),
}
ok = all(checks.values()) and all(r["pass"] for r in rows)
out = {"probe": "probe1-balance-arithmetic", "unit_id": "IMP-0271",
       "rows": rows, "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-balance.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0271-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0271-probe1 five-mix balance arithmetic matches hand-computed censuses; shortfall reported")

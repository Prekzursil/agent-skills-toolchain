#!/usr/bin/env python3
"""BLD-0013 probe 2 (SATISFIES re-read, live): for sampled SATISFIES verdicts,
re-read the demanded mechanism from the cited catalog line and the bound unit's
target from the catalog itself, then re-derive the verdict. The re-derivation
must agree with the recorded verdict - the reviewer's method, re-run live."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0013.json"
UNIT = "BLD-0013"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SAMPLE_N = 5


def tokens(s) -> set[str]:
    return set(re.findall(r"[a-z0-9_.:/-]{4,}", str(s or "").lower()))


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))
    rows = [r for r in (doc.get("classifications") or []) if isinstance(r, dict)]
    cat_lines = CATALOG.read_text(encoding="utf-8").splitlines()
    wus = {u.get("id"): u for u in
           json.loads(CATALOG.read_text(encoding="utf-8")).get("work_units", [])
           if isinstance(u, dict)}

    sat = [r for r in rows if r.get("verdict") == "SATISFIES"][:SAMPLE_N]
    if not sat:
        print(f"FAILED:{UNIT}-probe2 no SATISFIES rows recorded")
        return 1
    report = []
    ok = True
    for r in sat:
        anc = str(r.get("demanded_anchor") or "")
        p, _, line_s = anc.rpartition(":")
        line = int(line_s) if line_s.isdigit() else -1
        demand_text = cat_lines[line - 1] if 1 <= line <= len(cat_lines) else ""
        unit = wus.get(r.get("bound_unit_id") or "")
        target = json.dumps(unit.get("question_or_target"), ensure_ascii=False) \
            if unit else ""
        need = (r.get("matched_disjunct") or [r.get("demanded_mechanism_quote")])
        have = tokens(demand_text) | tokens(target)
        covered = [d for d in need if tokens(d) and tokens(d) <= have]
        missing = sorted(tokens(" ".join(need)) - have)
        derived = "SATISFIES" if covered else "MIS-BOUND"
        row_ok = derived == "SATISFIES" and r.get("verdict") == "SATISFIES"
        if not row_ok:
            ok = False
        report.append({
            "requirement_id": r.get("requirement_id"),
            "bound_unit_id": r.get("bound_unit_id"),
            "derived": derived,
            "recorded": r.get("verdict"),
            "missing_tokens": missing[:8],
            "ok": row_ok,
        })

    out = {
        "unit_id": UNIT,
        "probe": "probe2-satisfies-reread",
        "sampled": len(sat),
        "rows": report,
        "pass": bool(ok and sat),
    }
    (HERE / "probe2_satisfies_reread_out.json").write_text(json.dumps(out, indent=1),
                                                           encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 {len(sat)} SATISFIES verdicts re-derived "
              "from spec line + unit target live; all agree")
        return 0
    print(f"FAILED:{UNIT}-probe2 re-derivation disagreement on sampled rows")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

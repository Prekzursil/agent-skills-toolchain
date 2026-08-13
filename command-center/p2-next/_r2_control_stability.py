"""ROUND-2 detector control, BOTH STATES, for the new STABILITY check and the new ladder.

The fixed resolver prints "STABILITY: 52 units classified at BOTH 899ff779^ and HEAD; 0 moved".
Silence proves nothing until the same instrument FIRES on the known-broken state. So:

  STATE BROKEN : monkeypatch the v2 ladder (rule D inverts unconditionally, no rule A2) back into
                 the module and re-run the identical stability_check. It MUST report the 6 AUD
                 units as moved -- that is the defect the auditor confirmed.
  STATE FIXED  : the shipped ladder. It MUST report 0 moved.

Also asserts the two hypotheses are distinguishable at the COUNT level (rule 3c): the check reports
a count of the thing being compared (units classified at both revisions), and fails closed below 40.

Prints the SATISFIABLE id set on both bases so the set -- not just the count -- is on the record.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "command-center" / "p2-next" / "vendor_satisfiability.py"

spec = importlib.util.spec_from_file_location("vs", MOD)
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

out = {}

# ---------------- STATE FIXED ----------------
fixed_rows = vs.load_units("committed")
print("=== STATE FIXED (shipped ladder) ===")
fixed_problems = vs.stability_check(fixed_rows)
fixed_sat = sorted(r["id"] for r in fixed_rows if r["verdict"] == vs.SAT)
fixed_rail = sorted(r["id"] for r in fixed_rows if r["verdict"] == vs.BLOCKED_RAIL)
print(f"  blocked={len(fixed_rows)} rail={len(fixed_rail)} sat={len(fixed_sat)}")
print(f"  SATISFIABLE ids: {fixed_sat}")

wt_rows = vs.load_units("worktree")
wt_sat = sorted(r["id"] for r in wt_rows if r["verdict"] == vs.SAT)
wt_rail = sorted(r["id"] for r in wt_rows if r["verdict"] == vs.BLOCKED_RAIL)
print(f"  worktree basis: blocked={len(wt_rows)} rail={len(wt_rail)} sat={len(wt_sat)}")
print(f"  worktree SATISFIABLE ids identical to committed: {wt_sat == fixed_sat}")

# ---------------- STATE BROKEN ----------------
V2_RULES = re.compile(r"never-used", re.I)  # placeholder so the intent is explicit


def resolve_v2(blocked_on, reviewer_notes, req, produced):
    """The REFUTED v2 ladder, verbatim in behaviour: no rule A2, rule D inverts unconditionally."""
    produced = (produced or "anthropic").lower()
    if vs.CONTRADICTORY_REQ.search(req or "") and produced == "anthropic":
        return "openai", "0"
    v = vs.named_vendor(blocked_on)
    if v:
        return v, "A"
    m = re.search(
        r"qualif\w*\s+(?:refuter|reviewer)\s+is\s+([^.,;]{0,40})",
        reviewer_notes or "",
        re.I,
    )
    if m:
        v = vs.named_vendor(m.group(1))
        if v:
            return v, "B"
    if vs.RELATIVE_PAT.search(req or ""):
        return vs.other(produced), "C"
    v = vs.named_vendor(req or "")
    if v:
        if v == produced:
            return vs.other(produced), "D:unconditional-invert"
        return v, "D"
    if vs.VENDOR_ANY.search(req or ""):
        return vs.other(produced), "E"
    if vs.REVIEW_ANY.search(req or ""):
        return "any", "F"
    return "any", "F"


print("\n=== STATE BROKEN (v2 ladder monkeypatched back in) ===")
real = vs.resolve
vs.resolve = resolve_v2
try:
    broken_rows = vs.load_units("committed")
    broken_problems = vs.stability_check(broken_rows)
    broken_sat = sorted(r["id"] for r in broken_rows if r["verdict"] == vs.SAT)
    broken_rail = [r["id"] for r in broken_rows if r["verdict"] == vs.BLOCKED_RAIL]
    print(f"  blocked={len(broken_rows)} rail={len(broken_rail)} sat={len(broken_sat)}")
    print(f"  SATISFIABLE ids: {broken_sat}")
finally:
    vs.resolve = real

fires = len(broken_problems) > 0
silent = len(fixed_problems) == 0
print(
    f"\nCONTROL fires_on_v2={fires} ({len(broken_problems)} moved) silent_on_fixed={silent}"
)
print(f"  v2 moved units: {[p.split(':')[0] for p in broken_problems]}")

out = {
    "fixed": {
        "committed": {
            "blocked": len(fixed_rows),
            "rail": len(fixed_rail),
            "sat": fixed_sat,
        },
        "worktree": {"blocked": len(wt_rows), "rail": len(wt_rail), "sat": wt_sat},
        "stability_problems": fixed_problems,
    },
    "broken_v2": {
        "committed": {
            "blocked": len(broken_rows),
            "rail": len(broken_rail),
            "sat": broken_sat,
        },
        "stability_problems": broken_problems,
    },
    "control": {"fires_on_v2": fires, "silent_on_fixed": silent},
}
(REPO / "command-center/p2-next/R2-CONTROL-STABILITY.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
ok = fires and silent
print("SUCCESS:r2-control-stability" if ok else "FAILED:r2-control-stability")
raise SystemExit(0 if ok else 1)

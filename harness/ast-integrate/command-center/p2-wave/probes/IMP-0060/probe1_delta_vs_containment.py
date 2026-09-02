"""Named probe 1: lattice delta vs independent raw set-containment.

Catalog evidence: the computed delta for a widening pair, a narrowing pair and
an unchanged pair, plus an independent set-containment check over the raw
permission sets reproducing the same three verdicts. Disagreement is a lattice
bug.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import permission_diff as pd  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0060.json"
PAIRS = {
    "widen": pd.WIDEN_PAIR,
    "narrow": pd.NARROW_PAIR,
    "unchanged": pd.UNCHANGED_PAIR,
}
EXPECTED = {"widen": pd.WIDEN, "narrow": pd.NARROW, "unchanged": pd.UNCHANGED}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0060-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0060" not in text:
        print("FAILED:IMP-0060-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0060-probe1 self-declared", doc.get("state"))
        return 1

    rows = []
    for name, (inst, cand) in PAIRS.items():
        delta = pd.compute_delta(inst, cand)
        raw = pd.raw_set_verdict(inst, cand)
        lat = pd.lattice_verdict(inst, cand)
        want = EXPECTED[name]
        agree = lat == raw == want == delta.verdict
        if not delta.lattice_atom_agree:
            print(f"FAILED:IMP-0060-probe1 lattice/atom disagreement on {name}")
            print(json.dumps(delta.__dict__, default=str)[:2000])
            return 1
        if not agree:
            print(f"FAILED:IMP-0060-probe1 signal disagreement on {name}")
            print(json.dumps({"lattice": lat, "raw": raw, "want": want}, indent=2))
            return 1
        rows.append(
            {
                "pair": name,
                "installed": inst,
                "candidate": cand,
                "lattice": lat,
                "raw_set_containment": raw,
                "atom_containment": delta.atom_verdict,
                "added": delta.added,
                "removed": delta.removed,
                "agree": True,
            }
        )

    # Reorder-only pair is UNCHANGED under both methods.
    inst_r, cand_r = pd.UNCHANGED_PAIR
    if list(inst_r) == list(cand_r):
        print("FAILED:IMP-0060-probe1 reorder fixture is not a reorder")
        return 1
    if pd.compute_delta(inst_r, cand_r).verdict != pd.UNCHANGED:
        print("FAILED:IMP-0060-probe1 reorder classified as change")
        return 1

    out = {
        "probe": "probe1-delta-vs-containment",
        "unit_id": "IMP-0060",
        "pass": True,
        "pairs": rows,
        "two_independent_signals": True,
        "methods": [
            "lattice covers() delta",
            "raw canonical-string set containment (no glob expansion)",
        ],
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0060-probe1 lattice delta agrees with raw set-containment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

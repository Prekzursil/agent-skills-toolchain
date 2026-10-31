#!/usr/bin/env python3
"""RES-0102 independent re-derivation: control-row zero-delta + NC mutant."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0102"

def control_delta(doc):
    rows = doc.get("ablation_delta_table") or []
    full = next((r for r in rows if r.get("component") == "full"), None)
    ctrl = [r for r in rows if r.get("is_control")]
    if not full or not ctrl:
        return None
    acc = ctrl[0]["n_correct"] / ctrl[0]["n_tasks"]
    return acc - float(full["accuracy"])

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    d0 = control_delta(doc)
    c.append(("recomputed control delta is exactly zero", d0 == 0.0, f"delta={d0}"))
    defs = doc.get("components_with_no_measured_effect") or []
    c.append(("zero-effect components recorded explicitly", len(defs) >= 1, f"{defs}"))

    def mutate(d):
        for r in d["ablation_delta_table"]:
            if r.get("is_control"):
                r["n_correct"] = int(r["n_correct"]) + 3  # control moves: no longer ~0
        return d

    mp = L.mutation_copy(doc, mutate)
    try:
        mdoc = json.loads(mp.read_text(encoding="utf-8"))
        fired = control_delta(mdoc) != 0.0
        c.append(("NC: control improvement breaks the approximately-zero control", fired,
                  f"mutant delta={control_delta(mdoc)}"))
    finally:
        mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""RES-0086 gate-rule mutants must fire; delivered table must stay silent."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L
from importlib import import_module
P1 = import_module("RES-0086_probe1") if False else None

def gate_rule(doc):
    # second, independently written implementation of the same rule
    v = []
    for r in doc.get("mechanism_table") or []:
        rid, cls = str(r.get("id")), str(r.get("enforcement_classification"))
        fld = str(r.get("checkable_artifact_field") or "").strip().lower()
        rec = bool(r.get("recommended_as_gate"))
        if rec and (not fld or fld == "none"):
            v.append(rid + ":recommended-without-checkable-field")
        if cls == "norm-dependent" and rec:
            v.append(rid + ":norm-dependent-recommended-as-gate")
    return v

def main() -> int:
    c = []
    p, doc, text = L.load_artifact("RES-0086")
    c.append(("delivered table passes the recomputed rule", not gate_rule(doc),
              f"violations={gate_rule(doc)[:3]}"))

    def mut_norm_as_gate(d):
        for r in d["mechanism_table"]:
            if str(r.get("id") or "").startswith("M6"):
                r["recommended_as_gate"] = True
        return d

    def mut_empty_field(d):
        for r in d["mechanism_table"]:
            if str(r.get("id") or "").startswith("M1"):
                r["checkable_artifact_field"] = ""
        return d

    for name, mut in (("norm-dependent recommended as gate", mut_norm_as_gate),
                      ("structurally-enforced with empty checkable field", mut_empty_field)):
        mp = L.mutation_copy(doc, mut)
        try:
            mdoc = json.loads(mp.read_text(encoding="utf-8"))
            fired = bool(gate_rule(mdoc))
            c.append((f"NC mutant ({name}) fires the gate rule", fired,
                      f"mutant violations={gate_rule(mdoc)[:3]}"))
        finally:
            mp.unlink(missing_ok=True)
    return L.finish("RES-0086", "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())

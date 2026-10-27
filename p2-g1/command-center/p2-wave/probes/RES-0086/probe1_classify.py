#!/usr/bin/env python3
"""RES-0086 delivery predicate: enforcement classification + gate rule.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0086"

def gate_rule(doc):
    """Recomputed rule: only structurally-enforced mechanisms may be
    recommended as gates, and must name a checkable artifact field."""
    v = []
    for r in doc.get("mechanism_table") or []:
        rid = str(r.get("id"))
        cls = str(r.get("enforcement_classification"))
        fld = str(r.get("checkable_artifact_field") or "").strip()
        rec = bool(r.get("recommended_as_gate"))
        pres = bool(r.get("preserves_minority"))
        if cls == "structurally-enforced":
            if not fld or fld == "none":
                v.append(rid + ":recommended-without-checkable-field")
        if cls == "norm-dependent":
            if rec:
                v.append(rid + ":norm-dependent-recommended-as-gate")
        if rec and not pres:
            v.append(rid + ":non-preserving-recommended-as-gate")
    return v

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    mt = doc.get("mechanism_table") or []
    allowed = {"structurally-enforced", "norm-dependent"}
    c.append(("every mechanism classified structurally-enforced vs norm-dependent",
              len(mt) >= 6 and all(r.get("enforcement_classification") in allowed for r in mt),
              f"{len(mt)} rows"))
    v = gate_rule(doc)
    c.append(("recomputed gate rule: zero violations on the delivered table", not v,
              f"violations={v[:4]}"))
    se = [str(r.get("id")) for r in mt if r.get("enforcement_classification") == "structurally-enforced"]
    c.append(("each structurally-enforced row names a concrete checkable field",
              all(str(r.get("checkable_artifact_field") or "").strip() not in ("", "none")
                  for r in mt if r.get("enforcement_classification") == "structurally-enforced"),
              f"structural={se}"))
    nd = [str(r.get("id")) for r in mt if r.get("enforcement_classification") == "norm-dependent"]
    c.append(("no norm-dependent row recommended as gate",
              not [r for r in mt if r.get("enforcement_classification") == "norm-dependent"
                   and r.get("recommended_as_gate")], f"norm-dependent={nd}"))
    hg = doc.get("hard_gate") or {}
    c.append(("hard-gate block names a concrete artifact field and predicate",
              bool(hg.get("artifact_field")) and bool(str(hg.get("predicate") or "").strip()),
              f"field={hg.get('artifact_field')} derived={len(hg.get('derived_from') or [])}"))
    nc = doc.get("negative_controls") or []
    ok_nc = any((n.get("bad_state_output") or {}).get("empty_field_violations")
                and (n.get("bad_state_output") or {}).get("norm_as_gate_violations")
                for n in nc if isinstance(n.get("bad_state_output"), dict))
    c.append(("recorded mutants carry empty-field + norm-as-gate violations", ok_nc,
              f"n_controls={len(nc)}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())

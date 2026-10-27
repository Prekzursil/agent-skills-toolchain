#!/usr/bin/env python3
"""Run the program's canonical receipt gate (receipt_schema_gate.evaluate_full:
Layer 1 schema vs platform/schema/receipt.schema.json + Layer 2 12-condition
predicate + coherence) on the 12 shard18-w4 units, with the fragment derived
from each unit's catalog output_schema via the gate's own parse_schema_ref.
Read-only: prints markers, writes a results file in this reviewer dir.
"""
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as gate  # noqa: E402

UNITS = ["TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
         "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138"]


def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    cmap = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and "id" in u}
    out = []
    for uid in UNITS:
        unit = cmap[uid]
        receipt = json.loads((REPO / unit["output_path"]).read_text(encoding="utf-8"))
        _base, frag = gate.parse_schema_ref(unit.get("output_schema") or "")
        fragment = frag.lstrip("#/").replace("$defs/", "") if frag else None
        result, extra = gate.evaluate_full(
            receipt, repo_root=str(REPO), verify_filesystem=True, fragment=fragment)
        d = result.to_dict()
        unsat = [c for c in d["conditions"] if c["outcome"] != "SATISFIED"]
        out.append({
            "unit_id": uid,
            "fragment": fragment,
            "state": d.get("state"),
            "complete": d.get("complete"),
            "marker": result.marker(),
            "schema_errors": d.get("schema_errors", []),
            "unsat_conditions": unsat,
            "coherence_problems": extra,
        })
        print("%s complete=%s state=%s frag=%s schema_err=%d unsat=%d coherence=%d" % (
            uid, d.get("complete"), d.get("state"), fragment,
            len(d.get("schema_errors", [])), len(unsat), len(extra)))
        for c in unsat:
            print("    cond %s [%s] %s -> %s" % (c["n"], c["outcome"], c["text"][:60], str(c["basis"])[:140]))
        for e in d.get("schema_errors", [])[:6]:
            print("    schema-err:", e[:150])
        for p in extra:
            print("    coherence:", str(p)[:160])
    (Path(__file__).parent / "gate-results.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

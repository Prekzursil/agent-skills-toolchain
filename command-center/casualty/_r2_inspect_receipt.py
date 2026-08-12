"""Inspect the ADV-0021 receipt: mitigated cells, routing of unmitigated cells,
and any prose field that carries the two overclaims the audit confirmed."""
import json
from pathlib import Path

CAS = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/casualty")
P = CAS / "ADV-0021-install-path-stride-threat-model.json"
doc = json.loads(P.read_text(encoding="utf-8"))

print("TOP-LEVEL KEYS:", sorted(doc.keys()))
rep = doc.get("report") or {}
print("REPORT KEYS:", sorted(rep.keys()))

cells = None
for holder, key in ((rep, "stride_matrix"), (doc, "stride_matrix"), (rep, "cells")):
    if isinstance(holder.get(key), list):
        cells = holder[key]
        print(f"cells found at {'report' if holder is rep else 'root'}.{key}: {len(cells)}")
        break
if cells is None:
    print("NO CELLS FOUND — dumping report shape")
    for k, v in rep.items():
        print(" ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") else ""))
    raise SystemExit(1)

print("\nCELL KEYS:", sorted(cells[0].keys()))
mit = [c for c in cells if c.get("status") == "mitigated"]
print(f"\n=== {len(mit)} MITIGATED CELLS ===")
for c in mit:
    print(json.dumps(c, indent=2)[:2600])
    print("-" * 60)

unmit = [c for c in cells if c.get("status") == "unmitigated"]
routed, unrouted = [], []
for c in unmit:
    blob = json.dumps(c)
    (routed if "ADV-00" in blob.replace(doc.get("unit_id", "ADV-0021"), "") else unrouted).append(c)
print(f"\nunmitigated={len(unmit)} routed={len(routed)} unrouted={len(unrouted)}")
for c in unrouted:
    print("  UNROUTED:", c.get("boundary_id"), c.get("stride"),
          "| disposition:", str(c.get("disposition"))[:220])

print("\n=== tests_required_closure ===")
print(json.dumps(rep.get("tests_required_closure"), indent=2)[:1500])
print("\n=== stride_status_counts ===")
print(json.dumps(rep.get("stride_status_counts"), indent=2))

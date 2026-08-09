"""Print a compact per-candidate digest so the registry rows can be authored
from measured content rather than from the prior doc's prose."""

import json

with open("command-center/_wfa1_deep_scan.json", encoding="utf-8") as fh:
    R = json.load(fh)

for r in R:
    print("=" * 100)
    print(f"[{r['n']:>2}] {r['id']}   ({r['family']})  kind={r['kind']}")
    print(f"     name        : {r['name']}")
    print(f"     prior class : {r['classification']}")
    print(f"     prov        : {r['provenance_claim']}")
    print(f"     lines       : {r['measured_lines']}  chars={r.get('measured_chars')}")
    if r.get("tree_file_count"):
        print(f"     tree        : {r['tree_file_count']} files / {r['tree_total_bytes']} bytes")
        print(f"     paths       : {r.get('tree_paths')}")
    if r.get("phase_names"):
        print(f"     phases      : {r['phase_names']}")
    sc = r.get("scan") or {}
    nz = {k: v for k, v in sc.items() if v}
    print(f"     scan        : {nz}")
    print(f"     prior does  : {r.get('prior_does')}")
    print(f"     prior mech  : {r.get('prior_mechanisms')}")
    print(f"     prior evid  : {(r.get('prior_evidence') or '')[:400]}")
    print(f"     prior notes : {(r.get('prior_notes') or '')[:400]}")
    print("     --- head ---")
    for ln in (r.get("body_head") or "").splitlines()[:26]:
        print("      | " + ln[:150])

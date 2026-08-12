"""Print the schema requirements and one exemplar of each array I intend to append to,
so a round-2 addition cannot invent a shape the gate will reject."""
import json
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
CAS = ROOT / "command-center" / "casualty"
SCH = ROOT / "command-center" / "schema"

for s in ("threat-model.schema.json", "exploit-proof.schema.json"):
    doc = json.loads((SCH / s).read_text(encoding="utf-8"))
    print(f"\n########## {s}")
    print("required:", doc.get("required"))
    props = doc.get("properties", {})
    for key in ("evidence", "defects", "residual_unknowns", "extensions", "report", "tests",
                "negative_controls"):
        if key in props:
            p = props[key]
            item = p.get("items", {})
            print(f"  {key}: type={p.get('type')} item_required={item.get('required')} "
                  f"item_props={sorted((item.get('properties') or {}).keys())}"
                  f"{' additionalProperties=' + str(item.get('additionalProperties')) if 'additionalProperties' in item else ''}")
    print("  additionalProperties:", doc.get("additionalProperties"))

d = json.loads((CAS / "ADV-0022-declared-permission-escape.json").read_text(encoding="utf-8"))
print("\n########## ADV-0022 exemplars")
print("defects[0]:", json.dumps(d["defects"][0], indent=1)[:900])
print("n_defects:", len(d["defects"]), " n_evidence:", len(d["evidence"]))
ev = dict(d["evidence"][0])
for p in ev.get("probes", []):
    if "raw_output" in p:
        p["raw_output"] = f"<{len(p['raw_output'])} B elided for this dump>"
print("evidence[0]:", json.dumps(ev, indent=1)[:1400])
print("extensions keys:", sorted(d["extensions"].keys()))
print("residual_unknowns[0]:", json.dumps(d.get("residual_unknowns", [None])[0], indent=1)[:700])

d21 = json.loads((CAS / "ADV-0021-install-path-stride-threat-model.json").read_text(encoding="utf-8"))
print("\n########## ADV-0021")
print("extensions keys:", sorted(d21["extensions"].keys()))
print("n_residual_unknowns:", len(d21.get("residual_unknowns", [])))
for r in d21.get("residual_unknowns", []):
    t = json.dumps(r)
    if "safe_join" in t or "deploy" in t:
        print("  DEPLOY-RELATED residual:", t[:600])

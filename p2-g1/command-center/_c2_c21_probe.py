"""Lane C2 read-only probe for scorecard condition 21 (and 2c). Writes nothing but stdout."""

import json
import os

SEP = chr(92)  # backslash, kept out of a literal to survive shell transports

cat = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
units = cat.get("work_units") or []
print("work_units", len(units))

man = json.load(open("command-center/ARTIFACT-MANIFEST.json", encoding="utf-8"))
mpaths = {a["path"].replace(SEP, "/") for a in man["artifacts"]}
print("manifest paths", len(mpaths))

outs = [u.get("output_path") for u in units]
nonempty = [o for o in outs if o]
norm = {o.replace(SEP, "/") for o in nonempty}
print("with non-empty output_path", len(nonempty), "distinct", len(norm))

inter = norm & mpaths
print("INTERSECTION with manifest:", len(inter), sorted(inter)[:5])

ctrl = (norm | {"command-center/STATUS.md"}) & mpaths
print("CONTROL (inject command-center/STATUS.md) ->", len(ctrl), sorted(ctrl))

exist = [o for o in nonempty if os.path.exists(o)]
print("EXIST at declared output_path:", len(exist), exist[:8])

blob = [u for u in units if "tools/marketplace" in json.dumps(u)]
print("units referencing tools/marketplace:", len(blob))
sch = set()
for u in blob:
    s = u.get("output_schema")
    if isinstance(s, str):
        sch.add(s)
print("distinct output_schema tokens naming tools/marketplace:", len(sch))
for s in sorted(sch):
    head = s.split("#")[0]
    print("   ", s, "exists=", os.path.exists(head))

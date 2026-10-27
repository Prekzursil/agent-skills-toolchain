"""Second instrument: validate each receipt against its catalog-declared
output_schema shim VERBATIM via native jsonschema referencing (file:// auto
retrieval), with NO custom inlining. Cross-checks battery.py A5."""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))
from referencing import Registry, Resource  # noqa: E402
from referencing.jsonschema import DRAFT202012  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

IDS = ["IMP-0430", "IMP-0435", "IMP-0437", "IMP-0439", "IMP-0442", "IMP-0448",
       "IMP-0450", "IMP-0460", "IMP-0466", "IMP-0467", "IMP-0468", "IMP-0470"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
WU = {u.get("id"): u for u in cat["work_units"]}


def load(url: str):
    if url.startswith("file:///"):
        p = Path(url[len("file:///"):].replace("/", "\\"))
        if not p.is_file():
            # map the foreign absolute base onto THIS checkout (verified
            # byte-identical earlier: schema + profiles + gate)
            rel = p.relative_to(r"C:\Users\Prekzursil\source\ast-integrate")
            p = REPO / rel
        return json.loads(p.read_text(encoding="utf-8"))
    raise RuntimeError(url)


reg = Registry(retrieve=lambda url: Resource.from_contents(load(url), default_specification=DRAFT202012))

bad = 0
for uid in IDS:
    entry = WU[uid]
    shim_rel = entry["output_schema"]
    shim_path = REPO / shim_rel
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    ref = shim["$ref"]  # absolute file:///...#$defs/<class>
    validator = Draft202012Validator({"$ref": ref}, registry=reg)
    doc = json.loads((REPO / entry["output_path"]).read_text(encoding="utf-8"))
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        bad += 1
        print(uid, "SCHEMA-FAIL", shim_rel)
        for e in errs[:4]:
            print("   ", "/".join(map(str, e.absolute_path)) or "<root>", "::", e.message[:160])
    else:
        print(uid, "SCHEMA-OK", shim_rel)
print("NATIVE-SCHEMA-DONE failures=%d" % bad)

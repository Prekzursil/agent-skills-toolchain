import json
from pathlib import Path
from urllib.parse import unquote, urlparse
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = ["IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442","IMP-0448",
       "IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468","IMP-0470"]
cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}

def retrieve(uri):
    path = unquote(urlparse(uri).path).lstrip("/")
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return Resource.from_contents(doc, default_specification=DRAFT202012)

def build_validator(shim_path):
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    ref = shim["$ref"]
    base, frag = ref.split("#", 1)
    phys_path = ROOT / unquote(urlparse(base).path).lstrip("/").split("source/ast-integrate/")[-1]
    phys = json.loads(phys_path.read_text(encoding="utf-8"))
    res = Resource.from_contents(phys, default_specification=DRAFT202012)
    reg = Registry(retrieve=retrieve).with_resource(uri=base, resource=res)
    full_ref = {"$ref": base + "#" + frag}
    return Draft202012Validator(full_ref, registry=reg)

out = {}
for uid in IDS:
    ce = units[uid]
    receipt = json.loads((ROOT / ce["output_path"]).read_text(encoding="utf-8"))
    try:
        v = build_validator(ROOT / ce["output_schema"])
        errs = sorted(v.iter_errors(receipt), key=lambda e: list(map(str, e.path)))
        out[uid] = {
            "schema_ok": len(errs) == 0,
            "error_count": len(errs),
            "errors": ["%s: %s" % (list(e.path), e.message[:400]) for e in errs[:10]],
        }
    except Exception as e:
        out[uid] = {"schema_ok": None, "error": str(e)[:300]}
(ROOT / "_p2shard14-w3-review" / "schema_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
for uid, o in out.items():
    print(uid, "schema_ok:", o.get("schema_ok"), "errors:", o.get("error_count"))
    for e in o.get("errors", [])[:6]:
        print("   ", e[:350])
    if o.get("error"): print("    BUILD-ERR:", o["error"])

"""Verify the profile-generation root cause MYSELF against the resolved fragment.

The w2-shard2 closure claimed: every artifact-class profile is generated as
allOf[receipt generic_report, report.kind pin] and therefore demands receipt-core
fields that non-receipt artifacts do not carry. My classification found the same
error families (top-level receipt fields + evidence/negative_controls row shapes).
Before I adopt that adjudication, I verify it directly on the resolved fragment.
"""
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform/lib"))
import importlib.util
spec = importlib.util.spec_from_file_location("schema_resolver", REPO / "platform/lib/schema_resolver.py")
sr = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = spec
# register under the name the module itself imports as
sys.modules["schema_resolver"] = sr
try:
    spec.loader.exec_module(sr)
except Exception as exc:
    print("resolver load failed:", exc)
    raise

DECLS = {
    "ADV-0038": "command-center/schema/supply-chain-attestation.schema.json",
    "ADV-0040": "command-center/schema/privacy-dataflow.schema.json",
    "ADV-0090": "command-center/schema/benchmark-integrity.schema",
}
# Just probe one representative per schema family on the fragment level.
CHECK = [
    ("ADV-0124", "command-center/schema/fault-injection-run.schema.json"),
    ("ADV-0038", "command-center/schema/supply-chain-attestation.schema.json"),
    ("ADV-0090", "command-center/schema/benchmark-integrity.schema.json"),
]

for uid, decl in CHECK:
    rs = sr.resolve(decl)
    phys = REPO / rs.physical_path
    doc = json.loads(phys.read_text(encoding="utf-8"))
    frag = doc
    if rs.physical_fragment:
        node = doc
        for part in rs.physical_fragment.lstrip("#/").split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        frag = node
    print("==", uid, decl)
    print("  fragment kind:", rs.kind, "| pinned:", rs.report_kind_pinned,
          "| fragment ptr:", rs.physical_fragment)
    print("  fragment top keys:", sorted(frag.keys()) if isinstance(frag, dict) else type(frag))
    allof = frag.get("allOf")
    if allof:
        for i, branch in enumerate(allof):
            if "$ref" in branch:
                print(f"  allOf[{i}] $ref:", branch["$ref"])
            else:
                print(f"  allOf[{i}] inline keys:", sorted(branch.keys()))
    # does the fragment demand receipt fields on evidence rows?
    reqs = frag.get("required") or []
    print("  fragment requires:", reqs[:20])
    # look for the evidence item subschema in the fragment itself
    defs = frag.get("$defs") or frag.get("definitions") or {}
    for name in ("evidence", "negative_controls"):
        if name in defs:
            item = (defs[name].get("items") or {})
            print(f"  $defs/{name} item required:", item.get("required"),
                  "| kind enum:", ((item.get("properties") or {}).get("kind") or {}).get("enum"))
        elif name in frag.get("properties", {}):
            node = frag["properties"][name]
            items = node.get("items") or {}
            if "$ref" in items:
                print(f"  properties/{name} items -> $ref {items['$ref']}")
            else:
                print(f"  properties/{name} item required:", items.get("required"))
    print()

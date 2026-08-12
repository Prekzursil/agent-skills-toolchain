"""Round-1 probe 2: dump receipt.schema.json base + generic_report, and the
top-level shape of a known-COMPLETE sibling artifact (ADV-0024, exploit-proof)
and a known-COMPLETE threat-model sibling if one exists.
Read-only.
"""
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
rec = json.load(open(os.path.join(ROOT, "platform/schema/receipt.schema.json"), encoding="utf-8"))
print("top $ref:", rec.get("$ref"))
defs = rec.get("$defs", {})
print("$defs keys:", list(defs.keys()))
for k in ("receipt", "generic_report"):
    if k in defs:
        print("\n" + "=" * 25, k, "=" * 25)
        print(json.dumps(defs[k], indent=2)[:9000])

ADV = os.path.join(ROOT, "command-center/adversarial")


def shape(o, depth=0, maxd=3):
    if depth > maxd:
        return "..."
    if isinstance(o, dict):
        return {k: shape(v, depth + 1, maxd) for k, v in list(o.items())[:40]}
    if isinstance(o, list):
        return [shape(o[0], depth + 1, maxd), f"...len={len(o)}"] if o else []
    if isinstance(o, str):
        return f"str[{len(o)}]"
    return type(o).__name__


for f in ("ADV-0024-", "ADV-0033-", "ADV-0036-"):
    hits = [x for x in os.listdir(ADV) if x.startswith(f)]
    for h in hits:
        p = os.path.join(ADV, h)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print(f"\n{h}: UNPARSEABLE {e}")
            continue
        print(f"\n===== {h} ({os.path.getsize(p)} B) kind={d.get('report',{}).get('kind')}")
        print(json.dumps(shape(d, 0, 2), indent=1)[:4000])

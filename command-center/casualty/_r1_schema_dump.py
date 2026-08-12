"""Round-1 probe: dump the PHYSICAL schema defs for threat-model / exploit-proof,
plus the top-level shape of a known-COMPLETE exemplar (ADV-0024).

Read-only. No writes outside stdout.
"""
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"

prof_p = os.path.join(ROOT, "platform/schema/artifact-class-profiles.schema.json")
rec_p = os.path.join(ROOT, "platform/schema/receipt.schema.json")

prof = json.load(open(prof_p, encoding="utf-8"))
print("=== artifact-class-profiles top keys:", list(prof.keys()))
defs = prof.get("$defs", {})
print("=== $defs keys:", list(defs.keys()))
for k in ("threat-model", "exploit-proof"):
    print("\n" + "=" * 30, k, "=" * 30)
    print(json.dumps(defs.get(k), indent=2)[:6000])

if os.path.exists(rec_p):
    rec = json.load(open(rec_p, encoding="utf-8"))
    print("\n=== receipt.schema.json top keys:", list(rec.keys()))
    print("required:", rec.get("required"))
    props = rec.get("properties", {})
    print("properties:", list(props.keys()))
    print("additionalProperties:", rec.get("additionalProperties"))
    for pk in props:
        pv = props[pk]
        t = pv.get("type")
        req = pv.get("required")
        print(f"  - {pk}: type={t} required={req} keys={[x for x in pv.keys() if x not in ('description',)][:8]}")

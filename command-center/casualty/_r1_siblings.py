"""Round-1: sibling ADV units this threat model must aim, + manifest presence."""
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
d = json.load(open(os.path.join(ROOT, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"))
for wu in d["work_units"]:
    i = wu.get("id", "")
    if i.startswith("ADV-00"):
        n = int(i.split("-")[1])
        if 22 <= n <= 41:
            print(f"{i} | {wu.get('title')}")
            print(f"     Q: {(wu.get('question_or_target') or '')[:230]}")

print("\n--- manifest presence ---")
for p in ("command-center/ARTIFACT-MANIFEST.json",):
    fp = os.path.join(ROOT, p)
    print(p, "exists=", os.path.exists(fp), os.path.getsize(fp) if os.path.exists(fp) else "")

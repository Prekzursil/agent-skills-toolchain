"""Probe the structure of the prior archaeology registry JSON (read-only)."""

import json
import collections
import pathlib
import sys

P = pathlib.Path(
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"
)
raw = P.read_text(encoding="utf-8")
doc = json.loads(raw)
print("top-level type:", type(doc).__name__)
if isinstance(doc, dict):
    print("top-level keys:", list(doc.keys()))
    for k, v in doc.items():
        print(f"  {k}: {type(v).__name__} len={len(v) if hasattr(v, '__len__') else 'n/a'}")
    # find the candidate array
    for k, v in doc.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"\n--- array '{k}' first element keys: {sorted(v[0].keys())}")
            print(json.dumps(v[0], indent=2)[:2500])
            fams = collections.Counter(e.get("family") for e in v)
            print("\nfamily counts:", dict(fams))
            cls = collections.Counter(e.get("classification") for e in v)
            print("classification counts:", dict(cls))
            print("total entries:", len(v))
            ids = [e.get("id") for e in v]
            print("unique ids:", len(set(ids)), "of", len(ids))
            # field presence
            allkeys = collections.Counter()
            for e in v:
                for kk in e:
                    allkeys[kk] += 1
            print("\nfield presence (of", len(v), "):")
            for kk, n in allkeys.most_common():
                print(f"  {kk}: {n}")
elif isinstance(doc, list):
    print("len:", len(doc))
    print("first keys:", sorted(doc[0].keys()))
    print(json.dumps(doc[0], indent=2)[:2000])
sys.stdout.flush()

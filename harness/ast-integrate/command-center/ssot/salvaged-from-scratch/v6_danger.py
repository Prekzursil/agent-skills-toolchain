"""V6: DANGEROUS-DIRECTION attack. For each of the 10 'satisfiable' units, dump EVERY catalog
field and EVERY receipt string that could carry a reviewer demand, and every vendor token hit."""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def sh(rel, rev="HEAD"):
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=REPO,
                       capture_output=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


SAT10 = ["AUD-0006", "AUD-0020", "AUD-0021", "AUD-0030", "AUD-0041", "AUD-0051",
         "CC-0002", "IMP-0440", "TST-0334", "TST-0350"]
cat = json.loads(sh("command-center/WORK-UNIT-CATALOG.json"))
by_id = {u["id"]: u for u in cat["work_units"]}

print("### catalog field names present on the 10 (union) ###")
keys = set()
for u in SAT10:
    keys |= set(by_id[u].keys())
print(sorted(keys))

VEND = re.compile(r"\bopenai\b|\bcodex\b|\bgpt-?5\b|\bgemini\b|\bgoogle\b|\bcross[- _]?vendor\b|different\s+vendor", re.I)

print("\n### every CATALOG value on the 10 that mentions a rival vendor / cross-vendor ###")
for u in SAT10:
    for k, v in by_id[u].items():
        s = json.dumps(v)
        if VEND.search(s):
            print(f"  {u}.{k} = {s[:300]}")

print("\n### every RECEIPT string path on the 10 that mentions a rival vendor / cross-vendor ###")


def walk(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{p}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{p}[{i}]")
    elif isinstance(o, str):
        yield p, o


for u in SAT10:
    rec = json.loads(sh(by_id[u]["output_path"]))
    hits = [(p, s) for p, s in walk(rec) if VEND.search(s)]
    if hits:
        print(f"\n  --- {u}: {len(hits)} hit(s)")
        for p, s in hits[:12]:
            print(f"      {p}: {s[:220]}")

print("\n### completion_conditions / reviewer-ish fields verbatim for the 10 ###")
for u in SAT10:
    d = by_id[u]
    for k in sorted(d):
        if "review" in k.lower() or "vendor" in k.lower() or "completion" in k.lower():
            print(f"  {u}.{k} = {json.dumps(d[k])[:400]}")

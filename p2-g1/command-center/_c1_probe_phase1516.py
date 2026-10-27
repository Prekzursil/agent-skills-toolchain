"""LANE C1 read-only probe: what does the catalog hold for phases 15/16?

READ-ONLY. Opens WORK-UNIT-CATALOG.json for reading only; never writes it.
"""
import json
import collections
import re
import sys

P = "command-center/WORK-UNIT-CATALOG.json"
d = json.load(open(P, encoding="utf-8"))
print("top keys:", list(d.keys()))
units = None
for k in ("units", "work_units", "items", "entries"):
    if k in d:
        units = d[k]
        print("units key =", k)
        break
if units is None:
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print("candidate list key:", k, len(v))
print("type", type(units), "len", len(units) if units is not None else None)

if isinstance(units, dict):
    ks = list(units)
    print("sample id", ks[0])
    print("sample keys", list(units[ks[0]].keys()))
    seq = [dict(units[k], _key=k) for k in ks]
elif isinstance(units, list):
    print("sample keys", list(units[0].keys()))
    seq = units
else:
    seq = []

print("TOTAL UNITS:", len(seq))

# phase distribution
phase_fields = set()
for u in seq[:50]:
    for k in u:
        if "phase" in k.lower():
            phase_fields.add(k)
print("phase-ish fields:", sorted(phase_fields))

cnt = collections.Counter()
for u in seq:
    for f in phase_fields:
        cnt[(f, str(u.get(f)))] += 1
for k, v in sorted(cnt.items(), key=lambda x: str(x[0])):
    print("  ", k, v)

# state distribution
st = collections.Counter(str(u.get("state")) for u in seq)
print("STATES:", dict(st))

# Find units mentioning release / phase 15 / phase 16 / self-improvement
pat = re.compile(
    r"phase\s*1[56]|release ceremony|sbom|changelog|provenance|"
    r"marketplace listing|deprecation polic|governance guide|support polic|"
    r"migration guide|self-improvement|semantic version",
    re.I,
)
hits = []
for u in seq:
    blob = json.dumps(u, ensure_ascii=False)
    m = pat.findall(blob)
    if m:
        hits.append((u.get("id") or u.get("_key"), u.get("state"), sorted(set(x.lower() for x in m))[:6],
                     (u.get("title") or u.get("text") or "")[:100]))
print("\nRELEASE/SELF-IMPROVE-RELATED UNITS:", len(hits))
for h in hits[:60]:
    print("  ", h)

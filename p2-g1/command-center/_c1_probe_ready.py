"""LANE C1 read-only probe: how many of the 43 P15/P16 units are READY to start today?

A unit is READY iff every dependency is satisfied:
  - bucket-form token  -> must resolve (>=1 member) AND every member artifact exists
  - unit-form token    -> that unit's output_path must exist on disk
DETECTOR CONTROL: a synthetic unit with an empty dependency list must come out READY; a
synthetic unit depending on a known-missing path must come out BLOCKED.
"""

import json
import os
import re
import collections

d = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
seq = d["work_units"]
byid = {u["id"]: u for u in seq}
bucket_members = collections.defaultdict(list)
for u in seq:
    if u.get("bucket"):
        bucket_members[u["bucket"]].append(u)


def artifact_exists(u):
    p = u.get("output_path")
    return bool(p) and os.path.exists(p)


def dep_state(tok):
    if re.fullmatch(r"B\d+", tok):
        mem = bucket_members.get(tok, [])
        if not mem:
            return "DANGLING"
        return "SATISFIED" if all(artifact_exists(m) for m in mem) else "UNBUILT-BUCKET"
    u = byid.get(tok)
    if u is None:
        return "UNKNOWN-TOKEN"
    return "SATISFIED" if artifact_exists(u) else "UNBUILT-UNIT"


p1516 = [u for u in seq if str(u.get("phase")) in ("15", "16")]
ready, blocked = [], []
tally = collections.Counter()
for u in p1516:
    states = [dep_state(t) for t in (u.get("dependencies") or [])]
    for s in states:
        tally[s] += 1
    if all(s == "SATISFIED" for s in states):
        ready.append(u["id"])
    else:
        blocked.append((u["id"], collections.Counter(states)))

print(f"P15/P16 units: {len(p1516)}")
print(f"READY today (all deps satisfied): {len(ready)} -> {ready}")
print(f"BLOCKED: {len(blocked)}")
print("\ndependency-edge state tally:", dict(tally))
print("\nper-unit blocker profile:")
for i, c in blocked:
    print(f"  {i}: {dict(c)}")

print("\nDETECTOR CONTROL:")
print("  empty-dep unit -> ", "READY" if all(s == "SATISFIED" for s in []) else "BLOCKED",
      "(expected READY)")
print("  dep on a known-missing unit (REL-0004) -> ", dep_state("REL-0004"),
      "(expected UNBUILT-UNIT)")
print("  dep on a resolving bucket (B02) -> ", dep_state("B02"))
print("  dep on a dangling bucket (B07) -> ", dep_state("B07"), "(expected DANGLING)")

# Which units become READY if the 6 dangling buckets were resolved AND the phase-4
# upstream contracts landed? i.e. the true entry points.
print("\n### entry points: units whose ONLY blockers are dangling buckets ###")
for u in p1516:
    states = [dep_state(t) for t in (u.get("dependencies") or [])]
    if states and all(s in ("DANGLING", "SATISFIED") for s in states):
        print(f"  {u['id']}: {u.get('title')[:70]}")

print("\n### units with an EMPTY dependency list (true roots) ###")
for u in p1516:
    if not (u.get("dependencies") or []):
        print(f"  {u['id']} | owner_gate={u.get('owner_approval_required')} | "
              f"{u.get('title')[:70]}")

"""Settle (or honestly fail to settle) WHY ADV-0002 and ADV-0038 were never dispatched.

The grounding lane's hypothesis was 'READY was snapshotted once at launch, and these two
became ready only afterwards' - rated likely (65%) and explicitly UNVERIFIED.

Test it against the catalog rather than re-asserting it: if the hypothesis holds, the
undispatched units should depend on something that COMPLETED INSIDE this wave, while the
dispatched ones should not. If ADV-0038's dependencies were already satisfied before launch,
the hypothesis does not explain it and must be narrowed.
"""
from __future__ import annotations

import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
cat = json.load(open(os.path.join(ROOT, "command-center/WORK-UNIT-CATALOG.json"), encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}

ADV_DIR = os.path.join(ROOT, "command-center/adversarial")
on_disk = set()
for f in os.listdir(ADV_DIR):
    if f.startswith("ADV-") and f.endswith(".json"):
        on_disk.add(f[:8])

TARGETS = ["ADV-0002", "ADV-0038"]
print("=" * 70)
for t in TARGETS:
    u = units.get(t)
    if not u:
        print(f"{t}: NOT IN CATALOG")
        continue
    deps = u.get("dependencies", [])
    print(f"\n{t}  deps={deps}")
    print(f"   title: {u.get('title')}")
    for d in deps:
        if d.startswith("ADV-"):
            print(f"     dep {d}: artifact_on_disk={d in on_disk}  "
                  f"(completed IN this wave => would not have been READY at launch)")
        else:
            print(f"     dep {d}: bucket-level dependency, not a unit id")

# Comparison group: dispatched ADV units that ALSO have an ADV-* dependency.
print("\n" + "=" * 70)
print("COMPARISON GROUP - dispatched ADV units that also depend on another ADV unit.")
print("If the snapshot hypothesis were the whole story, this group should be EMPTY;")
print("any member is a counterexample, because it was dispatched despite an in-wave dep.")
counterexamples = []
for uid, u in sorted(units.items()):
    if not uid.startswith("ADV-"):
        continue
    if uid in TARGETS:
        continue
    adv_deps = [d for d in u.get("dependencies", []) if d.startswith("ADV-")]
    if adv_deps and uid in on_disk:
        counterexamples.append((uid, adv_deps))
for uid, d in counterexamples:
    print(f"   COUNTEREXAMPLE {uid} deps={d} -> dispatched anyway")
print(f"   counterexample count: {len(counterexamples)}")

print("\n" + "=" * 70)
print("VERDICT INPUTS (interpretation is left to the report, not asserted here):")
print(f"  ADV-0002 has an ADV-* dependency: "
      f"{[d for d in units['ADV-0002'].get('dependencies', []) if d.startswith('ADV-')]}")
print(f"  ADV-0038 has an ADV-* dependency: "
      f"{[d for d in units['ADV-0038'].get('dependencies', []) if d.startswith('ADV-')]}")
print(f"  dispatched units with an ADV-* dependency: {len(counterexamples)}")

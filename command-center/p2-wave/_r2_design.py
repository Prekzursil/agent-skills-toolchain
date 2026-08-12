"""ROUND2 R1b: MEASURE the fix design before writing it (control the detector first).

The adversarial verifier CONFIRMED (reproduced by me): the declared contract of the 23
meta-schema units accepts garbage, so condition 4 of `artifact_delivered()` is a NO-OP for them,
and `command-center/receipts/IMP-0433.json` with `state` flipped to SUCCESS is accepted as
DELIVERED -- a false green one word away.

Proposed fix = condition 4 gains a VACUITY GUARD plus a type-appropriate fallback. Before coding
it, measure the four things it depends on. If any answer is not what the design assumes, the
design is wrong, not the measurement.

P1  Does receipt.schema.json REJECT the IMP-0433 receipt mutated to state=SUCCESS?
    (If not, the receipts fallback does not fire and the fix is theatre.)
P2  Does "is a JSON Schema document" accept WFA-0001's real artifact and reject the garbage
    probes? (If not, the fix moves the partition and breaks the only delivered unit.)
P3  How many DISTINCT declared contracts in the catalog are vacuous, by two thresholds?
P4  Partition movement: over every unit whose artifact exists, does the new verdict differ?
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = CAT["work_units"]

p = REPO / "platform" / "lib" / "schema_resolver.py"
sys.path.insert(0, str(p.parent))
spec = importlib.util.spec_from_file_location("schema_resolver", p)
R = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = R
spec.loader.exec_module(R)

RECEIPT_SCHEMA = "command-center/schema/receipt.schema.json"

#: The three shapes that actually fooled verifiers in this program, plus one empty object.
GARBAGE = [
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
]


def errs(doc, schema):
    try:
        return len(R.validate_artifact(doc, schema))
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def n_rejected(schema):
    """How many of the garbage probes does this contract REJECT? (3 = fully discriminating)"""
    out = 0
    for g in GARBAGE:
        e = errs(g, schema)
        if isinstance(e, str) or e > 0:
            out += 1
    return out


print("=== P1: does receipt.schema.json reject the state=SUCCESS mutant of IMP-0433? ===")
real = json.loads((REPO / "command-center/receipts/IMP-0433.json").read_text(encoding="utf-8"))
mut = copy.deepcopy(real)
mut["state"] = "SUCCESS"
print(f"  real   receipt vs receipt.schema.json -> errors={errs(real, RECEIPT_SCHEMA)}")
print(f"  MUTANT state=SUCCESS                  -> errors={errs(mut, RECEIPT_SCHEMA)}")
print(f"  reviewer block present: {'reviewer' in real}  verdict={real.get('reviewer', {}).get('verdict')!r}")
for g in GARBAGE:
    print(f"  GARBAGE(keys={list(g)[:2]}) vs receipt.schema.json -> errors={errs(g, RECEIPT_SCHEMA)}")

print()
print("=== P2: the 'is a JSON Schema document' discriminator ===")


def looks_like_schema_doc(doc) -> bool:
    if not isinstance(doc, dict):
        return False
    if not ("$schema" in doc or "$id" in doc):
        return False
    try:
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception:  # noqa: BLE001
        return False
    return True


wfa = json.loads((REPO / "command-center/wfa/schema/wfa-schema-pack.json").read_text("utf-8"))
print(f"  WFA-0001 artifact  -> looks_like_schema_doc={looks_like_schema_doc(wfa)}")
print(f"  IMP-0433 receipt   -> looks_like_schema_doc={looks_like_schema_doc(real)}")
for g in GARBAGE:
    print(f"  GARBAGE(keys={list(g)[:2]}) -> looks_like_schema_doc={looks_like_schema_doc(g)}")
broken_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": 123,
                 "required": "not-an-array"}
print(f"  KNOWN-BAD schema doc -> looks_like_schema_doc={looks_like_schema_doc(broken_schema)}")

print()
print("=== P3: vacuity census over DISTINCT declared contracts ===")
decls = sorted({u.get("output_schema") for u in UNITS if isinstance(u.get("output_schema"), str)
                and u.get("output_schema")})
tally = {0: [], 1: [], 2: [], 3: []}
for d in decls:
    tally[n_rejected(d)].append(d)
for k in sorted(tally):
    print(f"  rejects {k}/3 garbage probes: {len(tally[k])} distinct declarations")
print(f"  distinct declarations total: {len(decls)}")
print("  fully-vacuous (0/3) declarations:")
for d in tally[0]:
    n = sum(1 for u in UNITS if u.get("output_schema") == d)
    print(f"     {d}   (declared by {n} units)")
if tally[1] or tally[2]:
    print("  PARTIAL discriminators (1/3 or 2/3) -- these would change meaning by threshold:")
    for k in (1, 2):
        for d in tally[k]:
            n = sum(1 for u in UNITS if u.get("output_schema") == d)
            print(f"     [{k}/3] {d}   (declared by {n} units)")

print()
print("=== P4: partition movement -- units whose artifact EXISTS, old vs new verdict ===")
sys.path.insert(0, str(REPO / "command-center"))
import ready_units as RU  # noqa: E402

res = RU._load_resolver()
moved = []
present = 0
for u in UNITS:
    op = u.get("output_path")
    if not op or not (REPO / op).exists():
        continue
    present += 1
    old, oldwhy = RU.artifact_delivered(u, res)
    # NEW predicate, simulated here exactly as it will be implemented
    new, newwhy = old, oldwhy
    if old:
        sch = u.get("output_schema")
        if isinstance(sch, str) and sch and n_rejected(sch) < 3:
            doc = json.loads((REPO / op).read_text(encoding="utf-8")) if op.endswith(".json") else None
            if isinstance(doc, dict) and op.startswith("command-center/receipts/"):
                e = errs(doc, RECEIPT_SCHEMA)
                new, newwhy = (e == 0), f"vacuous-contract;receipt-fallback-errors={e}"
            elif looks_like_schema_doc(doc):
                new, newwhy = True, "vacuous-contract;schema-document-fallback"
            else:
                new, newwhy = False, "contract-vacuous:no-type-appropriate-fallback"
    if new is not old:
        moved.append((u["id"], old, oldwhy, new, newwhy))
print(f"  units with an artifact on disk: {present}")
print(f"  verdict CHANGES under the new predicate: {len(moved)}")
for m in moved:
    print(f"     {m[0]}: old={m[1]}({m[2]}) -> new={m[3]}({m[4]})")

print()
print("=== P4b: the KNOWN-BROKEN state (the mutant) under BOTH predicates ===")
tmp = REPO / "command-center/p2-wave/_r2_tmp"
tmp.mkdir(exist_ok=True)
mpath = tmp / "IMP-0433-mutant.json"
mpath.write_text(json.dumps(mut, indent=1, sort_keys=True) + "\n", encoding="utf-8")
fake = dict(next(u for u in UNITS if u["id"] == "IMP-0433"))
fake["output_path"] = str(mpath.relative_to(REPO)).replace("\\", "/")
old, oldwhy = RU.artifact_delivered(fake, res)
e = errs(mut, RECEIPT_SCHEMA)
print(f"  OLD predicate on mutant: delivered={old} ({oldwhy})   <-- known-broken state")
print(f"  NEW receipt-fallback   : errors={e} -> delivered={e == 0}")
print()
print("DONE:r2-design")

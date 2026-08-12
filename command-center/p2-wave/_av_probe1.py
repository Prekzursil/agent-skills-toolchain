"""ADVERSARIAL VERIFIER probe 1.

Attacks BOTH the build and the audit. Nothing here reads a claim; every line executes.

Q1. What does IMP-0433's catalog ROW actually declare?
Q2. How many units declare a META-schema contract (ALL forms, not just the one path the
    auditor grepped)? The auditor asserted "exactly 1 of 2,007". If other spellings of the
    same vacuous contract exist, the auditor UNDER-COUNTED the blast radius.
Q3. Is the meta-schema contract really vacuous? Two-sided control on EVERY meta-declaring unit.
Q4. THE DECISIVE ONE -- is `delivered` one word away? Build a MUTANT copy of each of the five
    shipped artifacts with `state` flipped to SUCCESS and run the SHIPPED predicate on it.
    Expected if the audit is right: IMP-0433 mutant -> delivered=True (false green),
    the other four -> delivered=False (schema catches it). That is a two-sided control.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"
TMP = REPO / "command-center/p2-wave/_av_tmp"
TMP.mkdir(parents=True, exist_ok=True)


def load(name: str, rel: str):
    p = REPO / rel
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(p.parent))
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ru = load("ready_units", "command-center/ready_units.py")
sr = load("schema_resolver", "platform/lib/schema_resolver.py")

units = json.loads(CAT.read_text(encoding="utf-8"))["work_units"]
by_id = {u["id"]: u for u in units}
print(f"catalog units: {len(units)}")

FIVE = ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"]

print("\n=== Q1: the five rows, verbatim fields ===")
for uid in FIVE:
    u = by_id[uid]
    print(f"{uid}: phase={u.get('phase')!r}")
    print(f"   output_path   = {u.get('output_path')!r}")
    print(f"   output_schema = {u.get('output_schema')!r}")
    tr = u.get("tests_required")
    print(f"   tests_required= {json.dumps(tr)[:300] if tr else None}")
    print(f"   reviewer_req  = {str(u.get('reviewer_requirement'))[:120]!r}")

print("\n=== Q2: EVERY unit whose contract resolves to a meta-schema (all spellings) ===")
meta_units = []
kinds = {}
errs_resolve = []
for u in units:
    d = u.get("output_schema")
    try:
        res = sr.resolve(d)
    except Exception as e:  # noqa: BLE001
        errs_resolve.append((u["id"], str(d), type(e).__name__))
        continue
    kinds[res.kind] = kinds.get(res.kind, 0) + 1
    if res.kind in ("meta-schema-url", "meta-schema-mirror"):
        meta_units.append((u["id"], d, res.kind, u.get("output_path")))
print(f"resolve() kind histogram over all {len(units)} units: {kinds}")
print(f"resolve() RAISED for: {len(errs_resolve)} units  {errs_resolve[:5]}")
print(f"units with a META-schema contract: {len(meta_units)}")
for m in meta_units:
    print(f"   {m[0]:10s} kind={m[2]:20s} declared={m[1]}")
    print(f"              output_path={m[3]}")

print("\n=== Q3: two-sided vacuity control on each META-declaring unit ===")
GARBAGE = {"totally": "unrelated", "nonsense": [1, 2, 3], "n": 999999}
KNOWN_BAD_FOR_METASCHEMA = {"type": 123, "required": "not-an-array"}
for uid, declared, kind, opath in meta_units:
    e_g = sr.validate_artifact(GARBAGE, declared)
    e_b = sr.validate_artifact(KNOWN_BAD_FOR_METASCHEMA, declared)
    real = None
    if opath and (REPO / opath).is_file():
        real = sr.validate_artifact(
            json.loads((REPO / opath).read_text(encoding="utf-8")), declared
        )
    print(
        f"   {uid}: garbage_errors={len(e_g)}  known-bad-schema_errors={len(e_b)}  "
        f"real_artifact_errors={len(real) if real is not None else 'NO-FILE'}"
    )
    print(
        f"        -> VACUOUS for ordinary artifacts: {len(e_g) == 0}   "
        f"(detector alive at all: {len(e_b) > 0})"
    )

print("\n=== Q4: DECISIVE -- is `delivered` one word away? MUTANT state=SUCCESS ===")
resolver = ru._load_resolver()
print(f"   shipped resolver loaded: {resolver is not None}")
for uid in FIVE:
    u = by_id[uid]
    opath = u["output_path"]
    src = REPO / opath
    doc = json.loads(src.read_text(encoding="utf-8"))
    base_ok, base_why = ru.artifact_delivered(u, resolver)
    mut = json.loads(json.dumps(doc))
    mut["state"] = "SUCCESS"
    mp = TMP / f"{uid}-mutant.json"
    mp.write_text(json.dumps(mut, indent=1), encoding="utf-8")
    fake = dict(u)
    fake["output_path"] = str(mp.relative_to(REPO)).replace("\\", "/")
    mut_ok, mut_why = ru.artifact_delivered(fake, resolver)
    flag = "  <<< FALSE GREEN" if mut_ok else ""
    print(
        f"   {uid:10s} real: delivered={base_ok} ({base_why})   "
        f"state=SUCCESS mutant: delivered={mut_ok} ({mut_why}){flag}"
    )

print("\nDONE:av-probe1")

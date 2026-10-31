"""ADVERSARIAL VERIFIER probe 2.

Q5. WHICH unit is the single `delivered=1` in the shipped partition, and does its
    condition-4 contract discriminate anything? If the one delivered unit in a 2,007-unit
    program is gated by a vacuous schema, the strict predicate's headline is hollow.
Q6. ready_units.py --self-test: is CONTROL_GOOD itself vacuously validated? Run the
    both-states test the self-test does NOT run: flip CONTROL_BAD's state to SUCCESS and
    flip CONTROL_GOOD's state to BLOCKED, and see which condition actually fires.
Q7. The `except Exception: pass` fail-open at ready_units.py:111-112 -- how many units would
    silently skip condition 4 because resolve()/validator_for() raises? (Builder claimed 0
    unresolvable; validator_for can still raise where resolve() does not.)
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
resolver = ru._load_resolver()

print("=== Q5: who is `delivered`? ===")
delivered = []
present_not_delivered = 0
for u in units:
    ok, why = ru.artifact_delivered(u, resolver)
    if ok:
        delivered.append((u["id"], why, u.get("output_path"), u.get("output_schema")))
    elif u.get("output_path") and (REPO / u["output_path"]).exists():
        present_not_delivered += 1
print(
    f"delivered count = {len(delivered)}   present-but-not-delivered = {present_not_delivered}"
)
for uid, why, op, os_ in delivered:
    try:
        kind = sr.resolve(os_).kind
    except Exception as e:  # noqa: BLE001
        kind = f"RAISED:{type(e).__name__}"
    garbage = None
    try:
        garbage = len(sr.validate_artifact({"totally": "unrelated", "n": 999999}, os_))
    except Exception as e:  # noqa: BLE001
        garbage = f"RAISED:{type(e).__name__}"
    print(f"  {uid}: why={why}")
    print(f"      output_path   = {op}")
    print(f"      output_schema = {os_}")
    print(f"      resolved kind = {kind}")
    print(
        f"      GARBAGE validates with errors = {garbage}   "
        f"-> condition-4 discriminates: {garbage != 0}"
    )

print("\n=== Q6: the self-test's own controls, both states ===")
by_id = {u["id"]: u for u in units}
for uid in (ru.CONTROL_GOOD, ru.CONTROL_BAD):
    u = by_id[uid]
    doc = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
    real_state = doc.get("state") if isinstance(doc, dict) else None
    ok, why = ru.artifact_delivered(u, resolver)
    for flip in ("SUCCESS", "BLOCKED"):
        mut = json.loads(json.dumps(doc))
        if isinstance(mut, dict):
            mut["state"] = flip
        mp = TMP / f"selftest-{uid}-{flip}.json"
        mp.write_text(json.dumps(mut, indent=1), encoding="utf-8")
        fake = dict(u)
        fake["output_path"] = str(mp.relative_to(REPO)).replace("\\", "/")
        mok, mwhy = ru.artifact_delivered(fake, resolver)
        print(
            f"  {uid} (real state={real_state!r}, real delivered={ok}/{why}) "
            f"| state:={flip} -> delivered={mok} ({mwhy})"
        )

print("\n=== Q7: fail-open census -- units where condition 4 is SILENTLY skipped ===")
raise_resolve = 0
raise_validator = 0
examples = []
seen: dict[str, str] = {}
for u in units:
    d = u.get("output_schema")
    if not isinstance(d, str) or not d:
        continue
    if d in seen:
        continue
    try:
        sr.resolve(d)
    except Exception as e:  # noqa: BLE001
        raise_resolve += 1
        seen[d] = "resolve"
        examples.append((u["id"], d, "resolve", type(e).__name__))
        continue
    try:
        sr.validator_for(d)
        seen[d] = "ok"
    except Exception as e:  # noqa: BLE001
        raise_validator += 1
        seen[d] = "validator"
        examples.append((u["id"], d, "validator_for", type(e).__name__))
print(f"distinct declarations examined: {len(seen)}")
print(f"  resolve() raised      : {raise_resolve}")
print(f"  validator_for() raised: {raise_validator}")
for e in examples[:10]:
    print(f"   {e}")
print("\nDONE:av-probe2")

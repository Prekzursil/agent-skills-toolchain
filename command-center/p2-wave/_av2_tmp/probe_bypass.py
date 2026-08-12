"""ADVERSARIAL VERIFIER round-3 probe: attack the FIX itself.

Question 1: does `looks_like_schema_doc` gate on anything beyond the presence of a `$schema`/`$id`
key?  Question 2: does that reach the END-TO-END predicate `artifact_delivered`, i.e. can a garbage
document be counted DELIVERED for a unit that declares a vacuous contract, purely by adding one
key?  Question 3 (the control): the same document WITHOUT that key must be REJECTED in the same
run -- otherwise the probe is measuring something other than the key.

Nothing here writes to a real unit `output_path`. The synthetic unit points at a scratch file under
command-center/p2-wave/_av2_tmp/, so the census on disk is unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
TMP = REPO / "command-center/p2-wave/_av2_tmp"
TMP.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)

resolver = ru._load_resolver()
print(f"resolver loaded: {resolver is not None}")
print(f"ru.REPO == repo: {ru.REPO == REPO}  ({ru.REPO})")

META = "https://json-schema.org/draft/2020-12/schema"

GARBAGE = {"totally": "unrelated", "passing_tests": 999999}
GARBAGE_KEYED = {"$schema": META, "totally": "unrelated", "passing_tests": 999999}
BLOB = {"blob": "x" * 2000}
BLOB_KEYED = {"$schema": META, "blob": "x" * 2000}
EMPTY_KEYED = {"$schema": META}
IDONLY = {"$id": "urn:whatever", "totally": "unrelated", "passing_tests": 999999}

print("\n--- Q1  looks_like_schema_doc, function level ---")
for name, doc in [
    ("garbage (no key)      ", GARBAGE),
    ("garbage + $schema     ", GARBAGE_KEYED),
    ("2000-x blob (no key)  ", BLOB),
    ("2000-x blob + $schema ", BLOB_KEYED),
    ("bare {$schema}        ", EMPTY_KEYED),
    ("garbage + $id only    ", IDONLY),
]:
    print(f"  {name} -> {ru.looks_like_schema_doc(doc)}")

print("\n--- Q1b  is the vacuous contract still vacuous against the KEYED garbage? ---")
for name, doc in [("garbage + $schema", GARBAGE_KEYED), ("garbage (no key)", GARBAGE)]:
    errs = resolver.validate_artifact(doc, META)
    print(f"  meta-schema vs {name}: errors={len(errs)}")

print("\n--- Q2  END-TO-END artifact_delivered on a SYNTHETIC unit (scratch path) ---")
rel = "command-center/p2-wave/_av2_tmp/_synthetic_artifact.json"
fp = REPO / rel


def run(doc, label):
    fp.write_text(json.dumps(doc), encoding="utf-8")
    unit = {"id": "AV2-PROBE", "output_path": rel, "output_schema": META}
    ok, why = ru.artifact_delivered(unit, resolver)
    print(f"  {label:36s} bytes={fp.stat().st_size:5d}  delivered={ok}  ({why})")
    return ok


# the state field matters for condition 5, so give both shapes a passing state
g_state = dict(GARBAGE, state="SUCCESS")
gk_state = dict(GARBAGE_KEYED, state="SUCCESS")
ok_plain = run(g_state, "CONTROL garbage, NO $schema")
ok_keyed = run(gk_state, "garbage + ONE key ($schema)")
ok_blobk = run(dict(BLOB_KEYED, state="SUCCESS"), "2000-x blob + ONE key")
ok_bare = run({"$schema": META}, "bare {$schema} only, 42 bytes")

print("\n--- Q3  VERDICT ---")
print(f"  control (no key) rejected : {ok_plain is False}")
print(f"  one-key bypass accepted   : {ok_keyed is True}")
print(
    "  BYPASS_PROVEN =",
    (ok_plain is False) and (ok_keyed is True) and (ok_blobk is True) and (ok_bare is True),
)

fp.unlink(missing_ok=True)

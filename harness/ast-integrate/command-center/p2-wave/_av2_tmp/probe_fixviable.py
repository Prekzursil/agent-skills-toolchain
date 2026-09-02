"""Is a remedy for D1 (the one-key $schema bypass) viable, or is the hole inherent?

Candidate remedy, 5 lines: after `check_schema`, require the artifact USED AS A CONTRACT to reject
the same three garbage probes -- reusing the module's own convention that a contract which RAISES
on garbage has still refused it. Then measure whether it moves any verdict on the artifacts that
actually exist. A remedy that flips the program's single delivered unit is not a remedy.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location(
    "ru", REPO / "command-center/ready_units.py"
)
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()


_ORIG_LOOKS = (
    ru.looks_like_schema_doc
)  # bind BEFORE any monkeypatch, or `strengthened` recurses
# into itself (my own detector failure, caught by the
# RecursionError rather than by a plausible number)


def strengthened(doc) -> bool:
    """looks_like_schema_doc + the vacuity recursion."""
    if not _ORIG_LOOKS(doc):
        return False
    try:
        v = jsonschema.Draft202012Validator(doc)
    except Exception:
        return False
    for probe in ru._GARBAGE_PROBES:
        try:
            if not list(v.iter_errors(probe)):
                return False  # accepts garbage -> vacuous -> not usable as evidence
        except Exception:
            pass  # raised = refused, the module's own convention
    return True


META = "https://json-schema.org/draft/2020-12/schema"
cases = [
    (
        "garbage + $schema  (the bypass)",
        {"$schema": META, "totally": "u", "passing_tests": 999999},
        False,
    ),
    ("bare {$schema}", {"$schema": META}, False),
    ("garbage + $id only", {"$id": "urn:x", "totally": "u"}, False),
    ("structurally-broken + $schema", {"$schema": META, "type": 123}, False),
]
catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = catalog["work_units"] if isinstance(catalog, dict) else catalog
w = next(x for x in units if x["id"] == "WFA-0001")
pack = json.loads((REPO / w["output_path"]).read_text(encoding="utf-8"))
cases.append(("REAL WFA-0001 schema pack (must stay True)", pack, True))

print("--- A. remedy behaviour, two-sided ---")
allok = True
for label, doc, want in cases:
    got = strengthened(doc)
    ok = got is want
    allok &= ok
    print(
        f"  {label:44s} current={str(ru.looks_like_schema_doc(doc)):5s} remedy={str(got):5s} want={str(want):5s} {'OK' if ok else 'MISMATCH'}"
    )
print(f"  REMEDY_TWO_SIDED = {allok}")

print("\n--- B. does the remedy move any verdict on artifacts that EXIST today? ---")
orig = ru.looks_like_schema_doc
changed = []
present = 0
for u in units:
    p = u.get("output_path")
    if not p:
        continue
    fp = REPO / p
    if not fp.exists() or fp.stat().st_size <= 0:
        continue
    present += 1
    before, _ = ru.artifact_delivered(u, resolver)
    ru.looks_like_schema_doc = strengthened
    after, why = ru.artifact_delivered(u, resolver)
    ru.looks_like_schema_doc = orig
    if before != after:
        changed.append((u["id"], before, after, why))
print(f"  artifacts present on disk: {present}")
print(f"  verdict CHANGES under the remedy: {len(changed)} -> {changed}")

print(
    "\n--- C. strictness check: is the SHIPPED fix ever MORE permissive than the pre-4b one? ---"
)
looser = []
for u in units:
    p = u.get("output_path")
    if not p or not (REPO / p).exists():
        continue
    new, _ = ru.artifact_delivered(u, resolver)
    old = ru._prefix_predicate(u, resolver)
    if new and not old:
        looser.append(u["id"])
print(f"  units where NEW accepts but OLD rejected (would be a regression): {looser}")

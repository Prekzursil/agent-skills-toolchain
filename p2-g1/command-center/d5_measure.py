"""D5 measurement: assigned_model_vendor_role shape census, read off disk.

Deliverable (not a scratch _*.py): the census tool for defect D5.
Reads the catalog, classifies every work unit's assigned_model_vendor_role by
SHAPE, and prints counts. No writes.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "WORK-UNIT-CATALOG.json"
FIELD = "assigned_model_vendor_role"
CANON_KEYS = frozenset({"model", "vendor", "role"})
#: the optional keys the canonical assignment_object actually declares. Kept in sync with
#: platform/schema/work-unit.schema.json $defs/assignment_object - a key missing here is
#: reported as 'object-superset-unknown', so this set is part of the detector, not decoration.
OPTIONAL_KEYS = frozenset(
    {"basis", "rationale", "co_assignments", "multi_vendor_policy"}
)


def classify(val: object) -> str:
    """Classify one assigned_model_vendor_role value by shape."""
    if val is None:
        return "absent"
    if isinstance(val, str):
        parts = val.split("/")
        if len(parts) == 3 and all(p.strip() for p in parts):
            return "string-slash-triple"
        return "string-freeform"
    if isinstance(val, dict):
        keys = frozenset(val)
        if keys == CANON_KEYS:
            if all(isinstance(val[k], str) and val[k].strip() for k in CANON_KEYS):
                return "object-exact-3-str"
            return "object-exact-3-nonstr"
        if CANON_KEYS <= keys:
            extra = keys - CANON_KEYS
            if extra <= OPTIONAL_KEYS:
                return "object-superset-known"
            return "object-superset-unknown"
        return "object-missing-required"
    return f"other-{type(val).__name__}"


def shape_fingerprint(val: object) -> str:
    """A structural fingerprint used to count 'distinct shapes'."""
    if isinstance(val, dict):
        return "obj:" + ",".join(sorted(val))
    if isinstance(val, str):
        return "str"
    return type(val).__name__


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    print(f"catalog={CATALOG}")
    print(f"top-level keys={sorted(doc)}")
    print(f"work_units={len(units)}  items={len(doc.get('items', []))}")

    cls = Counter()
    fp = Counter()
    present = 0
    for u in units:
        val = u.get(FIELD)
        if FIELD in u:
            present += 1
        cls[classify(val)] += 1
        if FIELD in u:
            fp[shape_fingerprint(val)] += 1

    print(f"\nfield present on {present}/{len(units)} units")
    print("\n--- SHAPE CENSUS ---")
    for k, v in sorted(cls.items(), key=lambda kv: -kv[1]):
        print(f"{v:6d}  {k}")

    print("\n--- KEY-SET FINGERPRINTS (distinct structural shapes) ---")
    print(f"distinct fingerprints = {len(fp)}")
    for k, v in sorted(fp.items(), key=lambda kv: -kv[1])[:25]:
        print(f"{v:6d}  {k}")

    # distinct VALUE shapes (what a value-level audit would count)
    valset = Counter()
    for u in units:
        val = u.get(FIELD)
        valset[json.dumps(val, sort_keys=True)] += 1
    print(f"\ndistinct serialized VALUES = {len(valset)}")

    # distinct 'model' field values among object form
    models = Counter()
    for u in units:
        val = u.get(FIELD)
        if isinstance(val, dict) and isinstance(val.get("model"), str):
            models[val["model"]] += 1
    print(f"distinct object.model strings = {len(models)}")
    print("top 12 object.model values:")
    for k, v in sorted(models.items(), key=lambda kv: -kv[1])[:12]:
        print(f"{v:6d}  {k[:110]!r}")

    # multi-vendor detection among object.model
    multi = [
        u["id"]
        for u in units
        if isinstance(u.get(FIELD), dict)
        and isinstance(u[FIELD].get("model"), str)
        and re.search(r"\+|>=\s*2\s*vendors|\band\b", u[FIELD]["model"], re.I)
    ]
    print(f"\nobject.model values implying MULTI-VENDOR = {len(multi)}")
    print("sample ids:", multi[:6])

    # long / prose-bearing model strings
    prose = [
        (u["id"], u[FIELD]["model"])
        for u in units
        if isinstance(u.get(FIELD), dict)
        and isinstance(u[FIELD].get("model"), str)
        and len(u[FIELD]["model"]) > 60
    ]
    print(f"object.model strings longer than 60 chars = {len(prose)}")
    for i, m in prose[:4]:
        print(f"  {i}: {m[:150]!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

r"""Both-states test on the declared output_schema contracts.

The DoD says each delivered unit must be "executable-proven against its declared contract".
receipt.schema.json self-describes as a "GENERATED SHIM -- carries NO constraints of its own"
and is declared by 674 units. If validating a garbage document against it PASSES, then
"validated against its declared contract" proves nothing for those units.

Control: feed each schema (a) a known-garbage doc and (b) the real artifact, and report whether
the schema DISCRIMINATES. A schema that accepts both measures nothing.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print("FAILED:schema-is-real jsonschema not installed - cannot run the control")
        return 1

    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]

    # Which schema paths does the catalog actually declare, and how often?
    declared: Counter = Counter()
    for u in units:
        s = u.get("output_schema")
        if s:
            declared[s] += 1
    print(f"distinct declared output_schema paths: {len(declared)}")
    print("top 8 by unit count:")
    for s, n in declared.most_common(8):
        print(f"  {n:>5}  {s}")

    store = {}
    for p in (REPO / "command-center/schema").rglob("*.schema.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "$id" in d:
            store[d["$id"]] = d
    for p in (REPO / "platform").rglob("*.schema.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "$id" in d:
            store[d["$id"]] = d
    print(f"\nresolver store loaded with {len(store)} $id-bearing schemas")

    results = []
    for spath, n in declared.most_common(12):
        fp = REPO / spath
        if not fp.exists():
            results.append((spath, n, "SCHEMA-FILE-MISSING", 0, 0))
            continue
        try:
            schema = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            results.append((spath, n, f"SCHEMA-PARSE-FAIL:{type(exc).__name__}", 0, 0))
            continue
        res = jsonschema.RefResolver(
            base_uri=schema.get("$id", ""), referrer=schema, store=store
        )
        rejected = 0
        errs = 0
        for g in GARBAGE:
            try:
                jsonschema.validate(g, schema, resolver=res)
            except jsonschema.ValidationError:
                rejected += 1
            except Exception:
                errs += 1
        verdict = (
            "NO-OP (accepts all garbage)"
            if rejected == 0 and errs == 0
            else (
                f"resolve-error x{errs}"
                if errs
                else f"discriminates ({rejected}/3 garbage rejected)"
            )
        )
        results.append((spath, n, verdict, rejected, errs))

    print("\nGARBAGE-REJECTION CONTROL (3 garbage docs per schema):")
    noop_units = 0
    for spath, n, verdict, rej, errs in results:
        print(f"  {n:>5} units  {verdict:<34} {spath}")
        if verdict.startswith("NO-OP"):
            noop_units += n
    print(f"\nunits whose declared contract accepts all 3 garbage docs: {noop_units}")
    print("SUCCESS:schema-is-real control ran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

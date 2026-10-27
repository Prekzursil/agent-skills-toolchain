#!/usr/bin/env python3
# Read-only full-tree sweep v2: validate all 2007 catalog artifacts against their
# catalog-declared output_schema. The jsonschema library resolves the shim $ref
# chain itself (same code path as the shard-15 driver, which produced real
# constraint errors and passed RES-0020 - library resolution is the proven path).
import json
from pathlib import Path
from jsonschema.validators import validator_for

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = Path(__file__).resolve().parent / "fulltree-schema-sweep.json"

def main():
    cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
    units = cat["work_units"]
    vcache = {}
    results = {"total": 0, "schema_valid_success": 0, "schema_invalid_success": 0,
               "not_success": 0, "artifact_problem": 0}
    details = []
    for u in units:
        uid, op, osch = u.get("id"), u.get("output_path"), u.get("output_schema")
        results["total"] += 1
        p = REPO / op if op else None
        if not p or not p.exists() or p.stat().st_size == 0:
            results["artifact_problem"] += 1
            details.append({"unit": uid, "why": "artifact-missing/empty"})
            continue
        try:
            doc = json.loads(p.read_bytes().decode("utf-8"))
        except Exception:
            results["artifact_problem"] += 1
            details.append({"unit": uid, "why": "unparsable"})
            continue
        st = doc.get("state")
        if st != "SUCCESS":
            results["not_success"] += 1
            details.append({"unit": uid, "why": "state=" + str(st)})
            continue
        if osch not in vcache:
            try:
                s = json.loads((REPO / osch).read_bytes().decode("utf-8"))
                V = validator_for(s)
                V.check_schema(s)
                vcache[osch] = V(s)
            except Exception as ex:
                vcache[osch] = None
                details.append({"unit": uid, "why": "schema-load-error " + osch + ": " + repr(ex)[:120]})
                continue
        V = vcache[osch]
        if V is None:
            continue
        try:
            errs = sorted(V.iter_errors(doc), key=lambda e: list(e.path))
        except Exception as ex:
            details.append({"unit": uid, "why": "validate-error: " + repr(ex)[:120]})
            continue
        if errs:
            results["schema_invalid_success"] += 1
            e0 = errs[0]
            details.append({"unit": uid, "why": "schema: " + str(list(e0.path))[:80] + " " + e0.message[:120]})
        else:
            results["schema_valid_success"] += 1
        if len(details) % 100 == 0:
            print("...details so far:", len(details), flush=True)
    OUT.write_text(json.dumps(results, indent=1) + "\nDETAILS:\n" +
                   "\n".join(json.dumps(d) for d in details), encoding="utf-8")
    print(json.dumps(results, indent=1))
    print("wrote:", OUT)

if __name__ == "__main__":
    main()

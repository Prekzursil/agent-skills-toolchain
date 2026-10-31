#!/usr/bin/env python3
# Sweep v4 - FULL 2007 accounting, v3 loader, zero silent branches.
# Every unit lands in exactly one bucket: valid / invalid / not_success /
# artifact_problem / not_checked(with reason) / schema_defect(with reason).
import json
from pathlib import Path
from jsonschema.validators import validator_for
import warnings
warnings.filterwarnings("ignore")

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = Path(__file__).resolve().parent / "sweep-v4-full.json"

def load_doc(p):
    return json.loads(p.read_bytes().decode("utf-8"))

def main():
    cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
    units = cat["work_units"]
    vcache = {}
    buckets = {"schema-valid": [], "schema-invalid": [], "not_success": [],
               "artifact_problem": [], "not_checked": [], "schema_defect": []}
    def get_validator(osch):
        # returns ("OK", [validators]) | ("NOT_CHECKED", reason) | ("DEFECT", reason)
        if osch in vcache:
            return vcache[osch]
        out = ("NOT_CHECKED", "unparsed")
        try:
            parts = [x.strip() for x in osch.split(" + ") if x.strip()]
            vals = []
            for part in parts:
                frag = None
                pathpart = part
                if "#" in pathpart:
                    pathpart, frag = pathpart.split("#", 1)
                    frag = frag.lstrip("/")
                pathpart = pathpart.strip()
                if pathpart.startswith("http"):
                    vcache[osch] = ("NOT_CHECKED", "remote-schema-url: " + pathpart[:80])
                    return vcache[osch]
                if not pathpart.endswith(".json") or " " in pathpart:
                    toks = part.split()
                    cand = toks[0] if toks and toks[0].endswith(".json") else None
                    if cand is None:
                        vcache[osch] = ("NOT_CHECKED", "prose-decl: " + part[:80])
                        return vcache[osch]
                    pathpart, frag = cand, None
                sp = REPO / pathpart
                if not sp.exists():
                    vcache[osch] = ("DEFECT", "declared-schema-file-missing: " + pathpart)
                    return vcache[osch]
                s = load_doc(sp)
                V = validator_for(s)
                V.check_schema(s)
                if frag:
                    sub = dict(s)
                    sub["$ref"] = "#/" + frag
                    try:
                        V.check_schema(sub)
                        vals.append(V(sub))
                    except Exception as ex:
                        vcache[osch] = ("DEFECT", "schema-fragment-defect " + pathpart + "#" + frag[:50] + ": " + repr(ex)[:90])
                        return vcache[osch]
                else:
                    vals.append(V(s))
            out = ("OK", vals)
        except Exception as ex:
            out = ("DEFECT", "schema-load: " + repr(ex)[:120])
        vcache[osch] = out
        return out
    for u in units:
        uid, op, osch = u.get("id"), u.get("output_path"), u.get("output_schema")
        p = REPO / op if op else None
        if not p or not p.exists():
            buckets["artifact_problem"].append(uid + " artifact-missing")
            continue
        if p.stat().st_size == 0:
            buckets["artifact_problem"].append(uid + " artifact-empty")
            continue
        try:
            doc = load_doc(p)
        except Exception:
            buckets["artifact_problem"].append(uid + " unparsable")
            continue
        if doc.get("state") != "SUCCESS":
            buckets["not_success"].append(uid + " state=" + str(doc.get("state")))
            continue
        if not osch or not isinstance(osch, str):
            buckets["not_checked"].append(uid + " no-output_schema-declared")
            continue
        status, payload = get_validator(osch)
        if status == "NOT_CHECKED":
            buckets["not_checked"].append(uid + " " + str(payload)[:110])
            continue
        if status == "DEFECT":
            buckets["schema_defect"].append(uid + " " + str(payload)[:110])
            continue
        all_errs = []
        for val in payload:
            try:
                errs = list(val.iter_errors(doc))
            except Exception as ex:
                buckets["schema_defect"].append(uid + " validate-err: " + repr(ex)[:110])
                all_errs = None
                break
            all_errs.extend(errs)
        if all_errs is None:
            continue
        if all_errs:
            e0 = sorted(all_errs, key=lambda e: list(e.path))[0]
            buckets["schema-invalid"].append(uid + " [" + str(list(e0.path))[:70] + "] " + e0.message[:110])
        else:
            buckets["schema-valid"].append(uid)
    for k, v in buckets.items():
        print(k, "=", len(v))
    OUT.write_text(json.dumps(buckets, indent=1), encoding="utf-8")
    print("wrote", OUT)
    print("BUCKET-SUM:", sum(len(v) for v in buckets.values()), "of", len(units))

if __name__ == "__main__":
    main()

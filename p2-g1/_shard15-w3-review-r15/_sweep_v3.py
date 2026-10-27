#!/usr/bin/env python3
# Sweep v3: re-check only the units sweep v2 could not load a validator for.
# Handles: path#/$defs/Fragment, compound "A + B" declarations, profile=X forms.
# Remote https schema refs stay NOT-CHECKED (no network fetch).
import json
from pathlib import Path
from jsonschema.validators import validator_for

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = Path(__file__).resolve().parent / "sweep-v3-results.json"
TARGETS = ['IMP-0001','IMP-0004','IMP-0005','IMP-0006','IMP-0008','IMP-0010','IMP-0028',
 'IMP-0033','IMP-0034','IMP-0036','IMP-0043','IMP-0044','IMP-0045','IMP-0047','IMP-0049',
 'IMP-0051','IMP-0053','IMP-0056','IMP-0062','IMP-0063','IMP-0064','IMP-0067','IMP-0072',
 'IMP-0074','IMP-0075','IMP-0077','IMP-0078','IMP-0082','IMP-0084','IMP-0090','IMP-0094',
 'IMP-0096','IMP-0099','IMP-0100','IMP-0104','IMP-0108','IMP-0110','IMP-0111','IMP-0113',
 'IMP-0127','IMP-0257','IMP-0261','IMP-0262','IMP-0264','IMP-0265','IMP-0276','IMP-0280',
 'IMP-0282','IMP-0290','IMP-0298','IMP-0300','IMP-0302','IMP-0308','IMP-0311','IMP-0313',
 'IMP-0316','IMP-0317','IMP-0318','IMP-0326','IMP-0327','IMP-0328','IMP-0329','IMP-0342',
 'IMP-0344','IMP-0369','IMP-0370','IMP-0371','IMP-0372','IMP-0373','IMP-0374','IMP-0433',
 'IMP-0478','TST-0129','TST-0130','TST-0131','TST-0136','TST-0143','TST-0150','TST-0157',
 'TST-0158','TST-0164','TST-0172','TST-0174','TST-0179','TST-0186','TST-0194','TST-0206',
 'TST-0229','TST-0244','TST-0250','TST-0334','WFA-0002','WFA-0003','WFA-0004','WFA-0007',
 'WFA-0013','WFA-0032','WFA-0043','WFA-0044','WFA-0045','WFA-0056','WFA-0058','WFA-0068',
 'WFA-0078','WFA-0084','WFA-0086','WFA-0100','WFA-0112','WFA-0118','WFA-0129','WFA-0130',
 'WFA-0131','WFA-0132','WFA-0133','WFA-0134','WFA-0135','WFA-0136','WFA-0137','WFA-0138',
 'WFA-0139','WFA-0140','WFA-0141','WFA-0142','WFA-0143','WFA-0144','WFA-0145','WFA-0146',
 'WFA-0147','WFA-0148','WFA-0149','WFA-0150','WFA-0151','WFA-0152','WFA-0153','WFA-0154',
 'WFA-0155','WFA-0156','WFA-0157','WFA-0158','WFA-0159','WFA-0160','ARC-0079']
TARGETS = [t for t in dict.fromkeys(TARGETS)]

def load_doc(p):
    return json.loads(p.read_bytes().decode("utf-8"))

def validator_for_file(relpath):
    s = load_doc(REPO / relpath)
    V = validator_for(s)
    V.check_schema(s)
    return V, s

def main():
    cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
    cu = {u.get("id"): u for u in cat["work_units"]}
    res = {}
    vfile_cache, sfile_cache = {}, {}
    for uid in TARGETS:
        ce = cu.get(uid) or {}
        osch = ce.get("output_schema") or ""
        op = ce.get("output_path")
        p = REPO / op if op else None
        if not p or not p.exists():
            res[uid] = "artifact-missing"
            continue
        try:
            doc = load_doc(p)
        except Exception:
            res[uid] = "artifact-unparsable"
            continue
        if doc.get("state") != "SUCCESS":
            res[uid] = "state=" + str(doc.get("state"))
            continue
        if osch.startswith("http"):
            res[uid] = "NOT-CHECKED remote-schema-url"
            continue
        # split compound declarations on ' + '
        parts = [x.strip() for x in osch.split(" + ") if x.strip()]
        verdicts, problems = [], []
        for part in parts:
            # each part may be "path#/$defs/Frag" possibly followed by 'profile=...' prose
            frag = None
            pathpart = part
            if "#" in pathpart:
                pathpart, frag = pathpart.split("#", 1)
                frag = frag.lstrip("/").replace("$defs/", "$defs/")
            pathpart = pathpart.strip()
            if not pathpart or " " in pathpart:
                # descriptive prose remainder (profile=...) - extract leading token if it looks like a path
                tok = part.split()[0]
                if not tok.endswith(".json"):
                    problems.append("unparseable-decl: " + part[:60])
                    continue
                pathpart = tok
                frag = None
            key = (pathpart, frag)
            if key not in vfile_cache:
                try:
                    V, sroot = validator_for_file(pathpart)
                    if frag:
                        sub = dict(sroot)
                        sub["$ref"] = "#/" + frag
                        try:
                            V.check_schema(sub)
                            entry = (V(sub), V)
                        except Exception:
                            entry = ("SCHEMA-BAD", V)
                    else:
                        entry = (V(sroot), V)
                    vfile_cache[key] = entry
                except Exception as ex:
                    vfile_cache[key] = ("LOAD-ERR", repr(ex)[:140])
            entry = vfile_cache[key]
            if entry[0] == "LOAD-ERR":
                problems.append("schema-load-err " + pathpart + ": " + entry[1][:100])
                continue
            if entry[0] == "SCHEMA-BAD":
                problems.append("schema-self-invalid " + pathpart + "#" + str(frag))
                continue
            val = entry[0]
            try:
                errs = sorted(val.iter_errors(doc), key=lambda e: list(e.path))
            except Exception as ex:
                problems.append("validate-err " + pathpart + ": " + repr(ex)[:100])
                continue
            if errs:
                e0 = errs[0]
                verdicts.append("INVALID " + pathpart + (("#" + frag) if frag else "") +
                                " [" + str(list(e0.path))[:60] + "] " + e0.message[:90])
            else:
                verdicts.append("VALID " + pathpart + (("#" + frag) if frag else ""))
        if problems:
            res[uid] = "PROBLEM: " + " | ".join(problems)
        elif any(v.startswith("INVALID") for v in verdicts):
            res[uid] = "schema-invalid :: " + " | ".join(v for v in verdicts if v.startswith("INVALID"))
        else:
            res[uid] = "schema-valid :: " + " | ".join(verdicts)
    good = sum(1 for v in res.values() if v.startswith("schema-valid"))
    bad = sum(1 for v in res.values() if v.startswith("schema-invalid"))
    nc = sum(1 for v in res.values() if v.startswith("NOT-CHECKED"))
    other = len(res) - good - bad - nc
    OUT.write_text(json.dumps({"valid": good, "invalid": bad, "not_checked": nc, "other": other,
                               "units": res}, indent=1), encoding="utf-8")
    print(json.dumps({"valid": good, "invalid": bad, "not_checked": nc, "other": other}))
    for uid, v in res.items():
        if not v.startswith("schema-valid"):
            print(uid, "->", v[:220])

if __name__ == "__main__":
    main()

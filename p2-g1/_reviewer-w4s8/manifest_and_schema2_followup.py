r"""Follow-ups:
  F1: every artifacts[] row of every unit manifest re-hashed vs live file (CRLF-normalized).
  F2: IMP-0036 secondary deliverable (divergence-decision.schema.json) proven LIVE:
      - meta-schema validity (Draft 2020-12 / declared $schema)
      - both-states: a downstream recorded-decision document (from BLD-0004) validates;
        a stripped/garbage doc fails.
  F3: catalog receipt cross-check already done in resume_verify.py (C5 primary schema).
"""
import glob
import hashlib
import json
import os

os.chdir(os.path.expanduser("~/p2-g1"))

MINE = ["IMP-0002", "IMP-0006", "IMP-0022", "IMP-0031", "IMP-0035",
        "IMP-0036", "IMP-0037", "IMP-0038", "IMP-0041", "IMP-0044",
        "IMP-0051", "IMP-0068"]


def sha_norm(p):
    raw = open(p, "rb").read()
    return (hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
            len(raw), ("CRLF" if b"\r\n" in raw else "LF"))


print("F1: full-manifest row verification")
bad_total = 0
for uid in MINE:
    man = json.load(open(f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json", encoding="utf-8"))
    rows = man.get("artifacts", [])
    bad = []
    for a in rows:
        p = str(a.get("path", "")).replace("\\", "/")
        if not os.path.exists(p):
            bad.append(f"{p}:MISSING")
            continue
        live, nb, eol = sha_norm(p)
        if a.get("sha256") != live:
            bad.append(f"{p}:SHA-DIFF(live={live[:12]} row={str(a.get('sha256'))[:12]})")
        elif a.get("bytes") not in (None, nb):
            bad.append(f"{p}:BYTES-DIFF(live={nb} row={a.get('bytes')})")
    status = "ALL-ROWS-MATCH" if not bad else "BAD:" + ";".join(bad[:4])
    bad_total += len(bad)
    print(f"  {uid}: {len(rows)} rows -> {status}")
print(f"F1 TOTAL: {'ALL ROWS MATCH ACROSS 12 UNITS' if bad_total == 0 else f'{bad_total} bad rows'}")

print()
print("F2: IMP-0036 delivered schema liveness")
import jsonschema  # noqa: E402

schema_path = "tools/plugin/schema/divergence-decision.schema.json"
schema = json.load(open(schema_path, encoding="utf-8"))
declared = schema.get("$schema")
print(f"  declared $schema: {declared}")
try:
    checker = jsonschema.validators.validator_for(schema).CHECKER  # noqa
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    print("  meta-schema check: VALID", f"(validator={cls.__name__})")
except Exception as ex:
    print("  meta-schema check: FAIL", str(ex)[:160])

# downstream decision documents: BLD-0004 receipt carries recorded decisions
def find_decision_doc(path):
    r = json.load(open(path, encoding="utf-8"))
    for k in ("decisions", "answer", "measurement"):
        v = r.get(k)
        if isinstance(v, dict) and "decisions" in v:
            return v
        if isinstance(v, list) and k == "decisions":
            return v
    if isinstance(r.get("decisions"), list):
        return {"artifact": r.get("output_path", path), "decisions": r["decisions"]}
    return None


for cand in ("command-center/receipts/BLD-0004.json", "command-center/receipts/TST-0056.json"):
    doc = find_decision_doc(cand)
    if not doc:
        # dump top keys to see the shape
        r = json.load(open(cand, encoding="utf-8"))
        print(f"  {cand}: no embedded decision doc; keys={sorted(r.keys())[:14]}")
        continue
    try:
        jsonschema.validate(doc, schema)
        print(f"  downstream doc in {cand}: VALIDATES against delivered schema (POSITIVE control)")
    except jsonschema.ValidationError as ex:
        print(f"  downstream doc in {cand}: FAIL: {str(ex.message)[:160]}")
    # negative control: strip a required field -> must FAIL
    if isinstance(doc, dict):
        neg = dict(doc)
        neg.pop("decision_required", None)
        try:
            jsonschema.validate(neg, schema)
            print("  negative control (dropped decision_required): STILL VALID -> schema toothless")
        except jsonschema.ValidationError:
            print("  negative control (dropped decision_required): correctly REJECTED (both-states holds)")
    break

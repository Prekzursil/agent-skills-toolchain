#!/usr/bin/env python3
"""Independent reviewer w4 shard17 r2 - S4 output_schema battery.
Primary instrument: platform/lib/schema_resolver.validate_artifact (blessed).
Second instrument: raw jsonschema Draft202012 on the RESOLVED physical schema.
Controls: known-conforming same-class receipts must stay clean (both-states proof).
"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform"))
from lib.schema_resolver import resolve, validate_artifact  # noqa: E402

UNITS = ["TST-0032","TST-0057","TST-0060","TST-0066","TST-0067","TST-0068",
         "TST-0070","TST-0081","TST-0085","TST-0088","TST-0090","TST-0091"]
CONTROLS = ["TST-0101","TST-0102","TST-0103","TST-0105","TST-0106","TST-0107",
            "TST-0108","TST-0110","TST-0122","TST-0123","TST-0126","TST-0127","AUD-0035"]

cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

def check(uid):
    u = byid[uid]
    out = REPO / str(u["output_path"]).replace("\\", "/")
    doc = json.loads(out.read_text(encoding="utf-8"))
    errs = validate_artifact(doc, u["output_schema"])
    res = resolve(u["output_schema"])
    second = None
    if res.resolves and res.physical_exists:
        import jsonschema
        raw = json.loads((REPO / res.physical_path).read_text(encoding="utf-8"))
        target = raw
        if res.physical_fragment:
            for part in res.physical_fragment.split("/"):
                if part and part != "#":
                    target = target[part.replace("~1", "/").replace("~0", "~")]
        v = jsonschema.Draft202012Validator(target)
        second = ["%s: %s" % ("/".join(map(str, e.absolute_path)), e.message)
                  for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))]
    return {"primary_violations": errs, "primary_count": len(errs),
            "physical_path": res.physical_path,
            "second_count": len(second) if second is not None else None,
            "second_sample": (second or [])[:5]}

result = {"_meta": {"utc": datetime.now(timezone.utc).isoformat()}, "units": {}, "controls": {}}
for uid in UNITS:
    r = check(uid)
    result["units"][uid] = r
    print("%s: primary=%d second=%s  first=%s" % (
        uid, r["primary_count"], r["second_count"], (r["primary_violations"] or ["-"])[0][:110]))
for uid in CONTROLS:
    try:
        r = check(uid)
        result["controls"][uid] = {"primary_count": r["primary_count"], "second_count": r["second_count"]}
    except Exception as e:
        result["controls"][uid] = {"error": str(e)[:120]}
ok = [u for u, v in result["controls"].items() if v.get("primary_count") == 0]
print("controls clean: %d/%d %s" % (len(ok), len(CONTROLS), ok if len(ok) < len(CONTROLS) else ""))

outp = REPO/"_reviewer-w4-shard17-r2"/"schema_results.json"
outp.write_text(json.dumps(result, indent=1), encoding="utf-8")
print("wrote", outp)

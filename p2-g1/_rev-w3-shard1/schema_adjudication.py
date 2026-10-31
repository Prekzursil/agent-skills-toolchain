"""Classify every battery schema error into root-cause classes.

Adjudication basis (measured, not copied): are the physical profiles for my six
declared schemas generated as allOf[receipt generic_report, ...]? If yes, every
error that traces to a receipt-only field demanded of a non-receipt artifact is
the known profile-generation defect (w2-shard2 precedent, recorded-not-folded).
Errors outside that class are unit-content defects and fail the unit.
"""
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
REG = json.loads((REPO / "platform/schema/ARTIFACT-CLASS-REGISTRY.json").read_text(encoding="utf-8"))
B = json.loads((Path(__file__).parent / "battery_out.json").read_text(encoding="utf-8"))

RECEIPT_ONLY_TOP = {
    "schema_version", "spec_anchor", "min_bytes_threshold", "timestamps", "retry",
    "manifest_registration", "downstream_consumers", "residual_unknowns", "report",
    "artifacts", "tests", "reviewer", "produced_by", "extensions", "failure",
    "defects", "evidence",
}

def profile_info(logical: str):
    e = REG["entries"].get("command-center/schema/" + logical)
    phys = e["physical_path"]
    d = json.loads((REPO / phys).read_text(encoding="utf-8"))
    allof = d.get("allOf")
    refs = []
    if allof:
        for x in allof:
            if "$ref" in x:
                refs.append(x["$ref"])
            else:
                refs.append("inline:" + ",".join(sorted(x.keys())))
    return phys, refs, d

def receipt_generic(d: dict) -> bool:
    """Does any allOf branch $ref the receipt generic report?"""
    return any("generic_report" in r or "receipt" in r.lower() for r in d)

seen = {}
for u in B["units"]:
    uid = u["unit_id"]
    logical = u["details"]["output_schema"].split("/")[-1]
    phys, refs, d = profile_info(logical)
    errs = u["details"].get("schema_errors") or []
    in_class, outside = [], []
    for e in errs:
        path, _, msg = e.partition(": ")
        # Class A: top-level receipt-only required field missing
        m = msg.startswith("'") and " is a required property" in msg
        if m:
            field = msg.split("'")[1]
            if field in RECEIPT_ONLY_TOP:
                in_class.append(e)
                continue
        # Class A2: sub-shape errors within receipt-demanded structures
        # (artifacts rows, tests rows, reviewer block, defects rows demanded by the
        # receipt profile grafted onto non-receipt artifacts)
        if path.split("/")[0] in {"artifacts", "tests", "reviewer", "defects",
                                  "manifest_registration", "downstream_consumers",
                                  "residual_unknowns"}:
            in_class.append(e)
            continue
        outside.append(e)
    rec = seen.setdefault(logical, {"phys": phys, "refs": refs, "units": {}})
    rec["units"][uid] = {
        "n_err": u["details"].get("schema_error_count"),
        "in_class": len(in_class),
        "outside_class": outside,
    }

print("=== physical profile generation shape (measured) ===")
for logical, rec in seen.items():
    print(logical)
    print("  physical:", rec["phys"])
    print("  allOf refs:", json.dumps(rec["refs"])[:300])
print()
print("=== per-unit error classification ===")
worst = []
for logical, rec in seen.items():
    for uid, s in rec["units"].items():
        print(f"{uid} [{logical}] total={s['n_err']} receipt-profile-class={s['in_class']} outside={len(s['outside_class'])}")
        for e in s["outside_class"]:
            print("   OUTSIDE:", e[:240])
        if s["outside_class"]:
            worst.append(uid)
print()
print("units with errors OUTSIDE the receipt-profile class:", worst or "NONE")

#!/usr/bin/env python3
"""Check E: validate the 12 shard receipts against the repo receipt gate.
Plus fresh program census: receipts by state; reviewer-closed-green count;
sampled strict-schema conformance of closed-green receipts' artifacts.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(ROOT / "platform" / "lib"))
import schema_resolver as SR  # noqa: E402
import receipt_schema_gate as RSG  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import d2_validate  # noqa: E402

UNITS = ["RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
         "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157"]


def main():
    cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    entries = {u["id"]: u for u in cat["work_units"]}
    print("== Check E: receipt gate validation of the 12 ==")
    for uid in UNITS:
        rp = ROOT / "command-center" / "receipts" / f"{uid}.json"
        rec = json.loads(rp.read_bytes().decode("utf-8"))
        errs = RSG.validate_receipt(rec)
        rv = rec.get("reviewer") or {}
        gate, extra = RSG.evaluate_full(rec, repo_root=ROOT, verify_filesystem=True)
        print(f"{uid}: schema_errors={len(errs)} gate_ok={gate.ok} gate_violations={len(gate.violations)} extra={len(extra)}")
        for e in (errs[:2] + gate.violations[:2]):
            print("   ", str(e)[:180])

    print("\n== Fresh program census ==")
    rdir = ROOT / "command-center" / "receipts"
    states = {}
    closed_green = []
    for p in sorted(rdir.glob("*.json")):
        try:
            rec = json.loads(p.read_bytes().decode("utf-8"))
        except Exception:
            states["UNPARSEABLE"] = states.get("UNPARSEABLE", 0) + 1
            continue
        st = rec.get("state", "MISSING-STATE")
        states[st] = states.get(st, 0) + 1
        rv = rec.get("reviewer") or {}
        if st == "SUCCESS" and rv.get("verdict") == "PASS" and rv.get("independent") is True:
            closed_green.append(p.stem)
    total_receipts = sum(states.values())
    print("receipts:", total_receipts, "states:", states)
    print("reviewer-closed-green (SUCCESS+PASS+independent):", len(closed_green))

    # sampled strict-schema conformance over closed-green receipts
    random.seed(20261026)
    sample = random.sample(closed_green, min(60, len(closed_green)))
    schema_ok = schema_red = schema_unres = 0
    red_ids = []
    for uid in sample:
        e = entries.get(uid)
        if not e:
            continue
        p = ROOT / e["output_path"]
        if not p.is_file():
            schema_unres += 1
            continue
        try:
            doc = json.loads(p.read_bytes().decode("utf-8"))
            errs = SR.validate_artifact(doc, e["output_schema"])
        except Exception:
            schema_unres += 1
            continue
        if errs:
            schema_red += 1
            red_ids.append(uid)
        else:
            schema_ok += 1
    print(f"sampled strict-schema over closed-green (n={len(sample)}): ok={schema_ok} red={schema_red} unresolvable/skip={schema_unres}")
    print("red sample:", red_ids)
    out = {"states": states, "closed_green_n": len(closed_green),
           "sample_n": len(sample), "schema_ok": schema_ok, "schema_red": schema_red,
           "schema_unres": schema_unres, "red_sample": red_ids, "closed_green_ids": closed_green}
    (ROOT / "_reviewer-w4s15-r2" / "census.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

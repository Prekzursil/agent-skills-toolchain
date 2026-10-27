#!/usr/bin/env python3
"""Independent reviewer battery, wave-4 shard-21 (12 TST units)."""
from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
os.chdir(REPO)
sys.path.insert(0, str(REPO / "platform" / "lib"))

UNITS = ["TST-0206","TST-0215","TST-0219","TST-0221","TST-0223","TST-0227",
         "TST-0230","TST-0233","TST-0236","TST-0238","TST-0243","TST-0245"]

def sha_lf(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def main():
    cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}
    reg = json.loads((REPO/"platform/schema/ARTIFACT-CLASS-REGISTRY.json").read_bytes().decode("utf-8"))
    import schema_resolver
    out = {}
    for uid in UNITS:
        row = {"unit": uid}
        u = wu.get(uid)
        row["catalog_present"] = u is not None
        if u is None:
            out[uid] = row; continue
        row["catalog_fields"] = {k: bool(u.get(k)) for k in
            ("output_path","output_schema","probes","dependencies","description")}
        op = REPO / u["output_path"]
        row["output_path"] = u["output_path"]
        row["exists"] = op.is_file()
        if not op.is_file():
            out[uid] = row; continue
        raw = op.read_bytes()
        row["bytes"] = len(raw)
        row["nonempty"] = len(raw) > 0
        try:
            art = json.loads(raw.decode("utf-8"))
            row["parses"] = True
        except Exception as e:
            row["parses"] = False; row["parse_err"] = str(e)[:200]
            out[uid] = row; continue
        st = art.get("state")
        sent = str(art.get("sentinel", ""))
        row["state"] = st
        row["sentinel_head"] = sent[:90]
        row["self_declared_failed"] = (st in ("BLOCKED","FAILED")) or sent.startswith(("FAILED:","BLOCKED:"))
        row["schema_state_consistent"] = not (st == "SUCCESS" and sent.startswith(("FAILED:","BLOCKED:")))
        row["declared_output_schema"] = u["output_schema"]
        row["receipt_output_schema_field"] = art.get("output_schema")
        row["schema_field_matches_catalog"] = art.get("output_schema") == u["output_schema"]
        rev = art.get("reviewer", {}) or {}
        row["closure"] = {"state": st, "verdict": rev.get("verdict"),
                          "independent": rev.get("independent"),
                          "reviewer_id": str(rev.get("reviewer_id"))[:80]}
        out[uid] = row
    return out, wu, reg, schema_resolver

def battery_part2(out, wu, reg, schema_resolver):
    REPOX = REPO
    for uid in UNITS:
        row = out.get(uid, {})
        if not row.get("parses"):
            continue
        u = wu[uid]
        art = json.loads((REPOX / u["output_path"]).read_bytes().decode("utf-8"))
        mp = REPOX / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        row["manifest_exists"] = mp.is_file()
        if mp.is_file():
            m = json.loads(mp.read_bytes().decode("utf-8"))
            prim = [a for a in m.get("artifacts", []) if a.get("role") == "primary"]
            row["manifest_primary_rows"] = len(prim)
            if prim:
                p0 = prim[0]
                row["manifest_primary_path"] = p0.get("path")
                row["manifest_path_matches_catalog"] = p0.get("path") == u["output_path"]
                live_sha, live_n = sha_lf(REPOX / u["output_path"])
                row["recomputed_sha256"] = live_sha
                row["manifest_sha256"] = p0.get("sha256")
                row["sha_match"] = (p0.get("sha256") == live_sha)
                row["bytes_match"] = (p0.get("bytes") == live_n)
            mism = []
            for a in m.get("artifacts", []):
                if a.get("role") == "primary":
                    continue
                ap = REPOX / a["path"]
                if not ap.is_file():
                    mism.append({"path": a["path"], "problem": "absent"})
                    continue
                s, n = sha_lf(ap)
                if s != a.get("sha256"):
                    mism.append({"path": a["path"], "problem": "sha-mismatch"})
            row["nonprimary_row_mismatches"] = mism
        try:
            errs1 = schema_resolver.validate_artifact(art, u["output_schema"])
            row["t1_error_count"] = len(errs1)
            row["t1_errors"] = errs1[:6]
        except Exception as e:
            row["t1_error_count"] = -1
            row["t1_exception"] = (type(e).__name__ + ": " + str(e))[:300]
        try:
            logical, frag = u["output_schema"].split("#", 1)
            entry = reg["entries"][logical.replace("\\", "/")]
            name = frag.rstrip("/").split("/")[-1]
            kf = entry["fragments"][name]
            phys = REPOX / kf["physical_path"]
            from jsonschema import Draft202012Validator
            pf = kf.get("physical_fragment")
            if pf:
                uri = phys.resolve().as_uri() + pf
                v = Draft202012Validator({"$ref": uri})
            else:
                v = Draft202012Validator(json.loads(phys.read_bytes().decode("utf-8")))
            errs2 = sorted(
                ("/".join(str(p) for p in e.absolute_path) or "<root>") + ": " + e.message
                for e in v.iter_errors(art))
            row["t2_error_count"] = len(errs2)
            row["t2_errors"] = errs2[:6]
        except Exception as e:
            row["t2_error_count"] = -1
            row["t2_exception"] = (type(e).__name__ + ": " + str(e))[:300]
    return out

if __name__ == "__main__":
    out, wu, reg, sr = main()
    out = battery_part2(out, wu, reg, sr)
    print(json.dumps(out, indent=1))

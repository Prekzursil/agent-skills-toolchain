#!/usr/bin/env python3
"""Fresh independent reviewer battery, wave-4 shard-21 (12 TST units). Run 2026-10-26 by the re-dispatched reviewer (run r2)."""
from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
os.chdir(REPO)
sys.path.insert(0, str(REPO / "platform" / "lib"))

UNITS = ["TST-0206","TST-0215","TST-0219","TST-0221","TST-0223","TST-0227",
         "TST-0230","TST-0233","TST-0236","TST-0238","TST-0243","TST-0245"]


def sha_lf(p: Path):
    raw = p.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(lf).hexdigest(), len(lf), len(raw)


def probe_commands(uid: str):
    """Named probes from SUBAGENT-RETURN.json; fallback to probe*.py in the unit probe dir."""
    ret = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    cmds = []
    if ret.is_file():
        try:
            d = json.loads(ret.read_bytes().decode("utf-8"))
            for np in d.get("named_probes", []):
                c = np.get("command")
                if c:
                    cmds.append(c)
        except Exception:
            pass
    if not cmds:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        rels = sorted(str(p.relative_to(REPO)) for p in pdir.glob("probe*.py"))
        cmds = ["python -B " + r for r in rels]
    return cmds


def main() -> dict:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}
    reg = json.loads((REPO / "platform/schema/ARTIFACT-CLASS-REGISTRY.json").read_bytes().decode("utf-8"))
    import schema_resolver
    out = {}
    for uid in UNITS:
        row = {"unit": uid}
        u = wu.get(uid)
        row["catalog_present"] = u is not None
        if u is None:
            out[uid] = row
            continue
        row["catalog_fields"] = {k: bool(u.get(k)) for k in
                                 ("output_path", "output_schema", "probes", "dependencies", "description")}
        op = REPO / u["output_path"]
        row["output_path"] = u["output_path"]
        row["exists"] = op.is_file()
        if not op.is_file():
            out[uid] = row
            continue
        raw = op.read_bytes()
        row["bytes_raw"] = len(raw)
        row["nonempty"] = len(raw) > 0
        try:
            art = json.loads(raw.decode("utf-8"))
            row["parses"] = True
        except Exception as e:
            row["parses"] = False
            row["parse_err"] = str(e)[:200]
            out[uid] = row
            continue
        st = art.get("state")
        sent = str(art.get("sentinel", ""))
        row["state"] = st
        row["sentinel_head"] = sent[:90]
        row["self_declared_failed"] = (st in ("BLOCKED", "FAILED")) or sent.startswith(("FAILED:", "BLOCKED:"))
        row["schema_state_consistent"] = not (st == "SUCCESS" and sent.startswith(("FAILED:", "BLOCKED:")))
        row["declared_output_schema"] = u["output_schema"]
        row["receipt_output_schema_field"] = art.get("output_schema")
        row["schema_field_matches_catalog"] = art.get("output_schema") == u["output_schema"]
        rev = art.get("reviewer", {}) or {}
        row["closure"] = {"state": st, "verdict": rev.get("verdict"),
                          "independent": rev.get("independent"),
                          "reviewer_id": str(rev.get("reviewer_id"))[:80]}
        rg = art.get("reviewer_gate")
        if isinstance(rg, dict):
            row["reviewer_gate"] = {k: rg.get(k) for k in ("required_count", "completed_count") if k in rg}
        # manifest
        mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        row["manifest_exists"] = mp.is_file()
        if mp.is_file():
            m = json.loads(mp.read_bytes().decode("utf-8"))
            prim = [a for a in m.get("artifacts", []) if a.get("role") == "primary"]
            row["manifest_primary_rows"] = len(prim)
            if prim:
                p0 = prim[0]
                row["manifest_primary_path"] = p0.get("path")
                row["manifest_path_matches_catalog"] = p0.get("path") == u["output_path"]
                live_sha, live_n, raw_n = sha_lf(REPO / u["output_path"])
                row["recomputed_sha256"] = live_sha
                row["manifest_sha256"] = p0.get("sha256")
                row["sha_match"] = (p0.get("sha256") == live_sha)
                row["bytes_match"] = (p0.get("bytes") == live_n)
                row["bytes_live_lf"] = live_n
            mism = []
            for a in m.get("artifacts", []):
                if a.get("role") == "primary":
                    continue
                ap = REPO / a["path"]
                if not ap.is_file():
                    mism.append({"path": a["path"], "problem": "absent"})
                    continue
                s, n, _ = sha_lf(ap)
                if s != a.get("sha256"):
                    mism.append({"path": a["path"], "problem": "sha-mismatch"})
            row["nonprimary_row_mismatches"] = mism
        row["probe_commands"] = probe_commands(uid)
        # schema transport 1: platform resolver
        try:
            errs1 = schema_resolver.validate_artifact(art, u["output_schema"])
            row["t1_error_count"] = len(errs1)
            row["t1_errors"] = errs1[:6]
        except Exception as e:
            row["t1_error_count"] = -1
            row["t1_exception"] = (type(e).__name__ + ": " + str(e))[:300]
        # schema transport 2: raw jsonschema on registry-resolved physical fragment
        try:
            logical, frag = u["output_schema"].split("#", 1)
            entry = reg["entries"][logical.replace("\\", "/")]
            name = frag.rstrip("/").split("/")[-1]
            kf = entry["fragments"][name]
            phys = REPO / kf["physical_path"]
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
        out[uid] = row
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))

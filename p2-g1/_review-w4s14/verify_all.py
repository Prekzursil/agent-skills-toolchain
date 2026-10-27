#!/usr/bin/env python3
"""Independent reviewer verification, wave 4 shard 14 (12 units)."""
from __future__ import annotations
import hashlib, json, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = ["REL-0017","REL-0020","REL-0021","REL-0022","RES-0004","RES-0009","RES-0011",
       "RES-0037","RES-0044","RES-0049","RES-0077","RES-0079"]

def lf_digest(raw: bytes):
    norm = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)

def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    cat = load(REPO / "command-center/WORK-UNIT-CATALOG.json")
    units = {u["id"]: u for u in cat["work_units"]}
    out = {}
    for uid in IDS:
        u = units[uid]
        r = {"id": uid, "checks": {}, "probe_runs": []}
        op = REPO / u["output_path"]
        if not op.is_file():
            r["checks"]["A_exists"] = "FAIL missing " + u["output_path"]
            art = None
        else:
            raw = op.read_bytes()
            r["checks"]["A_nonempty"] = "PASS" if len(raw) > 0 else "FAIL 0 bytes"
            try:
                art = json.loads(raw.decode("utf-8"))
                r["checks"]["A_parses"] = "PASS"
                st = art.get("state")
                if st in ("BLOCKED", "FAILED"):
                    r["checks"]["A_notselfblocked"] = "FAIL artifact state=" + str(st)
                else:
                    r["checks"]["A_notselfblocked"] = "PASS state=" + repr(st)
            except Exception as e:
                r["checks"]["A_parses"] = "FAIL " + type(e).__name__ + ": " + str(e)[:120]
                art = None
        # B. manifest sha
        man_p = REPO / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
        if not man_p.is_file():
            r["checks"]["B_manifest"] = "FAIL no per-unit manifest"
        else:
            man = load(man_p)
            rows = [a for a in man.get("artifacts", [])
                    if str(a.get("path", "")).replace(chr(92), "/") == u["output_path"]]
            if not rows:
                r["checks"]["B_manifest"] = "FAIL manifest has no row for " + u["output_path"]
            elif not op.is_file():
                r["checks"]["B_manifest"] = "FAIL artifact missing"
            else:
                row = rows[0]
                sha, nb = lf_digest(op.read_bytes())
                msha = row.get("sha256")
                if sha == msha:
                    r["checks"]["B_manifest"] = "PASS"
                else:
                    r["checks"]["B_manifest"] = ("FAIL live=" + str(sha) + " manifest=" + str(msha)
                                                 + " livebytes=" + str(nb) + " manbytes=" + str(row.get("bytes")))
        # C. probes
        pdir = REPO / ("command-center/p2-wave/probes/" + uid)
        probes = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
        if not probes:
            r["checks"]["C_probes"] = "FAIL no probe scripts"
        else:
            results = []
            all_ok = True
            for p in probes:
                t0 = time.time()
                try:
                    proc = subprocess.run([sys.executable, "-B", str(p)], cwd=str(REPO),
                                          capture_output=True, text=True, timeout=900)
                    ok = proc.returncode == 0
                    lines = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
                    results.append({"probe": p.name, "rc": proc.returncode,
                                    "secs": round(time.time() - t0, 1),
                                    "tail": lines[-2:] if lines else []})
                    if not ok:
                        all_ok = False
                except subprocess.TimeoutExpired:
                    results.append({"probe": p.name, "rc": "TIMEOUT",
                                    "secs": round(time.time() - t0, 1)})
                    all_ok = False
            r["probe_runs"] = results
            r["checks"]["C_probes"] = "PASS" if all_ok else "FAIL see probe_runs"
        # D. schema
        sch_p = REPO / u["output_schema"]
        if not sch_p.is_file():
            r["checks"]["D_schema"] = "FAIL schema file missing " + u["output_schema"]
        elif art is None:
            r["checks"]["D_schema"] = "SKIP artifact unparseable"
        else:
            try:
                import jsonschema
                schema = load(sch_p)
                jsonschema.validate(art, schema)
                r["checks"]["D_schema"] = "PASS"
            except Exception as e:
                r["checks"]["D_schema"] = "FAIL " + type(e).__name__ + ": " + str(e)[:300]
        r["verdict"] = "PASS" if all(str(v).startswith("PASS") for v in r["checks"].values()) else "FAIL"
        out[uid] = r
        print(uid + ": " + r["verdict"] + "  " + json.dumps(r["checks"])[:400], flush=True)
    (REPO / "_review-w4s14/verify_out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("")
    print("SUMMARY:", {k: v["verdict"] for k, v in out.items()})

if __name__ == "__main__":
    main()

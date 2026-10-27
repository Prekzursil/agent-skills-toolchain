#!/usr/bin/env python3
"""Battery docstring."""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_p2shard23-w2-indep-review"
IDS = ["TST-0113","TST-0124","TST-0129","TST-0130","TST-0136","TST-0137",
       "TST-0138","TST-0139","TST-0141","TST-0142","TST-0143","TST-0144"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}

def sha_norm(b): return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()
def sha_raw(b):  return hashlib.sha256(b).hexdigest()

def load_gate():
    spec = importlib.util.spec_from_file_location(
        "rsg", REPO / "platform/lib/receipt_schema_gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rsg"] = mod
    spec.loader.exec_module(mod)
    return mod

GATE = load_gate()

def run_probe(path, timeout=180):
    try:
        p = subprocess.run([sys.executable, str(path)], cwd=str(REPO),
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, "SPAWN-ERR " + type(e).__name__ + ": " + str(e)

def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    entries = {u["id"]: u for u in cat["work_units"] if u.get("id") in IDS}
    report = {}
    for uid in IDS:
        R = {"id": uid, "holds": []}
        e = entries.get(uid)
        if not e:
            R["verdict"] = "FAIL"; R["reason"] = "no catalog entry"
            report[uid] = R; continue
        opath = e.get("output_path"); osch = e.get("output_schema")
        R["catalog"] = {"output_path": opath, "output_schema": osch,
                        "owner_approval_required": e.get("owner_approval_required")}
        af = REPO / opath
        exists = af.is_file(); size = af.stat().st_size if exists else 0
        doc = None; parse_err = ""
        if exists:
            try: doc = json.loads(af.read_text(encoding="utf-8"))
            except Exception as exc: parse_err = type(exc).__name__
        state = (doc or {}).get("state", "")
        R["artifact"] = {"exists": exists, "bytes": size, "parses": doc is not None,
                         "parse_err": parse_err, "state": state,
                         "self_blocked": state in NOT_DELIVERING,
                         "min_bytes": (doc or {}).get("min_bytes_threshold")}
        if not exists: R["holds"].append("artifact-missing")
        if size <= 0: R["holds"].append("artifact-empty")
        if doc is None: R["holds"].append("artifact-unparsable:" + parse_err)
        if state in NOT_DELIVERING: R["holds"].append("self-declared:" + str(state))
        man_p = REPO / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")
        rows_out = []
        primary_ok = False
        if man_p.is_file():
            man = json.loads(man_p.read_text(encoding="utf-8"))
            for row in man.get("artifacts", []):
                rp = REPO / row["path"]
                rb = rp.read_bytes() if rp.is_file() else None
                sn = sha_norm(rb) if rb is not None else None
                sr = sha_raw(rb) if rb is not None else None
                match = (rb is not None) and ((sn == row.get("sha256")) or (sr == row.get("sha256")))
                rec = {"path": row["path"], "role": row.get("role"),
                       "live": rb is not None,
                       "norm_match": (sn == row.get("sha256")) if rb is not None else None,
                       "raw_match": (sr == row.get("sha256")) if rb is not None else None,
                       "row_sha": str(row.get("sha256", ""))[:12],
                       "live_sha": (sn or "")[:12] if rb is not None else None,
                       "bytes_row": row.get("bytes"), "bytes_live": len(rb) if rb is not None else None}
                rows_out.append(rec)
                if row["path"].replace("\\", "/") == opath.replace("\\", "/"):
                    primary_ok = match
                    R["primary_manifest_row"] = rec
            R["manifest"] = {"exists": True, "rows": rows_out, "primary_ok": primary_ok}
        else:
            R["manifest"] = {"exists": False}
            R["holds"].append("manifest-missing")
        if not primary_ok: R["holds"].append("manifest-primary-sha-mismatch")
        probes = sorted((REPO / ("command-center/p2-wave/probes/" + uid)).glob("probe*.py"))
        pr = []
        for pp in probes:
            rc, out = run_probe(pp)
            marker = "SUCCESS:" + uid + "-"
            pr.append({"probe": pp.name, "rc": rc,
                       "marker_ok": (rc == 0 and marker in out),
                       "tail": (out.strip().splitlines()[-1][:220] if out.strip() else "")})
            if rc != 0: R["holds"].append("probe-rc:" + pp.name + ":" + str(rc))
            elif marker not in out: R["holds"].append("probe-no-marker:" + pp.name)
        R["probes"] = pr
        if doc is not None:
            errs_core = GATE.validate_receipt(doc)
            R["schema_receipt_core_errors"] = errs_core[:12]
            R["schema_receipt_core_count"] = len(errs_core)
            if errs_core: R["holds"].append("schema-receipt_core:" + str(len(errs_core)) + "-errors")
            rep = doc.get("report")
            class_errs = []
            if not isinstance(rep, dict):
                class_errs.append("report-missing")
            else:
                if rep.get("kind") != "test-receipt": class_errs.append("report.kind!=test-receipt")
                obs = rep.get("observations")
                if not isinstance(obs, list) or len(obs) < 1: class_errs.append("report.observations-minItems-1")
                else:
                    for i, o in enumerate(obs):
                        for k in ("name", "measured", "method", "anchor"):
                            if not isinstance(o, dict) or not o.get(k):
                                class_errs.append("report.observations/" + str(i) + "." + k + "-required")
                if not isinstance(rep.get("control_ids"), list) or len(rep.get("control_ids") or []) < 1:
                    class_errs.append("report.control_ids-minItems-1")
            R["schema_class_errors"] = class_errs
            if class_errs: R["holds"].append("schema-test-receipt-class:" + ";".join(class_errs[:3]))
            rv = doc.get("reviewer") or {}
            rv_ok = (rv.get("verdict") == "PASS" and rv.get("independent") is True)
            R["reviewer"] = {"verdict": rv.get("verdict"), "independent": rv.get("independent"),
                             "reviewer_id": rv.get("reviewer_id"), "invariant_ok": rv_ok}
            if not rv_ok: R["holds"].append("receipt_core-reviewer-invariant")
            sent = str(doc.get("sentinel") or "")
            if state == "SUCCESS" and not sent.startswith(("SUCCESS:", "SENTINEL:")):
                R["holds"].append("sentinel-not-success-family:" + sent[:60])
            ev = doc.get("evidence") or []
            if state == "SUCCESS" and len(ev) < 2: R["holds"].append("evidence:" + str(len(ev)) + "<2")
            tests = doc.get("tests") or []
            bad_tests = [str(t.get("id", i)) for i, t in enumerate(tests)
                         if isinstance(t, dict) and t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN")]
            if state == "SUCCESS":
                if len(tests) < 1: R["holds"].append("tests-empty")
                if bad_tests: R["holds"].append("tests-bad-results:" + ",".join(bad_tests[:4]))
            ncs = doc.get("negative_controls") or []
            nc_bad = []
            for i, nc in enumerate(ncs):
                if isinstance(nc, dict):
                    if nc.get("fired_on_bad_state") is False: nc_bad.append(str(i) + ":fired_on_bad_state=false")
                    if nc.get("silent_on_good_state") is False: nc_bad.append(str(i) + ":silent_on_good_state=false")
            if state == "SUCCESS":
                if len(ncs) < 1: R["holds"].append("negative_controls-empty")
                if nc_bad: R["holds"].append("negative_controls-both-states:" + ",".join(nc_bad[:3]))
            mr = doc.get("manifest_registration")
            if state == "SUCCESS" and not (isinstance(mr, dict) and mr.get("registered") is True):
                R["holds"].append("manifest_registration:" + ("missing" if mr is None else json.dumps(mr)[:80]))
            dcs = doc.get("downstream_consumers")
            if state == "SUCCESS":
                if not isinstance(dcs, list) or len(dcs) < 1:
                    R["holds"].append("downstream_consumers-missing/empty")
                else:
                    for i, d in enumerate(dcs):
                        if isinstance(d, dict):
                            if d.get("executed") is False: R["holds"].append("downstream/" + str(i) + "-not-executed")
                            if d.get("read_ok") is False: R["holds"].append("downstream/" + str(i) + "-read-failed")
            defects = doc.get("defects") or []
            open_p01 = [str(d.get("id", i)) for i, d in enumerate(defects)
                        if isinstance(d, dict) and d.get("severity") in ("P0", "P1") and d.get("status") == "open"]
            if open_p01: R["holds"].append("open-P0P1:" + ",".join(open_p01[:3]))
            for i, ru in enumerate(doc.get("residual_unknowns") or []):
                if isinstance(ru, dict) and not ru.get("settling_experiment"):
                    R["holds"].append("residual_unknown/" + str(i) + "-no-settling-experiment")
            if str(doc.get("output_path") or "") != opath:
                R["holds"].append("receipt-output-path!=catalog:" + str(doc.get("output_path")))
        R["verdict"] = "FAIL" if R["holds"] else "PASS"
        report[uid] = R
    (OUT / "battery_out.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for uid in IDS:
        R = report[uid]
        line = uid + ": " + str(R.get("verdict"))
        if R["holds"]: line += "  holds=" + " | ".join(R["holds"])
        print(line)
    n_fail = sum(1 for R in report.values() if R.get("verdict") == "FAIL")
    print("---- " + str(12 - n_fail) + "/12 PASS, " + str(n_fail) + "/12 FAIL")

if __name__ == "__main__":
    main()

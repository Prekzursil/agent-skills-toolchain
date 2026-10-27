"""INDEPENDENT REVIEWER wave 3 shard 12 - adversarial verification battery.
Units: IMP-0264,0269,0270-0275,0279,0303,0304,0306 (12).
Legs per unit:
  A artifact (exists/non-empty/parses/not-self-blocked/sentinel),
  B output_schema (program resolver + profile required fields + admission CLI),
  C live probes re-run (exit 0 + pass flag + SUCCESS line),
  D manifest sha256 rows (CRLF->LF) vs live bytes,
  E closure fields (state/reviewer/independent),
  F receipts-untouched proof (pre/post sha+mtime, asserted by caller).
Controls: resolver on foreign receipts IMP-0001/0021/0067 (expect 0 errors);
negative mutation control (expect errors).
"""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr

UNITS = ["IMP-0264","IMP-0269","IMP-0270","IMP-0271","IMP-0272","IMP-0273",
         "IMP-0274","IMP-0275","IMP-0279","IMP-0303","IMP-0304","IMP-0306"]
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}
PROBES = REPO / "command-center/p2-wave/probes"

def digest_lf(p):
    norm = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)

def fstate(p):
    st = p.stat()
    return {"sha256_lf": digest_lf(p)[0], "bytes": st.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime))}

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict)}

def profile_required(schema_str):
    m = re.search(r"required:\s*([^)]+)\)", schema_str or "")
    if not m:
        return []
    out = []
    for tok in m.group(1).split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.endswith("[]"):
            out.append((tok[:-2], True))
        else:
            out.append((tok, False))
    return out

results, controls = {}, {}

# ---- controls ----
for ctl in ["IMP-0001","IMP-0021","IMP-0067"]:
    d = json.loads((REPO/("command-center/receipts/%s.json" % ctl)).read_text(encoding="utf-8"))
    errs = sr.validate_artifact(d, byid[ctl]["output_schema"])
    controls[ctl] = {"errors": len(errs), "first": errs[:2]}
neg = json.loads((REPO/"command-center/receipts/IMP-0264.json").read_text(encoding="utf-8"))
neg.pop("unit_id", None)
negmut = sr.validate_artifact(neg, byid["IMP-0264"]["output_schema"])
controls["negative_mutation_IMP-0264_minus_unit_id"] = {"errors": len(negmut), "expect_gt0": len(negmut) > 0}

env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")

for uid in UNITS:
    u = byid[uid]
    r = {"unit": uid}
    out_rel = str(u["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    r["output_path"] = out_rel
    r["pre_state"] = fstate(out) if out.is_file() else None

    # A: artifact legs
    if not out.is_file():
        r["A"] = {"artifact": "FAIL absent"}; results[uid] = r; continue
    if out.stat().st_size <= 0:
        r["A"] = {"artifact": "FAIL empty"}; results[uid] = r; continue
    try:
        text = out.read_text(encoding="utf-8"); doc = json.loads(text)
    except Exception as e:
        r["A"] = {"artifact": "FAIL unparseable %s" % type(e).__name__}; results[uid] = r; continue
    st = str(doc.get("state") or "").upper()
    r["A"] = {
        "artifact": "ok", "state": st,
        "self_blocked": st in NOT_DELIVERING,
        "sentinel_present": str(u.get("completion_sentinel") or "") in text,
    }

    # B: schema legs
    errs = sr.validate_artifact(doc, u["output_schema"])
    prof = []
    for name, is_list in profile_required(u.get("output_schema")):
        v = doc.get(name)
        bad = (v is None) or (is_list and not (isinstance(v, list) and len(v) > 0))
        if bad:
            prof.append(name + ("[]" if is_list else ""))
    adm = subprocess.run([sys.executable, "command-center/receipt_validate.py", out_rel],
                         cwd=str(REPO), env=env, capture_output=True, text=True, timeout=120)
    adm_line = (adm.stdout or "").strip().splitlines()
    adm_bit = next((ln for ln in adm_line if ln.startswith(("ACCEPT", "REJECT"))), "NO-BIT rc=%s" % adm.returncode)
    r["B"] = {"resolver_errors": len(errs), "resolver_first3": errs[:3], "full_errors": errs,
              "profile_missing": prof, "admission": adm_bit[:200]}

    # C: live probes
    ret_p = PROBES/uid/"SUBAGENT-RETURN.json"; man_p = PROBES/uid/"UNIT-ARTIFACT-MANIFEST.json"
    r["C"] = {"subagent_return_present": ret_p.is_file(), "manifest_present": man_p.is_file()}
    probes = []
    if ret_p.is_file():
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        r["C"]["return_status"] = rst; r["C"]["return_blocked"] = rst in NOT_DELIVERING
        for npd in (ret.get("named_probes") or []):
            if not isinstance(npd, dict):
                continue
            cmd = str(npd.get("command") or ""); pid = str(npd.get("id") or "?")
            m = re.search(r"(\S+\.py)\s*$", cmd)
            entry = {"id": pid, "recorded": cmd}
            if not m:
                entry.update(rc=None, fail="no .py path in recorded command")
            else:
                script = m.group(1).replace("\\", "/")
                sp = REPO / script if not Path(script).is_absolute() else Path(script)
                entry["script"] = script
                if not sp.is_file():
                    entry.update(rc=None, fail="probe-script-absent")
                else:
                    t0 = time.time()
                    pr = subprocess.run([sys.executable, "-B", str(sp)], cwd=str(REPO),
                                        env=env, capture_output=True, text=True, timeout=240)
                    entry["rc"] = pr.returncode; entry["secs"] = round(time.time()-t0, 2)
                    so = pr.stdout or ""
                    passed = None
                    for ln in reversed(so.strip().splitlines()):
                        ln = ln.strip()
                        if ln.startswith("{"):
                            try:
                                passed = bool(json.loads(ln).get("pass")); break
                            except Exception:
                                pass
                    entry["json_pass_flag"] = passed
                    entry["success_line"] = "SUCCESS:" in so
                    if pr.returncode != 0:
                        entry["stderr_tail"] = (pr.stderr or "")[-400:]
            probes.append(entry)
    r["C"]["probes"] = probes
    r["C"]["all_exit0"] = bool(probes) and all(p.get("rc") == 0 and p.get("json_pass_flag") is not False for p in probes)

    # D: manifest rows vs live
    rows = []
    if man_p.is_file():
        man = json.loads(man_p.read_text(encoding="utf-8"))
        for a in (man.get("artifacts") or []):
            if not isinstance(a, dict):
                continue
            ap = str(a.get("path") or "").replace("\\", "/")
            live_p = REPO / ap if not Path(ap).is_absolute() else Path(ap)
            row = {"path": ap, "role": a.get("role"), "manifest_present_flag": a.get("present")}
            if not live_p.is_file():
                row["live"] = "ABSENT"
            else:
                lsha, lbytes = digest_lf(live_p)
                row["live_sha12"] = lsha[:12]; row["live_bytes"] = lbytes
                row["manifest_sha12"] = str(a.get("sha256") or "")[:12]; row["manifest_bytes"] = a.get("bytes")
                row["match"] = (str(a.get("sha256") or "") == lsha)
            rows.append(row)
    r["D"] = {"rows": rows,
              "receipt_row_match": any(x["path"] == out_rel and x.get("match") for x in rows),
              "rows_total": len(rows),
              "rows_match": sum(1 for x in rows if x.get("match")),
              "rows_absent": sum(1 for x in rows if x.get("live") == "ABSENT"),
              "rows_drift": [x["path"] for x in rows if not x.get("match")]}

    # E: closure fields
    rv = doc.get("reviewer") or {}
    r["E"] = {"state": doc.get("state"),
              "reviewer_verdict": rv.get("verdict"), "independent": rv.get("independent"),
              "reviewer_id": rv.get("reviewer_id"),
              "top_reviewer_verdict": doc.get("reviewer_verdict"),
              "valid_existing_closure": (doc.get("state") == "SUCCESS" and rv.get("verdict") == "PASS"
                                         and rv.get("independent") is True and bool(rv.get("reviewer_id")))}

    results[uid] = r

out = {"role": "INDEPENDENT REVIEWER wave 3 shard 12 battery", "repo": str(REPO),
       "units": UNITS, "controls": controls, "results": results}
dest = REPO/"_reviewer-w3-shard12/verify_battery.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
for uid, r in results.items():
    A = r.get("A", {}); B = r.get("B", {}); C = r.get("C", {}); D = r.get("D", {}); E = r.get("E", {})
    print("%s: A=%s/blocked=%s/sent=%s B:errs=%s prof_miss=%s adm=%s C:exit0=%s (%s probes) D:recv_row=%s rows=%s/%s drift=%s E:closure=%s" % (
        uid, A.get("artifact"), A.get("self_blocked"), A.get("sentinel_present"),
        B.get("resolver_errors"), B.get("profile_missing"), str(B.get("admission"))[:24],
        C.get("all_exit0"), len(C.get("probes") or []),
        D.get("receipt_row_match"), D.get("rows_match"), D.get("rows_total"), len(D.get("rows_drift") or []),
        E.get("valid_existing_closure")))
print("controls:", json.dumps(controls))

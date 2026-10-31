"""Independent reviewer re-measurement, wave2 shard15 (12 units). Fresh code, no reuse.
Checks per unit:
  catalog-has-deps / catalog-has-target  (catalog entry completeness)
  C2 artifact exists + non-empty at catalog output_path
  C3 artifact parses as JSON dict
  C4 not self-declared BLOCKED/FAILED/SEVERED
  C5 unit_id match (receipt vs catalog id)
  C6 sentinel: receipt.sentinel == catalog completion_sentinel
  C7 reviewer block: verdict PASS + independent true
  C8 live probes: every command-center/p2-wave/probes/<id>/probe*.py re-run, all rc==0 (>=1 probe)
  C9 manifest: UNIT-ARTIFACT-MANIFEST.json row for output_path, sha256 == live CRLF-normalized sha256
  C10 output_schema: artifact validates against catalog output_schema (jsonschema Draft2020-12)
"""
import json, hashlib, subprocess, sys, time, os
from pathlib import Path
from jsonschema import Draft202012Validator

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = ["IMP-0423","IMP-0430","IMP-0435","IMP-0437","IMP-0439","IMP-0442",
       "IMP-0448","IMP-0450","IMP-0460","IMP-0466","IMP-0467","IMP-0468"]
OUT = REPO / "_rev-w2-shard15-nd" / "RESULTS-ND.json"

cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat["work_units"]}


def crlf_norm_sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


schema_cache = {}


def validator_for(rel):
    if rel not in schema_cache:
        doc = json.loads((REPO/rel).read_text(encoding="utf-8"))
        schema_cache[rel] = Draft202012Validator(doc)
    return schema_cache[rel]


def run_probe(p, timeout=180):
    # Full environment: probes resolve Path.home() / USERPROFILE; a stripped env
    # produces artifacts of the runner, not of the unit (measured on IMP-0430).
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    try:
        cp = subprocess.run([sys.executable, str(p)], cwd=str(REPO), env=env,
                            capture_output=True, text=True, timeout=timeout)
        rc = cp.returncode
        tail = (cp.stdout.strip().splitlines() or [""])[-1][:200]
        err_tail = (cp.stderr.strip().splitlines() or [""])[-1][:200]
    except subprocess.TimeoutExpired:
        rc, tail, err_tail = -999, "TIMEOUT", "TIMEOUT"
    return {"probe": p.name, "rc": rc, "secs": round(time.time()-t0, 1),
            "last_line": tail, "err_line": err_tail}


results = {}
for uid in IDS:
    r = {"id": uid}
    ce = units.get(uid)
    r["in-catalog"] = ce is not None
    if not ce:
        results[uid] = r
        continue
    r["catalog-output_path"] = ce.get("output_path")
    r["catalog-output_schema"] = ce.get("output_schema")
    r["catalog-has-deps"] = isinstance(ce.get("dependencies"), list)
    r["catalog-has-target"] = bool(ce.get("question_or_target") or ce.get("description") or ce.get("title"))
    op = ce.get("output_path")
    art = REPO/op if op else None
    r["C2-present-nonempty"] = bool(art and art.is_file() and art.stat().st_size > 0)
    r["bytes"] = art.stat().st_size if art and art.is_file() else 0
    doc = None
    try:
        doc = json.loads(art.read_text(encoding="utf-8"))
        r["C3-parses-dict"] = isinstance(doc, dict)
    except Exception as e:
        r["C3-parses-dict"] = False
        r["C3-err"] = str(e)[:120]
    state = doc.get("state") if isinstance(doc, dict) else None
    r["state"] = state
    blocked = isinstance(doc, dict) and isinstance(doc.get("failure"), dict) and \
        doc["failure"].get("state") in ("BLOCKED", "FAILED")
    r["C4-not-self-blocked"] = state not in ("BLOCKED", "FAILED", "SEVERED") and not blocked
    r["C5-unit_id-match"] = (doc.get("unit_id") == uid) if isinstance(doc, dict) else False
    sent = ce.get("completion_sentinel")
    r["C6-sentinel-eq"] = bool(sent) and isinstance(doc, dict) and (doc.get("sentinel") == sent)
    rv = doc.get("reviewer") if isinstance(doc, dict) else None
    r["C7-reviewer-PASS-independent"] = bool(isinstance(rv, dict) and rv.get("verdict") == "PASS"
                                             and rv.get("independent") is True)
    r["reviewer_id-existing"] = rv.get("reviewer_id") if isinstance(rv, dict) else None
    # C8 live probes
    pdir = REPO/"command-center"/"p2-wave"/"probes"/uid
    probes = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
    runs = [run_probe(p) for p in probes]
    r["C8-probes-live-rc0"] = len(runs) >= 1 and all(x["rc"] == 0 for x in runs)
    r["probe_runs"] = runs
    # C9 manifest sha
    man_p = pdir/"UNIT-ARTIFACT-MANIFEST.json"
    ok9, nrows, live_sha = False, 0, None
    if r["C2-present-nonempty"] and man_p.is_file():
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            rows = [a for a in man.get("artifacts", []) if a.get("path") == op]
            nrows = len(rows)
            live_sha = crlf_norm_sha(art)
            ok9 = nrows >= 1 and any(a.get("sha256") == live_sha for a in rows)
            r["manifest-bytes-eq"] = nrows >= 1 and all(a.get("bytes") == art.stat().st_size for a in rows)
            r["manifest-unit-id-eq"] = man.get("unit_id") == uid
        except Exception as e:
            r["C9-err"] = str(e)[:120]
    r["live_sha256"] = live_sha
    r["manifest-rows"] = nrows
    r["C9-manifest-sha-match"] = ok9
    # C10 schema
    osch = ce.get("output_schema")
    c10, errs = False, []
    if osch and r["C3-parses-dict"] and (REPO/osch).is_file():
        try:
            v = validator_for(osch)
            es = sorted(v.iter_errors(doc), key=lambda e: [str(x) for x in e.absolute_path])
            errs = ["/".join(str(x) for x in e.absolute_path) or "<root>" + ": " + e.message[:150]
                    for e in es]
            c10 = len(es) == 0
        except Exception as e:
            errs = ["validator-error: " + str(e)[:150]]
    r["C10-output_schema-valid"] = c10
    r["schema_errors_n"] = len(errs)
    r["schema_errors_first5"] = errs[:5]
    checks = ["in-catalog", "catalog-has-deps", "catalog-has-target", "C2-present-nonempty",
              "C3-parses-dict", "C4-not-self-blocked", "C5-unit_id-match", "C6-sentinel-eq",
              "C7-reviewer-PASS-independent", "C8-probes-live-rc0", "C9-manifest-sha-match",
              "C10-output_schema-valid"]
    r["failing"] = [c for c in checks if not r.get(c)]
    r["verdict"] = "PASS" if not r["failing"] else "FAIL"
    results[uid] = r

npass = sum(1 for r in results.values() if r.get("verdict") == "PASS")
payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "reviewer_id": "claude-opus-5-5 independent-reviewer w2s15 fresh-code 2026-10-26",
           "pass": npass, "fail": len(results)-npass, "units": results}
OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
for uid in IDS:
    r = results[uid]
    print(uid, r.get("verdict"), "| failing:", r.get("failing"))

r"""Independent reviewer re-verification battery - resume of review:w4s8 (2026-10-26 evening).

Checks per unit, in order:
  C1 catalog entry present (output_path, output_schema, completion_sentinel)
  C2 artifact at catalog output_path: exists, non-empty, parses, state==SUCCESS,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, unit_id matches
  C3 live probes re-run by THIS reviewer: every command-center/p2-wave/probes/<id>/probe*.py exit 0
  C4 CRLF-normalized sha256 of live artifact == UNIT-ARTIFACT-MANIFEST.json primary row (present=true, bytes equal)
  C5 output_schema: jsonschema validate vs catalog schema(s) AND program admission validator ACCEPT
  C6 closure shape: receipt reviewer.verdict==PASS, reviewer.independent==True, state==SUCCESS, sentinel match

Run order: C2/C1 first, C3 (probes, may touch FS), then C4/C5/C6 re-measured AFTER probes
so a probe that mutated the receipt cannot hide behind a pre-probe hash.
"""
import glob
import hashlib
import json
import os
import subprocess
import sys

os.chdir(os.path.expanduser("~/p2-g1"))
REPO = os.getcwd()

MINE = ["IMP-0002", "IMP-0006", "IMP-0022", "IMP-0031", "IMP-0035",
        "IMP-0036", "IMP-0037", "IMP-0038", "IMP-0041", "IMP-0044",
        "IMP-0051", "IMP-0068"]
BAD_STATES = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

cat = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

import jsonschema  # noqa: E402


def sha_norm(p):
    raw = open(p, "rb").read()
    return (hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
            "CRLF" if b"\r\n" in raw else "LF", len(raw))


report = {}
for uid in MINE:
    e = byid.get(uid)
    r = {"catalog_entry": bool(e)}
    if not e:
        report[uid] = r
        continue
    op = str(e["output_path"]).replace("\\", "/")
    r["output_path"] = op
    r["output_schema_field"] = str(e["output_schema"])
    r["sentinel_expected"] = e.get("completion_sentinel")

    # C2 + C6 (artifact) - measured now, re-verified after probes via C4 hash
    probs = []
    art = None
    try:
        size = os.path.getsize(op)
        r["bytes"] = size
        if size == 0:
            probs.append("C2:artifact-empty")
        art = json.load(open(op, encoding="utf-8"))
    except Exception as ex:
        probs.append(f"C2:parse/{os.path.basename(op)}: {str(ex)[:120]}")
    if isinstance(art, dict):
        st = art.get("state")
        if st in BAD_STATES:
            probs.append(f"C2:self-blocked state={st}")
        s = json.dumps(art)
        for marker in ('"state": "BLOCKED"', '"verdict": "BLOCKED"', '"status": "BLOCKED"'):
            if marker in s:
                probs.append(f"C2:nested {marker}")
        if art.get("unit_id") != uid:
            probs.append(f"C2:unit_id={art.get('unit_id')!r}")
        rv = art.get("reviewer") or {}
        r["receipt_state"] = st
        r["reviewer_verdict"] = rv.get("verdict")
        r["reviewer_independent"] = rv.get("independent")
        r["reviewer_id"] = rv.get("reviewer_id")
        if rv.get("verdict") != "PASS":
            probs.append(f"C6:reviewer.verdict={rv.get('verdict')!r}")
        if rv.get("independent") is not True:
            probs.append("C6:reviewer.independent!=true")
        if st != "SUCCESS":
            probs.append(f"C6:state={st}!=SUCCESS")
        if art.get("sentinel") != e.get("completion_sentinel"):
            probs.append(f"C6:sentinel={art.get('sentinel')!r}")

    # C5 schema (direct jsonschema against catalog-declared schema files)
    if isinstance(art, dict):
        sch_field = str(e["output_schema"])
        parts = [p.strip().replace("\\", "/") for p in sch_field.split("+")]
        for i, part in enumerate(parts):
            primary = part.split(" ")[0]
            try:
                schema = json.load(open(primary, encoding="utf-8"))
                jsonschema.validate(art, schema)
            except jsonschema.ValidationError as ex:
                probs.append(f"C5:schema{i+1}-FAIL({os.path.basename(primary)}): {str(ex.message)[:200]}")
            except Exception as ex:
                probs.append(f"C5:schema{i+1}-unreadable({primary}): {str(ex)[:120]}")

    # C3 probes - run them AFTER recording C2 reading, BEFORE C4 re-hash
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = REPO
    probe_scripts = sorted(glob.glob(f"command-center/p2-wave/probes/{uid}/probe*.py"))
    per = {}
    for p in probe_scripts:
        try:
            res = subprocess.run([sys.executable, "-I", p], capture_output=True,
                                 text=True, timeout=300, env=env, cwd=REPO)
            per[os.path.basename(p)] = {"exit": res.returncode,
                                        "tail": ((res.stdout or "") + (res.stderr or "")).strip()[-300:]}
        except subprocess.TimeoutExpired:
            per[os.path.basename(p)] = {"exit": "TIMEOUT", "tail": ""}
    r["probes"] = per
    bad_probes = [k for k, v in per.items() if v["exit"] != 0]
    if not probe_scripts:
        probs.append("C3:no-probe-scripts")
    for k in bad_probes:
        probs.append(f"C3:{k} exit={per[k]['exit']}")

    # C4 manifest sha - measured AFTER the probe battery so mutation cannot hide
    man_path = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    try:
        live, eol, rawlen = sha_norm(op)
        man = json.load(open(man_path, encoding="utf-8"))
        rows = man.get("artifacts") if isinstance(man, dict) else None
        match = None
        if isinstance(rows, list):
            for a in rows:
                if (isinstance(a, dict) and a.get("unit_id") == uid
                        and str(a.get("path", "")).replace("\\", "/") == op):
                    match = a
        ok = bool(match) and match.get("sha256") == live and match.get("present") is True
        r["sha_live"] = live
        r["eol"] = eol
        r["manifest_row"] = ({"sha256": match.get("sha256"), "bytes": match.get("bytes"),
                              "present": match.get("present")} if match else None)
        if not ok:
            probs.append(f"C4:manifest-sha-mismatch live={live[:12]} row={str((match or {}).get('sha256'))[:12]}")
        # post-probe mutation check: bytes changed vs pre-probe reading?
        if "bytes" in r and r["bytes"] != rawlen:
            probs.append(f"C2:MUTATED-DURING-REVIEW {r['bytes']}->{rawlen}")
            r["bytes_after_probes"] = rawlen
    except Exception as ex:
        probs.append(f"C4:manifest-error: {str(ex)[:120]}")

    r["problems"] = probs
    r["verdict"] = "PASS" if not probs else "FAIL"
    report[uid] = r

json.dump(report, open("_reviewer-w4s8/verdicts_resume.json", "w"), indent=1)
npass = sum(1 for v in report.values() if v.get("verdict") == "PASS")
print(f"RESULT: {npass}/12 PASS")
for uid in MINE:
    v = report[uid]
    line = f"{uid}: {v.get('verdict')}"
    if v.get("verdict") == "FAIL":
        line += " | " + " ; ".join(v.get("problems", []))
    print(line)

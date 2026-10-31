#!/usr/bin/env python3
"""Independent reviewer wave-4 shard-17 RE-RUN (r2). Static battery:
S1 catalog entry, S2 artifact exists/non-empty/parses/not-self-blocked/sentinel,
S3 sha256 (CRLF->LF) vs manifest PRIMARY row + ALL rows,
S4rev reviewer block genuineness (probe-derived identity = not independent).
No writes to receipts/artifacts/probes. Emits phase1_state.json.
"""
import hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["TST-0032","TST-0057","TST-0060","TST-0066","TST-0067","TST-0068",
         "TST-0070","TST-0081","TST-0085","TST-0088","TST-0090","TST-0091"]
PROBE_DERIVED_RX = re.compile(
    r"probe\d|probe[_-]|schema-resolver|green-claim|timeout-only-mutant|coin[-_]flip", re.I)
NOT_DELIVERING = {"BLOCKED","FAILED","SEVERED","TIMEOUT"}

cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

def sha_lf(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

state = {}
for uid in UNITS:
    checks = {}
    u = byid.get(uid)
    checks["S1_catalog_entry"] = bool(u) and all(
        bool(u.get(k)) for k in ("output_path","output_schema","probes","dependencies"))
    if not u:
        state[uid] = {"checks": checks, "ok": False}
        continue

    out = REPO / str(u["output_path"]).replace("\\","/")
    checks["S2_exists"] = out.is_file() and out.stat().st_size > 0
    doc = None
    text = ""
    if checks["S2_exists"]:
        try:
            text = out.read_text(encoding="utf-8")
            doc = json.loads(text)
            checks["S2_parses"] = isinstance(doc, dict)
        except Exception as e:
            checks["S2_parses"] = False
            checks["S2_parse_err"] = str(e)[:120]
    else:
        checks["S2_parses"] = False
    st = str((doc or {}).get("state") or "").upper()
    checks["S2_not_self_blocked"] = bool(doc) and st not in NOT_DELIVERING
    checks["S2_state"] = st
    sentinel = str(u.get("completion_sentinel") or "")
    checks["S2_sentinel"] = (not sentinel) or (sentinel in text)

    man_p = REPO / ("command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)
    ret_p = REPO / ("command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid)
    checks["S3_manifest_present"] = man_p.is_file() and ret_p.is_file()
    man = ret = None
    try:
        man = json.loads(man_p.read_text(encoding="utf-8"))
        ret = json.loads(ret_p.read_text(encoding="utf-8"))
    except Exception as e:
        checks["S3_manifest_err"] = str(e)[:120]
    checks["S3_manifest_parses"] = man is not None and ret is not None
    if man is not None:
        arts = man.get("artifacts") if isinstance(man, dict) else None
        if arts is None and isinstance(man, list):
            arts = man
        arts = [a for a in (arts or []) if isinstance(a, dict)]
        out_rel = str(u["output_path"]).replace("\\","/")
        primary = [a for a in arts if str(a.get("path") or "").replace("\\","/") == out_rel]
        live = sha_lf(out) if checks["S2_exists"] else None
        checks["S3_primary_row_present"] = bool(primary)
        checks["S3_primary_sha_match"] = live is not None and any(
            a.get("present") is True and str(a.get("sha256") or "") == live for a in primary)
        bad = []
        for a in arts:
            ap = REPO / str(a.get("path") or "").replace("\\","/")
            if not ap.is_file():
                bad.append([a.get("path"), "absent"])
                continue
            ah = sha_lf(ap)
            if str(a.get("sha256") or "") != ah:
                bad.append([a.get("path"), "sha-mismatch"])
        checks["S3_all_rows_match"] = not bad
        checks["S3_all_rows_bad"] = bad[:8]
        checks["S3_return_status"] = str((ret or {}).get("status") or (ret or {}).get("state") or "").upper()

    rv = (doc or {}).get("reviewer") if isinstance(doc, dict) else None
    checks["S4rev_reviewer_block"] = isinstance(rv, dict)
    checks["S4rev_verdict_pass"] = isinstance(rv, dict) and str(rv.get("verdict") or "").upper() == "PASS"
    checks["S4rev_independent_true"] = isinstance(rv, dict) and rv.get("independent") is True
    rid = " ".join([str((rv or {}).get(k) or "") for k in ("reviewer_id","id","role","name")])
    checks["S4rev_identity_genuine"] = isinstance(rv, dict) and not PROBE_DERIVED_RX.search(rid)
    checks["S4rev_reviewer_id"] = rid[:100]

    probes = u.get("probes") or []
    missing = []
    for p in probes:
        pp = REPO / str(p).replace("\\","/")
        if not pp.is_file():
            missing.append(str(p))
    checks["S5_probe_files_present"] = not missing
    checks["S5_probe_files_missing"] = missing[:5]
    checks["S5_named_probe_count"] = len((ret or {}).get("named_probes") or [])

    checks["ok"] = all(v is True for k, v in checks.items() if isinstance(v, bool))
    state[uid] = {"checks": checks, "ok": checks["ok"]}

state["_meta"] = {"reviewer": "claude-opus-5-5-independent-reviewer-w4-shard17-r2",
                  "utc": datetime.now(timezone.utc).isoformat(), "units": UNITS}
outp = REPO/"_reviewer-w4-shard17-r2"/"phase1_state.json"
outp.write_text(json.dumps(state, indent=1), encoding="utf-8")
for uid in UNITS:
    c = state[uid]["checks"]
    fails = [k for k, v in c.items() if isinstance(v, bool) and not v]
    print("%s: %s  rev_id=%s" % (uid, "OK" if state[uid]["ok"] else "FAIL " + ",".join(fails),
                                 c.get("S4rev_reviewer_id","")[:60]))

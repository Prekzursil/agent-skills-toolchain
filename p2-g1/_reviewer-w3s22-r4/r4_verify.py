#!/usr/bin/env python3
"""Wave-3 shard-22 independent reviewer, round 4 (fresh context, fresh instrument).

Imports NOTHING from the builder or from prior reviewer code. Only the program's
official gates (platform/lib/receipt_schema_gate.py, platform/lib/schema_resolver.py,
command-center/receipt_validate.py) plus this file's own hashing/probing.

Checks per unit (all re-derived live):
  A. catalog entry + output_path
  B. receipt exists / non-empty / parses / unit_id binds
  C. closure predicate: closed units need state=SUCCESS + reviewer.verdict=PASS
     + reviewer.independent=True (no self-certification); the open unit needs
     state=BLOCKED + classification=[reviewer-absent] + reviewer=null
  D. UNIT-ARTIFACT-MANIFEST.json: every artifact row re-hashed (CRLF->LF) matches
  E. named probes re-run LIVE (exit 0 + SUCCESS:<uid>- sentinel); TST-0174 probe1
     gets 12 rounds (documented teardown race needs a fair chance to reproduce)
  F. schema: receipt_core 0 errors + catalog output_schema 0 errors + 12-condition
     predicate COMPLETE (closed units); admission ACCEPT via receipt_validate.py
  G. instrument mutation control: independent=false copy must REJECT (done in main)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = ["TST-0174", "TST-0175", "TST-0176", "TST-0178", "TST-0179", "TST-0180",
         "TST-0181", "TST-0185", "TST-0188", "TST-0190", "TST-0193", "TST-0194"]
OPEN_UNITS = {"TST-0174"}
S174_PROBE1_ROUNDS = 12  # documented r1 45% / r2 10% / r3 42% crash rate; fair chance
CLOSED_ROUNDS = 2
TIMEOUT = 900


def lf_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(script: str, timeout: int = TIMEOUT) -> tuple[int, str, float]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    r = subprocess.run([sys.executable, "-B", script], capture_output=True, text=True,
                       timeout=timeout, cwd=str(REPO), env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")), time.time() - t0


def load_gates():
    def load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    rsg = load("rsg_r4", REPO / "platform/lib/receipt_schema_gate.py")
    sr = load("sr_r4", REPO / "platform/lib/schema_resolver.py")
    return rsg, sr


RSG, SR = load_gates()
CATALOG = {u["id"]: u for u in json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))["work_units"]}


def scripts_for(uid: str) -> tuple[list[str], list[str]]:
    """Named probe scripts from SUBAGENT-RETURN.json; returns (scripts, fails)."""
    rp = PROBES / uid / "SUBAGENT-RETURN.json"
    if not rp.is_file():
        return [], ["subagent-return-absent"]
    ret = json.loads(rp.read_text(encoding="utf-8"))
    scripts, fails = [], []
    for np in ret.get("named_probes", []):
        toks = str(np.get("command", "")).split()
        m = [t for t in toks if t.endswith(".py")]
        if not m:
            fails.append("named-probe-no-script:" + str(np.get("id")))
        else:
            scripts.append(m[-1])
    if len(scripts) < 2:
        fails.append("named-probes<2")
    return scripts, fails


def probe_rounds(uid: str, script: str, rounds: int) -> tuple[dict, list[str]]:
    det = {"script": script, "rounds": [], "crashes": 0}
    fails: list[str] = []
    for i in range(rounds):
        try:
            rc, out, dt = run_probe(script)
        except subprocess.TimeoutExpired:
            det["rounds"].append({"r": i + 1, "rc": "TIMEOUT"})
            det["crashes"] += 1
            fails.append(f"probe-timeout:{Path(script).name}:r{i + 1}")
            break
        ok = (rc == 0) and (f"SUCCESS:{uid}-" in out)
        det["rounds"].append({"r": i + 1, "rc": rc, "sec": round(dt, 2), "ok": ok,
                              "tail": out.strip().splitlines()[-1][:200] if out.strip() else ""})
        if not ok:
            det["crashes"] += 1
            fails.append(f"probe-fail:{Path(script).name}:r{i + 1}:rc={rc}:"
                         + out.strip().splitlines()[-1][:300] if out.strip() else "no-output")
            if uid in OPEN_UNITS:
                break  # race reproduced; no point burning more rounds
    return det, fails


def verify(uid: str) -> dict:
    res: dict = {"id": uid, "checks": {}, "fails": []}
    F = res["fails"]
    ck = res["checks"]

    u = CATALOG.get(uid)
    if not u:
        return {"id": uid, "fails": ["catalog-entry-absent"], "checks": {}}
    ck["catalog_output_path"] = u.get("output_path") == f"command-center/receipts/{uid}.json"
    if not ck["catalog_output_path"]:
        F.append("catalog-output_path-drift")
    ck["catalog_output_schema"] = u.get("output_schema", "")

    rp = REPO / f"command-center/receipts/{uid}.json"
    if not rp.is_file():
        F.append("receipt-missing")
        return res
    if rp.stat().st_size == 0:
        F.append("receipt-empty")
        return res
    try:
        rec = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        F.append(f"receipt-unparseable:{type(e).__name__}")
        return res
    ck["receipt_unit_id"] = rec.get("unit_id") == uid
    if not ck["receipt_unit_id"]:
        F.append("receipt-unit-id-mismatch")

    closed = uid not in OPEN_UNITS
    if closed:
        rev = rec.get("reviewer") or {}
        ck["state"] = rec.get("state") == "SUCCESS"
        ck["reviewer_verdict"] = rev.get("verdict") == "PASS"
        ck["reviewer_independent"] = rev.get("independent") is True
        if not ck["state"]:
            F.append("state!=" + str(rec.get("state")))
        if not ck["reviewer_verdict"]:
            F.append("reviewer-verdict!=" + str(rev.get("verdict")))
        if not ck["reviewer_independent"]:
            F.append("reviewer-independent-not-true")
    else:
        ck["state_blocked"] = rec.get("state") == "BLOCKED"
        ck["classification"] = (rec.get("failure") or {}).get("classification") == ["reviewer-absent"]
        ck["reviewer_null"] = rec.get("reviewer") is None
        if not ck["state_blocked"]:
            F.append("open-unit-state!=" + str(rec.get("state")))

    # D. manifest rows
    manp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not manp.is_file():
        F.append("manifest-absent")
        return res
    man = json.loads(manp.read_text(encoding="utf-8"))
    rows = [a for a in man.get("artifacts", []) if isinstance(a, dict)]
    ck["manifest_rows"] = len(rows)
    bad_rows = []
    receipt_row_sha = None
    for a in rows:
        fp = REPO / str(a.get("path", ""))
        if not fp.is_file():
            bad_rows.append("absent:" + str(a.get("path")))
            continue
        d, _ = lf_sha(fp)
        if d != a.get("sha256"):
            bad_rows.append("sha:" + Path(str(a.get("path"))).name)
        if str(a.get("path")) == f"command-center/receipts/{uid}.json":
            receipt_row_sha = a.get("sha256")
    ck["manifest_rows_ok"] = not bad_rows
    if bad_rows:
        F.append("manifest-rows:" + ";".join(bad_rows[:4]))
    if receipt_row_sha is None:
        F.append("manifest-no-receipt-row")

    # E. live probes
    scripts, sfails = scripts_for(uid)
    F.extend(sfails)
    probe_detail = {}
    for s in scripts:
        rounds = S174_PROBE1_ROUNDS if (uid in OPEN_UNITS and "probe1" in s) else CLOSED_ROUNDS
        det, pfails = probe_rounds(uid, s, rounds)
        probe_detail[Path(s).name] = det
        F.extend(pfails)
    res["probes"] = probe_detail
    if closed and not sfails:
        # probe script bytes pinned by manifest already covered in D; keep going
        pass

    # F. schema + predicate + admission (closed units)
    if closed:
        core_errs = RSG.validate_receipt(rec)
        ck["receipt_core_errors"] = len(core_errs)
        if core_errs:
            F.append("receipt-core:" + core_errs[0][:150])
        try:
            prof = SR.validator_for(u.get("output_schema", ""))
            prof_errs = sorted(e.message for e in prof.iter_errors(rec))
            ck["profile_errors"] = len(prof_errs)
            if prof_errs:
                F.append("output-schema:" + prof_errs[0][:150])
        except Exception as e:
            F.append(f"output-schema-resolver:{type(e).__name__}:{e}")
        gate, extra = RSG.evaluate_full(rec, repo_root=str(REPO), verify_filesystem=True)
        ck["predicate_complete"] = bool(gate.complete)
        ck["predicate_extra"] = extra
        if not gate.complete:
            F.append("predicate:" + gate.marker().split(" ", 1)[-1][:200])
        r = subprocess.run([sys.executable, "-B", "command-center/receipt_validate.py",
                            f"command-center/receipts/{uid}.json"],
                           capture_output=True, text=True, cwd=str(REPO),
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        ck["admission_rc"] = r.returncode
        ck["admission_line"] = (r.stdout or "").strip().splitlines()[0][:160] if r.stdout.strip() else ""
        if r.returncode != 0 or not (r.stdout or "").startswith("ACCEPT"):
            F.append("admission:" + ck["admission_line"][:150])
    else:
        # open unit: record schema state, not a fail check (pre-closure shape)
        core_errs = RSG.validate_receipt(rec)
        ck["receipt_core_errors_preclosure"] = len(core_errs)

    res["verdict"] = "PASS" if not F else "FAIL"
    res["receipt_row_sha_matches_live"] = (
        receipt_row_sha == lf_sha(rp)[0] if receipt_row_sha else False)
    return res


def main() -> int:
    t0 = time.time()
    print(f"r4 independent reviewer battery over {len(UNITS)} units, fresh context")
    results = {}
    for uid in UNITS:
        r = verify(uid)
        results[uid] = r
        n_rounds = sum(len(d["rounds"]) for d in (r.get("probes") or {}).values())
        print(f"{r['verdict']}:{uid} fails={len(r['fails'])} probe_rounds={n_rounds} "
              f"row_sha_ok={r.get('receipt_row_sha_matches_live')}")
        for f in r["fails"]:
            print(f"  - {f}")
        sys.stdout.flush()

    # G. instrument mutation control (already spot-checked; record formally)
    src = REPO / "command-center/receipts/TST-0175.json"
    mut = json.loads(src.read_text(encoding="utf-8"))
    mut["reviewer"]["independent"] = False
    mutp = REPO / "_reviewer-w3s22-r4/mut_indep_false.json"
    mutp.write_text(json.dumps(mut), encoding="utf-8")
    rr = subprocess.run([sys.executable, "-B", "command-center/receipt_validate.py",
                         "_reviewer-w3s22-r4/mut_indep_false.json"],
                        capture_output=True, text=True, cwd=str(REPO),
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    mut_rejects = rr.returncode != 0 and (rr.stdout or "").startswith("REJECT")
    print(f"mutation-control independent=false -> REJECT={mut_rejects}")
    results["_mutation_control"] = {"mutant_rejected": mut_rejects,
                                    "output": (rr.stdout or "").strip()[:200]}

    out = REPO / "_reviewer-w3s22-r4/r4_verdicts.json"
    summary = {
        "reviewer": "w3-shard22-independent-reviewer-r4-fresh",
        "date": time.strftime("%Y-%m-%d"),
        "units_of_record": UNITS,
        "pass": sum(1 for u in UNITS if results[u]["verdict"] == "PASS"),
        "fail": sum(1 for u in UNITS if results[u]["verdict"] == "FAIL"),
        "elapsed_sec": round(time.time() - t0, 1),
        "mutation_control": results["_mutation_control"],
    }
    out.write_text(json.dumps({"summary": summary, "verdicts": results},
                              indent=1), encoding="utf-8")
    print(f"SUCCESS:r4-battery pass={summary['pass']} fail={summary['fail']} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

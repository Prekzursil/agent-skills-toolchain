#!/usr/bin/env python3
"""Round-3 fresh re-verification instrument, wave-3 shard-22 independent reviewer.

Written fresh this round (2026-10-26). Imports only the program's own gates
(platform/lib/receipt_schema_gate, command-center/p2-wave/_p2lib). Never
imports builder scripts or prior reviewer code: every check is re-derived from
the unit contract (catalog output_path/output_schema/probes; DELIVERED =
artifact exists/non-empty/parses/not-self-blocked, live probes exit 0,
manifest sha256 row matches live artifact CRLF->LF, output_schema valid).

Modes:
  closed [UID...]  re-verify closed units (stays-SUCCESS confirmation battery)
  s174 [N]         TST-0174: N-round probe1 characterization + static battery
  census           program-wide receipt-state census over all 2007 catalog units
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = REPO / "command-center" / "p2-wave" / "probes"
OUTDIR = REPO / "_reviewer-w3s22"
UNITS = ["TST-0174", "TST-0175", "TST-0176", "TST-0178", "TST-0179", "TST-0180",
         "TST-0181", "TST-0185", "TST-0188", "TST-0190", "TST-0193", "TST-0194"]
CLOSED = UNITS[1:]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def sha_lf_bytes(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def load_gate():
    spec = importlib.util.spec_from_file_location(
        "rsg", REPO / "platform" / "lib" / "receipt_schema_gate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rsg"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_p2lib():
    spec = importlib.util.spec_from_file_location(
        "p2l", REPO / "command-center" / "p2-wave" / "_p2lib.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["p2l"] = mod
    spec.loader.exec_module(mod)
    return mod


RSG = load_gate()
P2L = load_p2lib()


def catalog() -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def run_script(rel: str, timeout: int = 900) -> tuple[int, str]:
    """Run a probe script live under the ambient interpreter, cwd=REPO."""
    try:
        p = subprocess.run([sys.executable, "-B", rel], cwd=str(REPO),
                           capture_output=True, text=True, timeout=timeout,
                           errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, "SPAWN-ERR " + type(e).__name__ + ": " + str(e)


def named_probe_scripts(uid: str) -> list[str]:
    ret = json.loads((PROBES / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    scripts = []
    for np in ret.get("named_probes", []):
        m = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
        if m:
            scripts.append(m[-1])
    return scripts


def manifest_rows_ok(uid: str, receipt_path: Path) -> tuple[bool, list[str]]:
    fails = []
    manp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not manp.is_file():
        return False, ["manifest-missing"]
    man = json.loads(manp.read_text(encoding="utf-8"))
    rows = man.get("artifacts", [])
    if not rows:
        return False, ["manifest-no-rows"]
    for a in rows:
        rp = REPO / str(a.get("path", ""))
        if not rp.is_file():
            fails.append("row-absent:" + str(a.get("path")))
            continue
        live = sha_lf_bytes(rp.read_bytes())
        if live != a.get("sha256"):
            fails.append("row-sha-mismatch:" + rp.name)
    prow = [a for a in rows if a.get("path", "").replace("\\", "/") ==
            f"command-center/receipts/{uid}.json"]
    if not prow:
        fails.append("no-receipt-row")
    else:
        live = sha_lf_bytes(receipt_path.read_bytes())
        if prow[0].get("sha256") != live:
            fails.append("receipt-row-sha-mismatch")
    return (not fails), fails


def validator_rc(uid: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center" / "receipt_validate.py"),
         str(REPO / f"command-center/receipts/{uid}.json")],
        capture_output=True, text=True, timeout=600, cwd=str(REPO))
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def verify_closed(uid: str, u: dict, rounds: int = 2) -> dict:
    R = {"id": uid, "holds": []}
    rp = REPO / f"command-center/receipts/{uid}.json"
    if not rp.is_file():
        R["holds"].append("receipt-missing")
        return R
    raw = rp.read_bytes()
    if not raw.strip():
        R["holds"].append("receipt-empty")
        return R
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as e:
        R["holds"].append("receipt-unparsable:" + type(e).__name__)
        return R
    if doc.get("unit_id") != uid:
        R["holds"].append("unit-id")
    if str(doc.get("output_path") or "") != str(u.get("output_path")):
        R["holds"].append("output-path!=catalog")
    # closed-unit invariants
    if doc.get("state") != "SUCCESS":
        R["holds"].append("state=" + str(doc.get("state")))
    if doc.get("state") in NOT_DELIVERING:
        R["holds"].append("self-declared:" + str(doc.get("state")))
    rv = doc.get("reviewer") or {}
    if rv.get("verdict") != "PASS" or rv.get("independent") is not True:
        R["holds"].append("reviewer-invariant")
    if rv.get("reviewer_id") == (doc.get("produced_by") or {}).get("role"):
        R["holds"].append("reviewer==producer")
    if not str(doc.get("sentinel") or "").startswith("SUCCESS:"):
        R["holds"].append("sentinel:" + str(doc.get("sentinel"))[:60])
    # admission + gate + profile schema
    vrc, vout = validator_rc(uid)
    R["admission_rc"] = vrc
    if vrc != 0:
        R["holds"].append("admission-REJECT:" + vout[:160])
    g = RSG.evaluate_gate_a(doc, repo_root=str(REPO), verify_filesystem=True)
    R["gate_complete"] = g.complete
    if not g.complete:
        R["holds"].append("gate-incomplete:" + g.marker()[:120])
    try:
        perr = P2L.validate(doc, u.get("output_schema"))
        R["profile_schema_errors"] = perr[:5]
        if perr:
            R["holds"].append(f"profile-schema:{len(perr)}-errors:" + perr[0][:100])
    except Exception as e:
        R["holds"].append(f"profile-validate-raise:{type(e).__name__}:{str(e)[:100]}")
    # manifest integrity (all rows)
    man_ok, man_fails = manifest_rows_ok(uid, rp)
    R["manifest_ok"] = man_ok
    if not man_ok:
        R["holds"].extend(man_fails[:4])
    # live probes, N rounds each
    pr = []
    for s in named_probe_scripts(uid):
        rr = []
        for i in range(rounds):
            rc, out = run_script(s)
            rr.append(rc)
            if rc != 0:
                R["holds"].append(f"probe-fail:{Path(s).name}:r{i+1}:rc={rc}")
                break
            if f"SUCCESS:{uid}-" not in out:
                R["holds"].append(f"probe-no-sentinel:{Path(s).name}:r{i+1}")
                break
        pr.append({"script": Path(s).name, "rounds": rr})
    R["probes"] = pr
    R["verdict"] = "FAIL" if R["holds"] else "PASS"
    return R


def s174_battery(n_rounds: int) -> dict:
    uid = "TST-0174"
    u = catalog()[uid]
    R = {"id": uid, "rounds_requested": n_rounds}
    rp = REPO / f"command-center/receipts/{uid}.json"
    doc = json.loads(rp.read_text(encoding="utf-8"))
    R["builder_receipt"] = {
        "state": doc.get("state"),
        "classification": (doc.get("failure") or {}).get("classification"),
        "reviewer": doc.get("reviewer"),
        "unit_id": doc.get("unit_id"),
    }
    man_ok, man_fails = manifest_rows_ok(uid, rp)
    R["manifest_ok"] = man_ok
    R["manifest_fails"] = man_fails[:4]
    vrc, vout = validator_rc(uid)
    R["builder_admission_rc"] = vrc
    R["builder_admission_tail"] = vout[:220]
    # probe characterization: probe1 x N, probe2 x 3
    def char(s: str, n: int) -> dict:
        crashes, sent_ok, last_err = 0, 0, ""
        for i in range(n):
            rc, out = run_script(s)
            if rc != 0:
                crashes += 1
                lines = [ln for ln in out.strip().splitlines() if ln.strip()]
                last_err = lines[-1][:200] if lines else f"rc={rc} empty"
            elif f"SUCCESS:{uid}-" in out:
                sent_ok += 1
        return {"script": Path(s).name, "rounds": n, "crashes": crashes,
                "sentinel_ok": sent_ok, "last_error": last_err}
    R["probe1"] = char("command-center/p2-wave/probes/TST-0174/probe1_interleavings.py", n_rounds)
    R["probe2"] = char("command-center/p2-wave/probes/TST-0174/probe2_mutation_temps.py", 3)
    stable = (R["probe1"]["crashes"] == 0 and R["probe1"]["sentinel_ok"] == n_rounds
              and R["probe2"]["crashes"] == 0 and R["probe2"]["sentinel_ok"] == 3)
    R["probe_stability"] = "STABLE-GREEN" if stable else "UNSTABLE-FAIL"
    return R


def census() -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    ids = [u["id"] for u in cat["work_units"]]
    out = {"total_catalog_units": len(ids), "green": 0, "overclaimed": 0,
           "open": 0, "no_receipt": 0, "unparseable": 0, "terminal": 0,
           "terminal_ids_by_state": {}, "green_by_prefix": {}, "open_by_prefix": {}}
    for uid in ids:
        rp = REPO / "command-center" / "receipts" / f"{uid}.json"
        if not rp.is_file():
            out["no_receipt"] += 1
            continue
        try:
            doc = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            out["unparseable"] += 1
            continue
        st = doc.get("state")
        if st in ("SUPERSEDED", "DROPPED-BY-OWNER", "DONE-VERIFIED"):
            out["terminal"] += 1
            out["terminal_ids_by_state"][st] = out["terminal_ids_by_state"].get(st, 0) + 1
            continue
        rv = doc.get("reviewer") or {}
        ok_close = (st == "SUCCESS" and rv.get("verdict") == "PASS"
                    and rv.get("independent") is True)
        pre = re.match(r"^[A-Z]+", uid).group(0) if re.match(r"^[A-Z]+", uid) else "?"
        if ok_close:
            out["green"] += 1
            out["green_by_prefix"][pre] = out["green_by_prefix"].get(pre, 0) + 1
        elif st == "SUCCESS":
            out["overclaimed"] += 1
        else:
            out["open"] += 1
            out["open_by_prefix"][pre] = out["open_by_prefix"].get(pre, 0) + 1
    out["green_plus_terminal"] = out["green"] + out["terminal"]
    return out


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "closed":
        targets = [a for a in sys.argv[2:] if a in CLOSED] or CLOSED
        CAT = catalog()
        results = {}
        for uid in targets:
            t0 = time.time()
            res = verify_closed(uid, CAT[uid])
            res["secs"] = round(time.time() - t0, 1)
            results[uid] = res
            line = f"{'SUCCESS' if res['verdict']=='PASS' else 'FAILED'}:closed {uid}"
            if res["holds"]:
                line += " holds=" + " | ".join(h[:90] for h in res["holds"][:4])
            print(line, flush=True)
        (OUTDIR / "r3_closed.json").write_text(
            json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
        nfail = sum(1 for r in results.values() if r["verdict"] == "FAIL")
        print(f"--- closed re-verify: {len(results)-nfail}/{len(results)} PASS, {nfail} FAIL")
        return 1 if nfail else 0
    if mode == "s174":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        res = s174_battery(n)
        (OUTDIR / "r3_s174.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({k: res[k] for k in ("probe1", "probe2", "probe_stability",
                                              "manifest_ok", "builder_admission_rc")}, indent=1))
        marker = "SUCCESS:s174-stable" if res["probe_stability"] == "STABLE-GREEN" else \
                 f"FAILED:s174-unstable crashes={res['probe1']['crashes']}/{n}"
        print(marker)
        return 0 if res["probe_stability"] == "STABLE-GREEN" else 1
    if mode == "census":
        res = census()
        (OUTDIR / "r3_census.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items()
                          if k not in ("green_by_prefix", "open_by_prefix",
                                       "terminal_ids_by_state")}, indent=1))
        print("green_by_prefix:", json.dumps(res["green_by_prefix"], sort_keys=True))
        print("open_by_prefix:", json.dumps(res["open_by_prefix"], sort_keys=True))
        return 0
    print("usage: r3_verify.py closed [UID...] | s174 [N] | census")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Wave-3 shard-22 INDEPENDENT REVIEWER, round 2 (fresh re-verification instrument).

Written by the assigned reviewer for w3s22; NOT derived from the builder and NOT a
re-run of close_shard22.py's code path. For each of the 12 assigned units it
re-derives every contract check LIVE:

  CAT    catalog entry present; output_path/output_schema match the contract
  ART    artifact at output_path: exists, non-empty, parses JSON, honest state
         (SUCCESS requires reviewer.verdict=PASS + independent=true; BLOCKED
         requires failure.classification=[reviewer-absent] + reviewer null)
  PROBE  every named probe re-run LIVE by this reviewer (3 rounds):
         rc==0 AND SUCCESS:<uid>- sentinel in output
  MAN    every UNIT-ARTIFACT-MANIFEST.json row: file exists, sha256 row
         matches CRLF-normalized-to-LF digest of the live bytes; receipt row
         matches the CURRENT receipt bytes
  SCHEMA receipt validates against catalog output_schema $defs fragment
  GATE   platform/lib/receipt_schema_gate.py 12-condition predicate on the live
         receipt: marker SUCCESS:<uid> required for closed units
  ADMIT  command-center/receipt_validate.py ACCEPT (catalog cross-ref admission)

TST-0174 additionally gets a 10-round probe1 characterization (prior round measured
a nondeterministic PermissionError crash; verdict must be based on TODAY's runs).

Plus an instrument-liveness control: the gate must REJECT a mutated copy of a
passing receipt whose reviewer.independent is flipped false while state=SUCCESS.

Output: _reviewer-w3s22/r2_results.json + terminal marker on stdout.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = ["TST-0174", "TST-0175", "TST-0176", "TST-0178", "TST-0179", "TST-0180",
         "TST-0181", "TST-0185", "TST-0188", "TST-0190", "TST-0193", "TST-0194"]
KIND = {
    "TST-0174": "cache_report", "TST-0175": "cache_report", "TST-0176": "cache_report",
    "TST-0178": "cache_report", "TST-0179": "parser_report", "TST-0180": "parser_report",
    "TST-0181": "parser_report", "TST-0185": "parser_report", "TST-0188": "shell_report",
    "TST-0190": "shell_report", "TST-0193": "shell_report", "TST-0194": "portability_report",
}
REVIEWER_ID = "w3-shard22-independent-reviewer-20261026-r2"
ROUNDS = 3
CHAR_ROUNDS = 10  # TST-0174 probe1 characterization
TIMEOUT = 600


def digest_lf(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_probe(script_rel: str, timeout: int = TIMEOUT) -> tuple[int, str]:
    env = dict(__import__("os").environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-B", script_rel], capture_output=True,
                       text=True, timeout=timeout, cwd=str(REPO), env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-4000:]


def run_gate_cli(receipt_rel: str, fragment: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-B", "platform/lib/receipt_schema_gate.py",
         receipt_rel, "--fragment", fragment, "--repo-root", str(REPO)],
        capture_output=True, text=True, timeout=300, cwd=str(REPO))
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-3000:]


def run_admit(receipt_rel: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-B", "command-center/receipt_validate.py", receipt_rel],
        capture_output=True, text=True, timeout=300, cwd=str(REPO))
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-2000:]


CATALOG = {u["id"]: u for u in json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)["work_units"]}


def check_unit(uid: str) -> dict:
    res: dict = {"unit_id": uid, "checks": {}, "fails": [], "detail": {}}
    f = res["fails"]
    rel = f"command-center/receipts/{uid}.json"

    # ---- CAT: catalog entry -------------------------------------------------
    u = CATALOG.get(uid)
    if not u:
        f.append("CAT:catalog-entry-absent")
        res["checks"]["CAT"] = False
        return res
    cat_ok = (u.get("output_path") == rel
              and u.get("output_schema") ==
              f"command-center/schema/receipt.schema.json#/$defs/{KIND[uid]}")
    res["checks"]["CAT"] = bool(cat_ok)
    if not cat_ok:
        f.append(f"CAT:output_path-or-schema-drift path={u.get('output_path')} "
                 f"schema={u.get('output_schema')}")

    # ---- ART: artifact at output_path --------------------------------------
    rp = REPO / rel
    if not rp.is_file():
        f.append("ART:receipt-missing")
        res["checks"]["ART"] = False
        return res
    if rp.stat().st_size == 0:
        f.append("ART:receipt-empty")
        res["checks"]["ART"] = False
        return res
    try:
        rec = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        f.append(f"ART:receipt-unparseable:{type(e).__name__}")
        res["checks"]["ART"] = False
        return res
    res["detail"]["state"] = rec.get("state")
    res["detail"]["report_kind"] = (rec.get("report") or {}).get("kind")
    art_ok = True
    if rec.get("unit_id") != uid:
        art_ok = False
        f.append("ART:receipt-unit-id-mismatch")
    if rec.get("state") == "SUCCESS":
        rev = rec.get("reviewer") or {}
        if rev.get("verdict") != "PASS":
            art_ok = False
            f.append(f"ART:SUCCESS-without-PASS verdict={rev.get('verdict')!r}")
        if rev.get("independent") is not True:
            art_ok = False
            f.append("ART:SUCCESS-without-independent=true")
    elif rec.get("state") == "BLOCKED":
        cls = (rec.get("failure") or {}).get("classification")
        if cls != ["reviewer-absent"]:
            art_ok = False
            f.append(f"ART:BLOCKED-classification={cls!r}")
        if rec.get("reviewer") is not None:
            art_ok = False
            f.append("ART:BLOCKED-with-reviewer-set")
        res["detail"]["awaiting_closure"] = True
    else:
        art_ok = False
        f.append(f"ART:self-declared-state={rec.get('state')!r}")
    if (rec.get("report") or {}).get("kind") != KIND[uid]:
        art_ok = False
        f.append(f"ART:report-kind={(rec.get('report') or {}).get('kind')!r} != {KIND[uid]}")
    res["checks"]["ART"] = art_ok

    # ---- named probes (from the builder's SUBAGENT-RETURN, verified live) ---
    retp = PROBES / uid / "SUBAGENT-RETURN.json"
    scripts: list[str] = []
    if not retp.is_file():
        f.append("PROBE:subagent-return-absent")
    else:
        try:
            ret = json.loads(retp.read_text(encoding="utf-8"))
        except Exception as e:
            ret = {}
            f.append(f"PROBE:subagent-return-unparseable:{type(e).__name__}")
        for np in ret.get("named_probes", []):
            toks = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
            if toks:
                scripts.append(toks[-1])
        if len(scripts) < 2:
            f.append(f"PROBE:named-probes={len(scripts)}<2")
    # cross-check: every probe*.py in the unit dir is either named or a helper
    all_py = sorted(p.name for p in (PROBES / uid).glob("*.py"))
    named = sorted(Path(s).name for s in scripts)
    unnamed = [p for p in all_py if p.startswith("probe") and p not in named]
    if unnamed:
        f.append("PROBE:unnamed-probe-script-present:" + ",".join(unnamed))

    probe_ok = len(scripts) >= 2 and not unnamed
    outputs = {}
    for s in scripts:
        rounds = CHAR_ROUNDS if (uid == "TST-0174" and Path(s).name.startswith("probe1")) else ROUNDS
        oks, tail_store = 0, []
        for rnd in range(rounds):
            try:
                rc, out = run_probe(s)
            except subprocess.TimeoutExpired:
                rc, out = 124, "TIMEOUT"
            good = (rc == 0 and f"SUCCESS:{uid}-" in out)
            oks += int(good)
            tail_store.append({"rc": rc, "sentinel": f"SUCCESS:{uid}-" in out,
                               "tail": out[-300:]})
        outputs[Path(s).name] = {"rounds": rounds, "ok_rounds": oks, "runs": tail_store}
        if oks != rounds:
            probe_ok = False
            bad = [r for r in tail_store if r["rc"] != 0 or not r["sentinel"]]
            f.append(f"PROBE:{Path(s).name}:unstable {oks}/{rounds} rc0+sentinel; "
                     f"first-bad rc={bad[0]['rc'] if bad else '?'} tail={bad[0]['tail'][-220:] if bad else '?'}")
    res["checks"]["PROBE"] = probe_ok
    res["detail"]["probe_runs"] = outputs

    # ---- MAN: manifest rows vs live bytes ----------------------------------
    manp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man_ok = manp.is_file()
    if not man_ok:
        f.append("MAN:manifest-absent")
    else:
        try:
            man = json.loads(manp.read_text(encoding="utf-8"))
        except Exception as e:
            man_ok = False
            f.append(f"MAN:manifest-unparseable:{type(e).__name__}")
            man = {}
        rows = [a for a in man.get("artifacts", []) if isinstance(a, dict)]
        if not rows:
            man_ok = False
            f.append("MAN:no-artifact-rows")
        seen_receipt_row = False
        for a in rows:
            ap_ = REPO / str(a.get("path", ""))
            if not ap_.is_file():
                man_ok = False
                f.append(f"MAN:row-file-absent:{a.get('path')}")
                continue
            d = digest_lf(ap_)
            if d != a.get("sha256"):
                man_ok = False
                f.append(f"MAN:row-sha-mismatch:{Path(a.get('path','?')).name} "
                         f"manifest={str(a.get('sha256'))[:12]} live={d[:12]}")
            if a.get("path") == rel:
                seen_receipt_row = True
                if ap_.stat().st_size != a.get("bytes"):
                    man_ok = False
                    f.append(f"MAN:receipt-row-bytes manifest={a.get('bytes')} "
                             f"live={ap_.stat().st_size}")
        if not seen_receipt_row:
            man_ok = False
            f.append("MAN:no-receipt-row")
    res["checks"]["MAN"] = man_ok

    # ---- SCHEMA: catalog output_schema fragment ----------------------------
    try:
        p2lib = load_module(REPO / "command-center" / "p2-wave" / "_p2lib.py", "p2lib_r2")
        errs = p2lib.validate(rec, f"command-center/schema/receipt.schema.json#/$defs/{KIND[uid]}")
        schema_ok = not errs
        if errs:
            f.append("SCHEMA:" + ";".join(errs[:4]))
    except Exception as e:
        schema_ok = False
        f.append(f"SCHEMA:instrument-error:{type(e).__name__}:{e}")
    res["checks"]["SCHEMA"] = schema_ok

    # ---- GATE: 12-condition predicate --------------------------------------
    try:
        grc, gout = run_gate_cli(rel, KIND[uid])
        gate_ok = (grc == 0 and f"SUCCESS:{uid}" in gout)
        if rec.get("state") == "SUCCESS" and not gate_ok:
            f.append(f"GATE:rc={grc} out={gout[-260:]}")
        res["detail"]["gate_rc"] = grc
        res["detail"]["gate_tail"] = gout[-300:]
    except Exception as e:
        gate_ok = False
        f.append(f"GATE:instrument-error:{type(e).__name__}:{e}")
    res["checks"]["GATE"] = gate_ok

    # ---- ADMIT: catalog-cross-ref admission --------------------------------
    try:
        arc, aout = run_admit(rel)
        admit_ok = (arc == 0 and "ACCEPT" in aout)
        if not admit_ok:
            f.append(f"ADMIT:rc={arc} out={aout[-200:]}")
    except Exception as e:
        admit_ok = False
        f.append(f"ADMIT:instrument-error:{type(e).__name__}:{e}")
    res["checks"]["ADMIT"] = admit_ok

    return res


def mutation_control() -> dict:
    """The gate must REJECT state=SUCCESS whose reviewer.independent is false."""
    src = REPO / "command-center/receipts/TST-0175.json"
    rec = json.loads(src.read_text(encoding="utf-8"))
    rec["reviewer"]["independent"] = False
    tmp = REPO / "_reviewer-w3s22" / "tmp" / "mutant_indep_false.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-B", "platform/lib/receipt_schema_gate.py",
         str(tmp.relative_to(REPO)), "--fragment", "cache_report",
         "--repo-root", str(REPO)],
        capture_output=True, text=True, timeout=300, cwd=str(REPO))
    out = (r.stdout or "") + (r.stderr or "")
    rejected = not (r.returncode == 0 and "SUCCESS:TST-0175" in out)
    on_c9 = "c9=" in out
    return {"rejected": rejected, "rejected_on_c9": on_c9,
            "rc": r.returncode, "tail": out[-300:]}


def main() -> int:
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(check_unit, UNITS))
    ctrl = mutation_control()
    out = {
        "reviewer": REVIEWER_ID,
        "round": 2,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mutation_control": ctrl,
        "units": results,
    }
    dst = Path(__file__).resolve().parent / "r2_results.json"
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"mutation_control rejected={ctrl['rejected']} on_c9={ctrl.get('rejected_on_c9')}")
    npass = 0
    for r in results:
        uid = r["unit_id"]
        all_ok = all(r["checks"].values())
        npass += int(all_ok)
        state = r["detail"].get("state")
        print(f"{uid} state={state} checks={r['checks']} verdict="
              f"{'PASS' if all_ok else 'FAIL'}")
        for msg in r["fails"][:6]:
            print(f"   - {msg}")
    print(f"TOTAL {npass}/{len(UNITS)} PASS elapsed={time.time()-t0:.0f}s")
    print(f"SUCCESS:w3s22-r2-verify results={dst}" if npass == len(UNITS)
          else f"FAILED:w3s22-r2-verify pass={npass}/{len(UNITS)}")
    return 0 if npass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

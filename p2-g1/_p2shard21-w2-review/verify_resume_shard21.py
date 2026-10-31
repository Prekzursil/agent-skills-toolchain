#!/usr/bin/env python3
"""Independent re-verification (resume pass), P2 wave-2 shard-21, 12 TST units.

The prior reviewer pass closed all 12 units SUCCESS; this pass adversarially
RE-DERIVES the five DELIVERED contract checks from live disk + live probe
re-runs and decides, per unit: the existing PASS closure STAYS SUCCESS, or
FAIL with the precise failing check. This pass NEVER modifies any receipt.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard21-w2-review"
IDS = ["TST-0007", "TST-0010", "TST-0012", "TST-0014", "TST-0020", "TST-0026",
       "TST-0027", "TST-0031", "TST-0053", "TST-0054", "TST-0056", "TST-0058"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg   # noqa: E402
import schema_resolver as sres      # noqa: E402


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_sha(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(b):
    return hashlib.sha256(b).hexdigest()


def walk_self_decl(node, path="", acc=None):
    """Fire on any state/status/verdict/result key whose value is a
    not-delivering token. Both-states tested in self_test()."""
    if acc is None:
        acc = []
    if isinstance(node, dict):
        for k, v in node.items():
            p2 = path + "/" + str(k)
            if (k in ("state", "status", "verdict", "result")
                    and isinstance(v, str) and v.strip().upper() in NOT_DELIVERING):
                acc.append((p2, v.strip().upper()))
            walk_self_decl(v, p2, acc)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_self_decl(v, path + "/" + str(i), acc)
    return acc


def self_test():
    bad = {"state": "BLOCKED", "x": [{"result": "FAILED"}], "verdict": "CONFIRMED",
           "status": "ok", "y": {"z": {"verdict": " TIMEOUT "}}}
    hit_paths = {h[0] for h in walk_self_decl(bad)}
    fires = {"/state", "/x/0/result", "/y/z/verdict"} <= hit_paths
    clean = walk_self_decl({"state": "SUCCESS", "verdict": "PASS",
                            "exit_code": 0, "result": "pass"})
    return fires and not clean


def cat_entry(uid):
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json") or {}
    for e in cat.get("work_units", []):
        if isinstance(e, dict) and e.get("id") == uid:
            return e
    return {}


def run_probe(script):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", "-B", str(script)], cwd=REPO,
                           env=env, capture_output=True, text=True, timeout=900,
                           errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        js = None
        for ln in (p.stdout or "").splitlines():
            s = ln.strip()
            if s.startswith("{"):
                try:
                    js = json.loads(s)
                except json.JSONDecodeError:
                    continue
        checks_all_true = None
        if isinstance(js, dict):
            ch = js.get("checks")
            if isinstance(ch, dict) and ch:
                checks_all_true = all(v is True for v in ch.values())
        return {"script": script.name, "exit": p.returncode,
                "secs": round(time.time() - t0, 1),
                "ok_marker": ("SUCCESS:" in (p.stdout or "")),
                "checks_all_true": checks_all_true,
                "pass_flag": js.get("pass") if isinstance(js, dict) else None,
                "tail": out[-300:]}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": "TIMEOUT", "secs": 900.0,
                "ok_marker": False, "checks_all_true": None, "pass_flag": None,
                "tail": "killed at 900s"}


def verify(uid):
    entry = cat_entry(uid)
    v = {"id": uid}
    fails = []
    if not entry or not entry.get("output_path"):
        v["verdict"] = "FAIL"
        v["fail_checks"] = ["no-catalog-entry-or-output_path"]
        return v
    v["output_path"] = entry.get("output_path")
    v["output_schema"] = entry.get("output_schema")

    # 1) artifact exists / non-empty / parses / not self-declared not-delivering
    ap = REPO / str(entry["output_path"])
    raw = ap.read_bytes() if ap.is_file() else b""
    v["artifact_exists"] = ap.is_file()
    v["artifact_bytes"] = len(raw)
    parsed = load_json(ap) if raw else None
    v["artifact_parses"] = isinstance(parsed, (dict, list))
    if not v["artifact_exists"]:
        fails.append("artifact-missing")
    elif len(raw) == 0:
        fails.append("artifact-empty")
    elif not v["artifact_parses"]:
        fails.append("artifact-unparseable")
    hits = walk_self_decl(parsed) if v["artifact_parses"] else [("n/a", "UNPARSEABLE")]
    top = [h for h in hits if h[0].count("/") <= 1]
    v["self_decl_top"] = top
    v["self_decl_deep"] = [h for h in hits if h[0].count("/") > 1]
    if top:
        fails.append("self-declared-not-delivering:" + repr(top))

    # 2) live probe re-runs by THIS reviewer (exit 0 + SUCCESS marker required)
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    scripts = sorted(pdir.glob("probe*.py"))
    runs = [run_probe(s) for s in scripts]
    v["probes_run"] = [r["script"] for r in runs]
    v["probe_runs"] = runs
    if not scripts:
        fails.append("no-probe-scripts-found:" + str(pdir))
    for r in runs:
        if r["exit"] != 0:
            fails.append("probe-nonzero-exit:" + str(r["script"]))
        elif not r["ok_marker"]:
            fails.append("probe-no-SUCCESS-marker:" + str(r["script"]))
        if r["checks_all_true"] is False:
            fails.append("probe-json-checks-not-all-true:" + str(r["script"]))
        if r["pass_flag"] is False:
            fails.append("probe-json-pass-false:" + str(r["script"]))

    # 3) manifest sha256 row matches live artifact (CRLF normalized)
    mp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(mp) if mp.is_file() else None
    if not isinstance(man, dict):
        v["manifest_row"] = None
        fails.append("manifest-missing-or-unparseable")
    else:
        want = str(entry["output_path"]).replace("\\", "/")
        rows = [a for a in man.get("artifacts", [])
                if str(a.get("path", "")).replace("\\", "/") == want]
        row = rows[0] if rows else None
        v["manifest_row"] = row
        if row is None:
            fails.append("manifest-row-absent:" + want)
        else:
            ns = norm_sha(raw)
            if row.get("sha256") != ns:
                fails.append("manifest-sha-mismatch manifest=" + str(row.get("sha256"))[:16]
                             + " live_norm=" + ns[:16] + " live_raw=" + raw_sha(raw)[:16])
            if row.get("bytes") != len(raw):
                fails.append("manifest-bytes-mismatch manifest=" + str(row.get("bytes"))
                             + " live=" + str(len(raw)))

    # 3b) every artifact row in the receipt itself must match disk
    row_bad = []
    if v["artifact_parses"]:
        for a in parsed.get("artifacts", []):
            rp = REPO / str(a.get("path", ""))
            if not rp.is_file():
                row_bad.append(str(a.get("path")) + ": absent")
                continue
            rb = rp.read_bytes()
            if a.get("bytes") != len(rb) or a.get("sha256") not in (norm_sha(rb), raw_sha(rb)):
                row_bad.append(str(a.get("path")) + ": bytes/sha disagree with disk")
    v["receipt_row_problems"] = row_bad
    if row_bad:
        fails.append("receipt-artifact-rows-bad:" + "; ".join(row_bad))

    # 4) output_schema validation (program's Draft 2020-12 resolver)
    try:
        errs = sres.validate_artifact(parsed, entry.get("output_schema"))
        v["schema_errors"] = [str(e)[:200] for e in list(errs)[:10]]
        if errs:
            fails.append("output_schema:" + str(len(errs)) + " errors")
    except Exception as exc:
        v["schema_errors"] = ["resolver: " + str(exc)[:200]]
        fails.append("output_schema-resolver-error")

    # 5) admission via receipt_core gate
    admiss = rsg.validate_receipt(parsed) if v["artifact_parses"] else ["unparseable"]
    v["admission_errors"] = [str(a)[:200] for a in list(admiss)[:10]]
    if admiss:
        fails.append("admission:" + str(len(admiss)) + " errors")

    # 6) closure form: state SUCCESS + reviewer PASS + independent
    rv = parsed.get("reviewer") if isinstance(parsed, dict) else None
    v["receipt_state"] = parsed.get("state") if isinstance(parsed, dict) else None
    v["reviewer"] = ({"verdict": rv.get("verdict"), "independent": rv.get("independent")}
                     if isinstance(rv, dict) else None)
    if not (isinstance(parsed, dict) and parsed.get("state") == "SUCCESS"):
        fails.append("state-not-SUCCESS")
    if not (isinstance(rv, dict) and rv.get("verdict") == "PASS"
            and rv.get("independent") is True):
        fails.append("reviewer-block-not-PASS+independent")

    v["fail_checks"] = fails
    v["verdict"] = "PASS" if not fails else "FAIL"
    return v


def main():
    if not self_test():
        print("FAILED:reviewer-selftest self-decl detector failed both-states test")
        return 1
    results = {}
    for uid in IDS:
        t0 = time.time()
        v = verify(uid)
        results[uid] = v
        line = uid + " " + v["verdict"] + " (" + str(round(time.time() - t0, 1)) + "s)"
        if v["verdict"] != "PASS":
            line += " :: " + "; ".join(v["fail_checks"])
        print(line, flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    outp = OUT / ("verify_resume_out.json")
    outp.write_text(json.dumps({"generated": stamp, "results": results}, indent=1),
                    encoding="utf-8")
    bad = [u for u in IDS if results[u]["verdict"] != "PASS"]
    print("pass=" + str(12 - len(bad)) + "/12 fail=" + str(len(bad)))
    if bad:
        print("FAILED:shard21-w2-resume-verify failing=" + ",".join(bad))
        return 1
    print("SUCCESS:shard21-w2-resume-verify 12/12 closures confirmed valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

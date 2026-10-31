#!/usr/bin/env python3
"""Independent re-verification ROUND 2, P2 wave-2 shard-21 (12 TST units).

Written fresh by the round-2 reviewer agent. READ-ONLY over receipts, manifests
and probes: this script NEVER mutates anything under command-center/.

Per unit it mechanically re-derives the five DELIVERED contract checks plus the
closure form, and adds an adversarial probe1 protocol:

  A  catalog entry has output_path + output_schema
  B  artifact at output_path: exists, non-empty, parses
  C  self-declared not-delivering walk (both-states self-tested detector):
     zero hits anywhere in the parsed artifact (post-closure)
  D  closure form: state==SUCCESS; reviewer.verdict==PASS; independent is True;
     sentinel present, names the unit, starts with "SUCCESS:"
  E  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row (path == output_path)
     present=true, sha256 == live recompute over CRLF-normalized bytes,
     bytes == live size; EVERY unit row digest-matched against disk
  F  receipt artifacts[] rows: path exists, bytes exact, sha256 normalized/raw
  G  output_schema resolved via platform/lib/schema_resolver (fail-closed)
  H  admission via platform/lib/receipt_schema_gate.validate_receipt: 0 errors
  I  live probe re-runs by THIS reviewer, cwd=repo, python -I -B:
       - claim probes (probe2*, plus non-predicate probe1_* claim scripts):
         exit 0, terminal marker line discipline: LAST non-empty stdout line
         starts with "SUCCESS:" and NO line STARTS with "FAILED:" (a FAILED:
         string EMBEDDED in captured data - e.g. TST-0012's probe2 embedding
         the downstream consumers' own drift reports - is data, not a verdict)
       - probe1_delivery_predicate.py is the BUILDER-HANDOFF predicate: it
         asserts state==BLOCKED, which cannot hold once the reviewer closure
         this program mandates is applied (fleet precedent CC-0017 ships a
         mode-aware predicate; these 12 carry the phase-locked variant).  It is
         therefore run and PARTITIONED: any failing check outside the
         phase-locked set {state_blocked, failure_reviewer_absent} is a REAL
         failure; every closure-invariant check must be true.
  J  residual-gate honesty: live evaluate_gate_a(repo_root=REPO) red set must
     be a SUBSET of the conditions_red recorded at closure (no silent drift).

Exit 0 only when ALL 12 units hold ALL checks.
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
OUT = REPO / "_p2shard21-w2-review-r2"
IDS = ["TST-0007", "TST-0010", "TST-0012", "TST-0014", "TST-0020", "TST-0026",
       "TST-0027", "TST-0031", "TST-0054", "TST-0058"]
IDS.extend(["TST-0053", "TST-0056"])  # keep the full 12, order stable
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
# probe1 checks that read the RECEIPT's builder-handoff state: by the program's
# own lifecycle (builders BLOCK / reviewer closes) these are false after ANY
# legitimate closure, so their failure post-closure is expected, not evidence.
PHASE_LOCKED = {"state_blocked", "failure_reviewer_absent"}

sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as rsg   # noqa: E402
import schema_resolver as sres      # noqa: E402


def load_json(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def norm_sha(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def walk_self_decl(node, path="", acc=None):
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


def self_test() -> bool:
    bad = {"state": " BLOCKED ", "x": [{"result": "FAILED"}], "verdict": "CONFIRMED",
           "status": "ok", "y": {"z": {"verdict": "TIMEOUT"}}, "w": {"state": "SEVERED"}}
    hits = {h[0] for h in walk_self_decl(bad)}
    fires = {"/state", "/x/0/result", "/y/z/verdict", "/w/state"} <= hits
    clean = walk_self_decl({"state": "SUCCESS", "probe": "x",
                            "raw_tail": "FAILED:cc-render drift=2 is captured data"})
    ok = fires and not clean
    # marker discipline self-test: data-embedded FAILED must not count as verdict
    stdout_probe = ('{"checks":{"a":true},"pass":true,"tail":["FAILED:unit-x absent"]}\n'
                    "SUCCESS:unit-x-probe2 all good\n")
    lines = [l for l in stdout_probe.splitlines() if l.strip()]
    marker_ok = lines[-1].startswith("SUCCESS:") and not any(
        l.startswith("FAILED:") for l in lines)
    return ok and marker_ok


def run_probe(script: Path) -> dict:
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
        failed_checks = []
        if isinstance(js, dict) and isinstance(js.get("checks"), dict) and js["checks"]:
            checks_all_true = all(v is True for v in js["checks"].values())
            failed_checks = sorted(k for k, v in js["checks"].items() if v is not True)
        lines = [l for l in (p.stdout or "").splitlines() if l.strip()]
        terminal_ok = bool(lines) and lines[-1].startswith("SUCCESS:")
        no_failed_verdict = not any(l.startswith("FAILED:") for l in lines)
        return {"script": script.name, "exit": p.returncode,
                "secs": round(time.time() - t0, 1),
                "terminal_success": terminal_ok,
                "no_failed_verdict_line": no_failed_verdict,
                "pass_flag": js.get("pass") if isinstance(js, dict) else None,
                "checks_all_true": checks_all_true,
                "failed_checks": failed_checks,
                "tail": out[-300:]}
    except subprocess.TimeoutExpired:
        return {"script": script.name, "exit": "TIMEOUT", "secs": 900.0,
                "terminal_success": False, "no_failed_verdict_line": False,
                "pass_flag": None, "checks_all_true": None, "failed_checks": [],
                "tail": "killed at 900s"}


def cat_entry(uid):
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json") or {}
    for e in cat.get("work_units", []):
        if isinstance(e, dict) and e.get("id") == uid:
            return e
    return {}


def verify(uid: str) -> dict:
    entry = cat_entry(uid)
    v = {"id": uid}
    fails = []
    if not entry or not entry.get("output_path") or not entry.get("output_schema"):
        v["verdict"] = "FAIL"
        v["fail_checks"] = ["catalog-entry-missing-output_path-or-schema"]
        return v
    v["output_path"] = entry["output_path"]
    v["output_schema"] = entry["output_schema"]

    # B) artifact
    ap = REPO / str(entry["output_path"])
    raw = ap.read_bytes() if ap.is_file() else b""
    v["artifact_exists"] = ap.is_file()
    v["artifact_bytes"] = len(raw)
    parsed = load_json(ap) if raw else None
    v["artifact_parses"] = isinstance(parsed, (dict, list))
    if not ap.is_file():
        fails.append("artifact-missing")
    elif len(raw) == 0:
        fails.append("artifact-empty")
    elif not v["artifact_parses"]:
        fails.append("artifact-unparseable")

    # C) self-declared not-delivering (post-closure: zero tolerance, top+deep)
    hits = walk_self_decl(parsed) if v["artifact_parses"] else [("n/a", "UNPARSEABLE")]
    v["self_decl_hits"] = hits
    if hits:
        fails.append("self-declared-not-delivering:" + repr(hits[:6]))

    # D) closure form
    if isinstance(parsed, dict):
        state = parsed.get("state")
        rev = parsed.get("reviewer") if isinstance(parsed.get("reviewer"), dict) else {}
        sentinel = str(parsed.get("sentinel") or "")
        v["state"] = state
        v["reviewer"] = {"verdict": rev.get("verdict"), "independent": rev.get("independent"),
                         "reviewer_id": rev.get("reviewer_id")}
        if state != "SUCCESS":
            fails.append("state-not-SUCCESS:" + str(state))
        if rev.get("verdict") != "PASS":
            fails.append("reviewer-verdict-not-PASS")
        if rev.get("independent") is not True:
            fails.append("reviewer-independent-not-true")
        if not sentinel.startswith("SUCCESS:") or uid not in sentinel:
            fails.append("sentinel-not-SUCCESS-naming-unit")
    else:
        fails.append("no-parsed-artifact-for-closure-form")

    # E) per-unit manifest
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    man = load_json(pdir / "UNIT-ARTIFACT-MANIFEST.json probes".replace(" probes", ""))
    if not isinstance(man, dict):
        fails.append("manifest-missing-or-unparseable")
        v["manifest_row"] = None
    else:
        want = str(entry["output_path"]).replace("\\", "/")
        rows = [a for a in man.get("artifacts", [])
                if isinstance(a, dict) and str(a.get("path", "")).replace("\\", "/") == want]
        row = rows[0] if rows else None
        v["manifest_row"] = {k: row.get(k) for k in ("path", "sha256", "bytes", "present")} if row else None
        if row is None:
            fails.append("manifest-primary-row-absent:" + want)
        else:
            if row.get("present") is not True:
                fails.append("manifest-primary-present-not-true")
            if row.get("sha256") != norm_sha(raw):
                fails.append("manifest-sha-mismatch manifest=" + str(row.get("sha256"))[:16]
                             + " live_norm=" + norm_sha(raw)[:16] + " live_raw=" + raw_sha(raw)[:16])
            if row.get("bytes") != len(raw):
                fails.append("manifest-bytes-mismatch manifest=" + str(row.get("bytes"))
                             + " live=" + str(len(raw)))
        bad_rows = []
        for a in man.get("artifacts", []):
            if not isinstance(a, dict) or a.get("unit_id") != uid:
                continue
            rp = REPO / str(a.get("path", ""))
            if not rp.is_file():
                bad_rows.append(str(a.get("path")) + ": absent")
                continue
            rb = rp.read_bytes()
            if a.get("sha256") and a.get("sha256") not in (norm_sha(rb), raw_sha(rb)):
                bad_rows.append(str(a.get("path")) + ": sha disagrees")
        v["manifest_bad_rows"] = bad_rows
        if bad_rows:
            fails.append("manifest-unit-rows-bad:" + "; ".join(bad_rows[:3]))

    # F) receipt artifacts[] rows vs disk
    row_bad = []
    if v["artifact_parses"]:
        for a in parsed.get("artifacts", []):
            rp = REPO / str(a.get("path", ""))
            if not rp.is_file():
                row_bad.append(str(a.get("path")) + ": absent")
                continue
            rb = sha_row_check(a, rp)
            if rb:
                row_bad.append(str(a.get("path")) + ": " + rb)
    v["receipt_row_problems"] = row_bad
    if row_bad:
        fails.append("receipt-artifact-rows-bad:" + "; ".join(row_bad[:3]))

    # G) output_schema
    try:
        errs = list(sres.validate_artifact(parsed, entry.get("output_schema")))
        v["schema_errors"] = [str(e)[:200] for e in errs[:8]]
        if errs:
            fails.append("output_schema:" + str(len(errs)) + " errors")
    except Exception as exc:
        v["schema_errors"] = ["resolver: " + str(exc)[:200]]
        fails.append("output_schema-resolver-error")

    # H) admission
    try:
        admiss = list(rsg.validate_receipt(parsed)) if v["artifact_parses"] else ["unparseable"]
    except Exception as exc:
        admiss = ["gate-call:" + str(exc)[:150]]
    v["admission_errors"] = [str(a)[:200] for a in admiss[:8]]
    if admiss:
        fails.append("admission:" + str(len(admiss)) + " errors")

    # I) live probe re-runs by THIS reviewer
    scripts = sorted(pdir.glob("probe*.py"))
    v["probes_run"] = []
    if not scripts:
        fails.append("no-probe-scripts-found")
    handoff_runs = []
    claim_probe_count = 0
    for s in scripts:
        r = run_probe(s)
        v["probes_run"].append({k: r[k] for k in ("script", "exit", "secs", "terminal_success",
                                                  "no_failed_verdict_line", "pass_flag",
                                                  "checks_all_true", "failed_checks")})
        if s.name == "probe1_delivery_predicate.py":
            handoff_runs.append(r)
            real = [c for c in r["failed_checks"] if c not in PHASE_LOCKED]
            phase = [c for c in r["failed_checks"] if c in PHASE_LOCKED]
            r["phase_locked_failures"] = phase
            r["real_failures"] = real
            if real:
                fails.append("handoff-predicate-real-failure:" + s.name + ":" + ",".join(real))
            if r["exit"] == 0:
                fails.append("handoff-predicate-exit0-post-closure-unexpected")
        else:
            claim_probe_count += 1
            if r["exit"] != 0:
                fails.append("probe-nonzero-exit:" + s.name + ":" + ",".join(r["failed_checks"]))
            elif not r["terminal_success"] or not r["no_failed_verdict_line"]:
                fails.append("probe-terminal-marker-bad:" + s.name
                             + (" terminal_success=" + str(r["terminal_success"]))
                             + (" no_failed_verdict_line=" + str(r["no_failed_verdict_line"])))
            if r["pass_flag"] is False:
                fails.append("probe-json-pass-false:" + s.name)
            if r["checks_all_true"] is False:
                fails.append("probe-json-checks-not-all-true:" + s.name + ":" + ",".join(r["failed_checks"]))
    if claim_probe_count < 1:
        fails.append("no-claim-probe-ran")
    v["handoff_runs"] = [{k: h.get(k) for k in ("script", "exit", "failed_checks",
                                                "phase_locked_failures", "real_failures")}
                         for h in handoff_runs]

    # J) residual-gate honesty: live reds must not exceed the recorded set
    try:
        g = rsg.evaluate_gate_a(parsed, repo_root=REPO)
        live_reds = sorted(c.n for c in g.blocking_conditions)
        recorded = ((parsed.get("extensions") or {}).get("reviewer_residual_gate") or {}).get("conditions_red")
        v["live_gate_reds"] = live_reds
        v["recorded_gate_reds"] = recorded
        if isinstance(recorded, list) and not set(live_reds) <= set(recorded):
            fails.append("gate-drift live=" + str(live_reds) + " recorded=" + str(recorded))
    except Exception as exc:
        fails.append("gate-eval:" + str(exc)[:120])

    v["fail_checks"] = fails
    v["verdict"] = "PASS" if not fails else "FAIL"
    return v


def sha_row_check(a, rp: Path) -> str:
    rb = rp.read_bytes()
    if a.get("bytes") != len(rb):
        return "bytes declared " + str(a.get("bytes")) + " != on-disk " + str(len(rb))
    if a.get("sha256") and a.get("sha256") not in (norm_sha(rb), raw_sha(rb)):
        return "sha256 disagrees with disk"
    return ""


def main() -> int:
    if not self_test():
        print("FAILED:round2-selftest detector or marker-discipline failed the both-states test")
        return 1
    print("ok round2-selftest self-decl fires on bad/silent on good; "
          "data-embedded FAILED not read as verdict", flush=True)
    OUT.mkdir(exist_ok=True)
    results = {}
    for uid in IDS:
        t0 = time.time()
        v = verify(uid)
        results[uid] = v
        line = uid + " " + v["verdict"] + " (" + str(round(time.time() - t0, 1)) + "s)"
        if v["verdict"] != "PASS":
            line += " :: " + " | ".join(v["fail_checks"])
        print(line, flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    (OUT / "verify_round2_out.json").write_text(
        json.dumps({"generated": stamp, "results": results}, indent=1), encoding="utf-8")
    bad = [u for u in IDS if results[u]["verdict"] != "PASS"]
    print("pass=" + str(12 - len(bad)) + "/12 fail=" + str(len(bad)))
    if bad:
        print("FAILED:shard21-w2-round2-verify failing=" + ",".join(bad))
        return 1
    print("SUCCESS:shard21-w2-round2-verify 12/12 closures confirmed valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

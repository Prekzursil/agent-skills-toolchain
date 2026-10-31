#!/usr/bin/env python3
"""w3s23 review round r4 - INDEPENDENT verification instrument (written fresh).

NOT derived from r1/r2/r3 code. Checks per unit, fail-closed:
  C1  receipt exists at catalog output_path, size > 0
  C2  receipt parses as JSON
  C3  not self-declared BLOCKED/FAILED: state not in {BLOCKED, FAILED}
      AND sentinel not FAILED:-prefixed (SUCCESS sentinel must start SUCCESS:/SENTINEL:)
  C4  manifest primary row: exactly one role=primary row, path == output_path,
      LF-normalized sha256(recomputed live) == registered; receipt's own
      artifacts[] primary entry bytes == measured on-disk size
  C5  every manifest row re-hashes (CRLF->LF) to its registered sha256
  C6  every named-probe row re-run by THIS reviewer in pinned Git Bash:
      exit 0, no line-anchored FAILED: marker, last JSON ok != false
  C7  same probes re-run in pwsh 7 (second Windows shell per reviewer_requirement);
      exit-code divergence = finding
  C8  output_schema via estate-canonical schema_resolver.validate_artifact (0 errors)
  C9  output_schema via hand-derived targeted validator encoded directly from a
      read of the physical schema defs (second independent signal)

Soundness: mutation self-test (synthetic valid doc + 9 mutations, each must be
caught by resolver or hand validator) runs BEFORE any unit verdict is read.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
GITBASH = r"C:\Program Files\Git\bin\bash.exe"
PWSH = "pwsh"
CATALOG = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
OUT = Path(__file__).resolve().parent

UNITS = ["TST-0195", "TST-0197", "TST-0202", "TST-0204", "TST-0206", "TST-0215",
         "TST-0219", "TST-0221", "TST-0223", "TST-0227", "TST-0230", "TST-0233"]

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UNITID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]{4}$")
ISO_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$")
SENT_RE = re.compile(r"^(?:(?:SUCCESS|FAILED):[A-Z][A-Z0-9]*-[0-9]{4}(?:[\s:].*)?|SENTINEL:[A-Z][A-Z0-9]*-[0-9]{4}:[A-Z0-9][A-Z0-9-]*(?:[\s].*)?)$")
FAILED_MARKER = re.compile(r"^FAILED:", re.M)
TERMINAL_STATES = {"SUCCESS", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT", "SUPERSEDED", "DROPPED-BY-OWNER"}
ROLE_ENUM = {"primary", "supporting", "log", "fixture", "control"}
EOL_ENUM = {"LF", "CRLF", "MIXED", "BINARY", "NOT-CHECKED"}
VERDICT_ENUM = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
CONF_ENUM = {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}
TEST_RESULT_ENUM = {"PASS", "FAIL", "ERROR", "SKIP", "NOT-RUN"}
NC_KIND_ENUM = {"mutation", "malformed-input", "known-broken-fixture", "absent-input", "adversarial-payload", "other"}
PROBE_METHOD_ENUM = {"command", "file-read", "http", "process-table", "byte-compare",
                     "schema-validate", "static-analysis", "manual-inspection", "test-run", "other"}
SEV_ENUM = {"P0", "P1", "P2", "P3", "INFO"}


def lf_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ---------------- hand-derived targeted validator (C9) ----------------

def _probe_errs(pr, where, errs):
    if not isinstance(pr, dict):
        errs.append(f"{where}: probe not object"); return
    for k in ("role", "method", "command", "raw_output", "fingerprint"):
        if k not in pr:
            errs.append(f"{where}: probe missing required {k}")
    if pr.get("role") not in ("source", "verifier"):
        errs.append(f"{where}: probe.role invalid")
    if pr.get("method") not in PROBE_METHOD_ENUM:
        errs.append(f"{where}: probe.method invalid")
    for k in ("command", "raw_output", "fingerprint"):
        v = pr.get(k)
        if not isinstance(v, str) or len(v) < 1:
            errs.append(f"{where}: probe.{k} must be non-empty string")
    extra = set(pr) - {"role", "method", "command", "raw_output", "fingerprint", "exit_code"}
    if extra:
        errs.append(f"{where}: probe unexpected keys {sorted(extra)}")


def hand_validate(d, kind: str):
    errs = []
    if not isinstance(d, dict):
        return ["receipt not object"]
    if d.get("schema_version") != 1:
        errs.append("schema_version must be const 1")
    uid = d.get("unit_id")
    if not isinstance(uid, str) or not UNITID_RE.match(uid):
        errs.append("unit_id pattern")
    st = d.get("state")
    if st not in TERMINAL_STATES:
        errs.append("state enum")
    sent = d.get("sentinel")
    if not isinstance(sent, str) or not SENT_RE.match(sent):
        errs.append("sentinel pattern")
    if st == "SUCCESS" and isinstance(sent, str) and not (sent.startswith("SUCCESS:") or sent.startswith("SENTINEL:")):
        errs.append("SUCCESS sentinel must start SUCCESS:/SENTINEL:")
    if isinstance(sent, str) and sent.startswith("FAILED:") and st == "SUCCESS":
        errs.append("FAILED: sentinel under SUCCESS")
    if not isinstance(d.get("spec_anchor"), str) or len(d["spec_anchor"]) < 3:
        errs.append("spec_anchor")
    mbt = d.get("min_bytes_threshold")
    if not isinstance(mbt, int) or isinstance(mbt, bool) or mbt < 1:
        errs.append("min_bytes_threshold")
    arts = d.get("artifacts")
    if not isinstance(arts, list) or len(arts) < 1:
        errs.append("artifacts minItems 1")
    else:
        for i, a in enumerate(arts):
            w = f"artifacts/{i}"
            if not isinstance(a, dict):
                errs.append(f"{w}: not object"); continue
            for k in ("path", "bytes", "sha256", "exists"):
                if k not in a:
                    errs.append(f"{w}: missing required {k}")
            p = a.get("path")
            if not isinstance(p, str) or not p or "\\" in p or len(p) > 1024:
                errs.append(f"{w}.path")
            b = a.get("bytes")
            if not isinstance(b, int) or isinstance(b, bool) or b < 1:
                errs.append(f"{w}.bytes must be int >= 1 (size on disk)")
            if not (isinstance(a.get("sha256"), str) and SHA_RE.match(a.get("sha256", ""))):
                errs.append(f"{w}.sha256 hex64")
            if a.get("exists") is not True:
                errs.append(f"{w}.exists must be const true")
            if "role" in a and a["role"] not in ROLE_ENUM:
                errs.append(f"{w}.role invalid")
            if "eol" in a and a["eol"] not in EOL_ENUM:
                errs.append(f"{w}.eol invalid")
            extra = set(a) - {"path", "bytes", "sha256", "exists", "eol", "role"}
            if extra:
                errs.append(f"{w}: unexpected keys {sorted(extra)}")
    ev = d.get("evidence")
    if not isinstance(ev, list) or len(ev) < 1:
        errs.append("evidence minItems 1")
    else:
        if st == "SUCCESS" and len(ev) < 2:
            errs.append("evidence minItems 2 under SUCCESS")
        for i, e in enumerate(ev):
            w = f"evidence/{i}"
            if not isinstance(e, dict):
                errs.append(f"{w}: not object"); continue
            for k in ("claim", "verdict", "anchor", "probes"):
                if k not in e:
                    errs.append(f"{w}: missing required {k}")
            if e.get("verdict") not in VERDICT_ENUM:
                errs.append(f"{w}.verdict invalid")
            if not (isinstance(e.get("claim"), str) and e["claim"]):
                errs.append(f"{w}.claim")
            if not (isinstance(e.get("anchor"), str) and e["anchor"]):
                errs.append(f"{w}.anchor")
            pr = e.get("probes")
            if not isinstance(pr, list) or len(pr) < 1:
                errs.append(f"{w}.probes minItems 1")
            else:
                for j, p in enumerate(pr):
                    _probe_errs(p, f"{w}.probes/{j}", errs)
                if e.get("verdict") in ("CONFIRMED", "REFUTED"):
                    if len(pr) < 2:
                        errs.append(f"{w}: CONFIRMED/REFUTED needs probe pair (minItems 2)")
                    roles = [p.get("role") for p in pr if isinstance(p, dict)]
                    if "source" not in roles or "verifier" not in roles:
                        errs.append(f"{w}: CONFIRMED/REFUTED needs source+verifier roles")
                    if "confidence" not in e:
                        errs.append(f"{w}: CONFIRMED/REFUTED requires confidence")
                    elif e.get("confidence") not in CONF_ENUM:
                        errs.append(f"{w}.confidence invalid")
            if e.get("unverified") is True and "settling_experiment" not in e:
                errs.append(f"{w}: unverified=true requires settling_experiment")
            extra = set(e) - {"claim", "verdict", "confidence", "anchor", "probes", "unverified", "settling_experiment"}
            if extra:
                errs.append(f"{w}: unexpected keys {sorted(extra)}")
    tests = d.get("tests")
    if st == "SUCCESS":
        if not isinstance(tests, list) or len(tests) < 1:
            errs.append("tests minItems 1 under SUCCESS")
        else:
            for i, t in enumerate(tests):
                w = f"tests/{i}"
                if not isinstance(t, dict):
                    errs.append(f"{w}: not object"); continue
                for k in ("id", "command", "result"):
                    if k not in t:
                        errs.append(f"{w}: missing required {k}")
                if t.get("result") not in TEST_RESULT_ENUM:
                    errs.append(f"{w}.result invalid")
                elif t["result"] != "PASS":
                    errs.append(f"{w}.result={t['result']} under SUCCESS")
                extra = set(t) - {"id", "name", "command", "result", "assertions", "duration_seconds", "output_tail"}
                if extra:
                    errs.append(f"{w}: unexpected keys {sorted(extra)}")
    elif isinstance(tests, list):
        for i, t in enumerate(tests):
            if isinstance(t, dict):
                for k in ("id", "command", "result"):
                    if k not in t:
                        errs.append(f"tests/{i}: missing required {k}")
                if t.get("result") not in TEST_RESULT_ENUM:
                    errs.append(f"tests/{i}.result invalid")
    ncs = d.get("negative_controls")
    if st == "SUCCESS":
        if not isinstance(ncs, list) or len(ncs) < 1:
            errs.append("negative_controls minItems 1 under SUCCESS")
        else:
            for i, c in enumerate(ncs):
                w = f"negative_controls/{i}"
                if not isinstance(c, dict):
                    errs.append(f"{w}: not object"); continue
                for k in ("id", "kind", "description", "fired_on_bad_state", "silent_on_good_state"):
                    if k not in c:
                        errs.append(f"{w}: missing required {k}")
                if c.get("kind") not in NC_KIND_ENUM:
                    errs.append(f"{w}.kind invalid")
                if c.get("fired_on_bad_state") is False:
                    errs.append(f"{w}.fired_on_bad_state=false under SUCCESS")
                if c.get("silent_on_good_state") is False:
                    errs.append(f"{w}.silent_on_good_state=false under SUCCESS")
    rv = d.get("reviewer")
    if not isinstance(rv, dict):
        errs.append("reviewer required (SUCCESS adjudication)")
    else:
        for k in ("reviewer_id", "verdict", "independent"):
            if k not in rv:
                errs.append(f"reviewer: missing required {k}")
        if rv.get("verdict") not in ("PASS", "FAIL", "CHANGES-REQUESTED", "NOT-REVIEWED"):
            errs.append("reviewer.verdict invalid")
        if st == "SUCCESS":
            if rv.get("verdict") != "PASS":
                errs.append("SUCCESS requires reviewer.verdict=PASS")
            if rv.get("independent") is not True:
                errs.append("SUCCESS requires reviewer.independent=true")
        extra = set(rv) - {"reviewer_id", "verdict", "independent", "fresh_context", "vendor", "notes", "reviewed_at"}
        if extra:
            errs.append(f"reviewer: unexpected keys {sorted(extra)}")
    mr = d.get("manifest_registration")
    if st == "SUCCESS":
        if not isinstance(mr, dict):
            errs.append("manifest_registration required under SUCCESS")
        else:
            if mr.get("registered") is not True:
                errs.append("manifest_registration.registered must be true under SUCCESS")
            if not (isinstance(mr.get("manifest_path"), str) and mr["manifest_path"]):
                errs.append("manifest_registration.manifest_path")
    dcs = d.get("downstream_consumers")
    if st == "SUCCESS":
        if not isinstance(dcs, list) or len(dcs) < 1:
            errs.append("downstream_consumers minItems 1 under SUCCESS")
        else:
            for i, c in enumerate(dcs):
                w = f"downstream_consumers/{i}"
                if not isinstance(c, dict):
                    errs.append(f"{w}: not object"); continue
                for k in ("consumer", "artifact_path", "executed", "read_ok", "probe"):
                    if k not in c:
                        errs.append(f"{w}: missing required {k}")
                if c.get("executed") is False:
                    errs.append(f"{w}.executed=false under SUCCESS")
                if c.get("read_ok") is False:
                    errs.append(f"{w}.read_ok=false under SUCCESS")
                if isinstance(c.get("probe"), dict):
                    _probe_errs(c["probe"], f"{w}.probe", errs)
    defs_ = d.get("defects")
    if isinstance(defs_, list) and st == "SUCCESS":
        for i, x in enumerate(defs_):
            if isinstance(x, dict) and x.get("status") == "open" and x.get("severity") in ("P0", "P1"):
                errs.append(f"defects/{i}: open P0/P1 defect under SUCCESS")
    ts = d.get("timestamps")
    if not isinstance(ts, dict) or "started_at" not in ts or "ended_at" not in ts:
        errs.append("timestamps requires started_at+ended_at")
    else:
        for k in ("started_at", "ended_at"):
            if not (isinstance(ts[k], str) and ISO_RE.match(ts[k])):
                errs.append(f"timestamps.{k} not ISO with offset")
    rt = d.get("retry")
    if not isinstance(rt, dict) or "count" not in rt or "policy" not in rt:
        errs.append("retry requires count+policy")
    else:
        c = rt.get("count")
        if not isinstance(c, int) or isinstance(c, bool) or not (0 <= c <= 32):
            errs.append("retry.count must be int 0..32")
    ru = d.get("residual_unknowns")
    if st == "SUCCESS" and not isinstance(ru, list):
        errs.append("residual_unknowns required under SUCCESS")
    if isinstance(ru, list):
        for i, x in enumerate(ru):
            if isinstance(x, dict):
                for k in ("claim", "verdict", "settling_experiment"):
                    if k not in x:
                        errs.append(f"residual_unknowns/{i}: missing required {k}")
    if st in ("FAILED", "BLOCKED", "SEVERED", "TIMEOUT"):
        f = d.get("failure")
        if not isinstance(f, dict):
            errs.append("failure required for FAILED/BLOCKED/SEVERED/TIMEOUT")
        else:
            cl = f.get("classification")
            if not isinstance(cl, list) or len(cl) < 1:
                errs.append("failure.classification minItems 1")
            if not (isinstance(f.get("reason"), str) and f["reason"]):
                errs.append("failure.reason")
    rep = d.get("report")
    if kind == "portability_report":
        if not isinstance(rep, dict):
            errs.append("report required")
        else:
            if rep.get("kind") != "portability_report":
                errs.append("report.kind must be const portability_report")
            obs = rep.get("observations")
            if not isinstance(obs, list) or len(obs) < 1:
                errs.append("report.observations minItems 1")
            else:
                for i, o in enumerate(obs):
                    if isinstance(o, dict):
                        for k in ("name", "measured", "method", "anchor"):
                            if k not in o:
                                errs.append(f"report.observations/{i}: missing required {k}")
            ci = rep.get("control_ids")
            if not isinstance(ci, list) or len(ci) < 1:
                errs.append("report.control_ids minItems 1")
    elif kind == "security_report":
        if not isinstance(rep, dict):
            errs.append("report required")
        else:
            if rep.get("kind") != "security_report":
                errs.append("report.kind must be const security_report")
            fnd = rep.get("findings")
            if not isinstance(fnd, list):
                errs.append("report.findings required")
            else:
                for i, x in enumerate(fnd):
                    if isinstance(x, dict):
                        for k in ("id", "severity", "summary", "anchor", "exploit_proven", "credential_redacted"):
                            if k not in x:
                                errs.append(f"report.findings/{i}: missing required {k}")
                        if x.get("credential_redacted") is not True:
                            errs.append(f"report.findings/{i}.credential_redacted must be true")
                        if x.get("severity") not in SEV_ENUM:
                            errs.append(f"report.findings/{i}.severity invalid")
            sc = rep.get("scanners")
            if not isinstance(sc, list) or len(sc) < 1:
                errs.append("report.scanners minItems 1")
            else:
                for i, x in enumerate(sc):
                    if isinstance(x, dict):
                        for k in ("name", "version", "installed"):
                            if k not in x:
                                errs.append(f"report.scanners/{i}: missing required {k}")
    elif kind == "benchmark_result":
        if not isinstance(rep, dict):
            errs.append("report required")
        else:
            if rep.get("kind") != "benchmark_result":
                errs.append("report.kind must be const benchmark_result")
            mets = rep.get("metrics")
            if not isinstance(mets, list) or len(mets) < 1:
                errs.append("report.metrics minItems 1")
            else:
                for i, x in enumerate(mets):
                    if isinstance(x, dict):
                        for k in ("name", "value", "unit", "n", "variance_band", "null_model"):
                            if k not in x:
                                errs.append(f"report.metrics/{i}: missing required {k}")
                    n = x.get("n")
                    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                        errs.append(f"report.metrics/{i}.n must be int >= 1")
            if rep.get("input_non_empty") is not True:
                errs.append("report.input_non_empty must be const true")
    return errs


# ---------------- soundness: mutation self-test ----------------

def synthetic_valid(kind):
    doc = {
        "schema_version": 1,
        "unit_id": "TST-9999",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-9999",
        "spec_anchor": "_USER-PROMPTS.md:11016",
        "min_bytes_threshold": 100,
        "artifacts": [{"path": "command-center/receipts/TST-9999.json", "bytes": 500,
                       "sha256": "a" * 64, "exists": True, "eol": "LF", "role": "primary"}],
        "evidence": [
            {"claim": "c1", "verdict": "CONFIRMED", "confidence": "likely", "anchor": "x:1",
             "probes": [
                 {"role": "source", "method": "command", "command": "cmd1", "raw_output": "o", "fingerprint": "f1"},
                 {"role": "verifier", "method": "file-read", "command": "cmd2", "raw_output": "o2", "fingerprint": "f2"}]},
            {"claim": "c2", "verdict": "PARTIAL", "anchor": "y:2",
             "probes": [{"role": "source", "method": "command", "command": "cmd3", "raw_output": "o3", "fingerprint": "f3"}]},
        ],
        "tests": [{"id": "t1", "command": "run", "result": "PASS"}],
        "negative_controls": [{"id": "n1", "kind": "mutation", "description": "d",
                               "fired_on_bad_state": True, "silent_on_good_state": True}],
        "reviewer": {"reviewer_id": "independent-r4", "verdict": "PASS", "independent": True},
        "manifest_registration": {"registered": True, "manifest_path": "m.json"},
        "downstream_consumers": [{"consumer": "c", "artifact_path": "p", "executed": True, "read_ok": True,
                                  "probe": {"role": "source", "method": "file-read", "command": "rd",
                                            "raw_output": "ok", "fingerprint": "f4"}}],
        "defects": [],
        "timestamps": {"started_at": "2026-10-26T10:00:00Z", "ended_at": "2026-10-26T11:00:00Z"},
        "retry": {"count": 0, "policy": "two strikes"},
        "residual_unknowns": [],
        "report": {"kind": kind, "observations": [{"name": "o", "measured": "m", "method": "cmd", "anchor": "a:1"}],
                   "control_ids": ["n1"]},
    }
    if kind == "security_report":
        doc["report"] = {"kind": "security_report",
                         "findings": [{"id": "F1", "severity": "P2", "summary": "s", "anchor": "a",
                                       "exploit_proven": False, "credential_redacted": True}],
                         "scanners": [{"name": "s", "version": "1", "installed": True}]}
    elif kind == "benchmark_result":
        doc["report"] = {"kind": "benchmark_result", "input_non_empty": True,
                         "metrics": [{"name": "m", "value": 1.0, "unit": "u", "n": 5,
                                      "variance_band": "v", "null_model": "n"}]}
    return doc


def mutation_matrix(kind):
    good = synthetic_valid(kind)
    muts = []
    m = json.loads(json.dumps(good)); m["artifacts"][0]["role"] = "primary-implementation"
    muts.append(("artifacts.role-invalid-enum", m))
    m = json.loads(json.dumps(good)); del m["min_bytes_threshold"]
    muts.append(("core-field-missing", m))
    m = json.loads(json.dumps(good)); m["evidence"][0]["probes"] = m["evidence"][0]["probes"][:1]
    muts.append(("confirmed-single-probe", m))
    m = json.loads(json.dumps(good)); m["tests"][0]["result"] = "FAIL"
    muts.append(("failing-test-under-success", m))
    m = json.loads(json.dumps(good)); m["downstream_consumers"][0]["executed"] = False
    muts.append(("consumer-not-executed", m))
    m = json.loads(json.dumps(good)); m["defects"] = [{"id": "F1", "severity": "P1", "status": "open", "summary": "x"}]
    muts.append(("open-P1-under-success", m))
    m = json.loads(json.dumps(good)); m["sentinel"] = "FAILED:TST-9999 reason"
    muts.append(("failed-sentinel-under-success", m))
    m = json.loads(json.dumps(good)); m["timestamps"]["started_at"] = "2026-10-26 10:00:00"
    muts.append(("naive-timestamp", m))
    m = json.loads(json.dumps(good)); m["reviewer"]["independent"] = False
    muts.append(("reviewer-not-independent", m))
    return good, muts


def soundness():
    sys.path.insert(0, r"C:\Users\Prekzursil\source\ast-integrate\platform\lib")
    import schema_resolver as sr
    report = {"resolver_green_on_synthetic": {}, "hand_green_on_synthetic": {}, "mutations": {}}
    for kind, ptr in [("portability_report", "command-center/schema/receipt.schema.json#/$defs/portability_report"),
                      ("security_report", "command-center/schema/receipt.schema.json#/$defs/security_report"),
                      ("benchmark_result", "command-center/schema/receipt.schema.json#/$defs/benchmark_result")]:
        good = synthetic_valid(kind)
        r_errs = sr.validate_artifact(good, ptr)
        h_errs = hand_validate(good, kind)
        report["resolver_green_on_synthetic"][kind] = r_errs
        report["hand_green_on_synthetic"][kind] = h_errs
        caught = 0
        detail = {}
        _good, muts = mutation_matrix(kind)
        for name, mut in muts:
            re_ = sr.validate_artifact(mut, ptr)
            he_ = hand_validate(mut, kind)
            ok = bool(re_) or bool(he_)
            caught += 1 if ok else 0
            detail[name] = {"resolver": len(re_), "hand": len(he_), "caught": ok}
        report["mutations"][kind] = {"caught": caught, "of": 9, "detail": detail}
    return report, sr


# ---------------- probes ----------------

def run_bash(cwd: Path, script: str, timeout=300):
    t0 = time.time()
    p = subprocess.run([GITBASH, "-lc", f"python {script}"], capture_output=True, text=True,
                       timeout=timeout, cwd=str(cwd))
    return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "secs": round(time.time() - t0, 1)}


def run_pwsh(cwd: Path, script: str, timeout=300):
    t0 = time.time()
    p = subprocess.run([PWSH, "-NoProfile", "-Command", f"python {script}"], capture_output=True, text=True,
                       timeout=timeout, cwd=str(cwd))
    return {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "secs": round(time.time() - t0, 1)}


def probe_gate(res):
    if res["exit"] != 0:
        return False, f"exit={res['exit']} stderr_tail={res['stderr'][-250:]!r}"
    if FAILED_MARKER.search(res["stdout"]):
        return False, "line-anchored FAILED: marker in stdout"
    doc = None
    for line in reversed([l for l in res["stdout"].strip().splitlines() if l.strip()]):
        s = line.strip()
        if s.startswith("{"):
            try:
                doc = json.loads(s); break
            except Exception:
                continue
    if isinstance(doc, dict) and doc.get("ok") is False:
        return False, "final JSON protocol ok=false"
    return True, ""


# ---------------- main per-unit battery ----------------

def verify_unit(u, entry, sr):
    res = {"unit": u, "checks": {}, "findings": []}
    out_path = ROOT / entry["output_path"]
    ptr = entry["output_schema"]
    kind = ptr.rsplit("/", 1)[-1]
    res["checks"]["C1_exists_nonempty"] = out_path.is_file() and out_path.stat().st_size > 0
    if not res["checks"]["C1_exists_nonempty"]:
        res["findings"].append(f"C1: artifact missing/empty at {entry['output_path']}")
        res["verdict"] = "FAIL"; return res
    try:
        doc = json.loads(out_path.read_text(encoding="utf-8"))
        res["checks"]["C2_parses"] = True
    except Exception as e:
        res["checks"]["C2_parses"] = False
        res["findings"].append(f"C2: JSON parse error: {e}")
        res["verdict"] = "FAIL"; return res
    st = doc.get("state"); sent = doc.get("sentinel", "")
    c3 = st not in ("BLOCKED", "FAILED") and not (isinstance(sent, str) and sent.startswith("FAILED:"))
    res["checks"]["C3_not_self_blocked_failed"] = c3
    res["state_seen"] = st; res["sentinel_seen"] = sent[:80]
    if not c3:
        res["findings"].append(f"C3: self-declared state={st} sentinel={sent[:60]!r}")
    mpath = ROOT / "command-center" / "p2-wave" / "probes" / u / "UNIT-ARTIFACT-MANIFEST.json"
    man = None
    if not mpath.is_file():
        res["checks"]["C4_manifest_primary"] = False
        res["findings"].append("C4: UNIT-ARTIFACT-MANIFEST.json missing")
    else:
        man = json.loads(mpath.read_text(encoding="utf-8"))
        rows = man.get("artifacts", [])
        primaries = [r for r in rows if r.get("role") == "primary"]
        if len(primaries) != 1:
            res["checks"]["C4_manifest_primary"] = False
            res["findings"].append(f"C4: {len(primaries)} primary rows (need exactly 1)")
        else:
            pr = primaries[0]
            live = ROOT / pr["path"]
            if str(pr["path"]) != entry["output_path"]:
                res["checks"]["C4_manifest_primary"] = False
                res["findings"].append(f"C4: primary row path {pr['path']} != catalog output_path")
            elif not live.is_file():
                res["checks"]["C4_manifest_primary"] = False
                res["findings"].append("C4: primary row file missing on disk")
            else:
                h = lf_sha256(live)
                sz = live.stat().st_size
                ok_sha = (pr.get("sha256") == h)
                res["checks"]["C4_manifest_primary"] = ok_sha
                res["C4_detail"] = {"registered_sha": pr.get("sha256"), "live_lf_sha": h,
                                    "sha_match": ok_sha, "row_bytes": pr.get("bytes"), "on_disk_bytes": sz}
                if not ok_sha:
                    res["findings"].append("C4: primary row sha256 mismatch vs live LF-normalized bytes")
                rent = [a for a in doc.get("artifacts", []) if isinstance(a, dict) and a.get("path") == entry["output_path"]]
                if rent:
                    rb = rent[0].get("bytes")
                    if rb != sz:
                        res["checks"]["C4_manifest_primary"] = False
                        res["findings"].append(f"C4: receipt artifacts[].bytes={rb} != on-disk {sz} (schema: bytes = size on disk)")
        bad = []
        for r in man.get("artifacts", []):
            f = ROOT / r["path"]
            if not f.is_file():
                bad.append(f"{r['path']}: missing"); continue
            if r.get("present") is False:
                continue
            if lf_sha256(f) != r.get("sha256"):
                bad.append(f"{r['path']}: sha drift")
        res["checks"]["C5_all_rows_rehash"] = (len(bad) == 0)
        if bad:
            res["findings"].append("C5: " + "; ".join(bad))
    prows = [r for r in ((man or {}).get("artifacts", [])) if r.get("role") == "named-probe"]
    if not prows:
        res["checks"]["C6_probes_bash"] = False
        res["checks"]["C7_probes_pwsh"] = False
        res["findings"].append("C6: no named-probe rows in manifest")
    else:
        bres = {}
        for r in prows:
            script = Path(r["path"]).name
            b = run_bash(mpath.parent, script)
            gok, greason = probe_gate(b)
            bres[script] = {"exit": b["exit"], "gate_ok": gok, "reason": greason, "secs": b["secs"]}
        res["checks"]["C6_probes_bash"] = all(v["gate_ok"] for v in bres.values())
        if not res["checks"]["C6_probes_bash"]:
            res["findings"].append("C6: " + "; ".join(f"{k}: {v['reason']}" for k, v in bres.items() if not v["gate_ok"]))
        for r in prows:
            script = Path(r["path"]).name
            p = run_pwsh(mpath.parent, script)
            gok, greason = probe_gate(p)
            bres[script]["pwsh_exit"] = p["exit"]
            bres[script]["pwsh_gate_ok"] = gok
            bres[script]["pwsh_reason"] = greason
            if p["exit"] != bres[script]["exit"]:
                res["findings"].append(f"C7: exit-code divergence {script}: bash={bres[script]['exit']} pwsh={p['exit']}")
            if not gok:
                res["findings"].append(f"C7: pwsh gate fail {script}: {greason}")
        res["checks"]["C7_probes_pwsh"] = all(v.get("pwsh_gate_ok") for v in bres.values())
        res["probes"] = bres
    r_errs = sr.validate_artifact(doc, ptr)
    res["checks"]["C8_resolver_schema"] = (len(r_errs) == 0)
    res["C8_error_count"] = len(r_errs)
    res["C8_errors"] = r_errs[:12]
    if r_errs:
        res["findings"].append(f"C8: resolver schema errors={len(r_errs)} e.g. {r_errs[0][:160]}")
    h_errs = hand_validate(doc, kind)
    res["checks"]["C9_hand_schema"] = (len(h_errs) == 0)
    res["C9_error_count"] = len(h_errs)
    res["C9_errors"] = h_errs[:12]
    if h_errs:
        res["findings"].append(f"C9: hand-validator errors={len(h_errs)} e.g. {h_errs[0][:160]}")
    hard = ["C1_exists_nonempty", "C2_parses", "C3_not_self_blocked_failed", "C4_manifest_primary",
            "C5_all_rows_rehash", "C6_probes_bash", "C7_probes_pwsh", "C8_resolver_schema", "C9_hand_schema"]
    res["verdict"] = "PASS" if all(res["checks"].get(k) is True for k in hard) else "FAIL"
    return res


def main():
    t0 = time.time()
    sound, sr = soundness()
    print("== SOUNDNESS ==", flush=True)
    ok = True
    for kind in sound["resolver_green_on_synthetic"]:
        r = sound["resolver_green_on_synthetic"][kind]; h = sound["hand_green_on_synthetic"][kind]
        m = sound["mutations"][kind]
        print(f"  {kind}: synthetic resolver_errs={len(r)} hand_errs={len(h)} mutations_caught={m['caught']}/9", flush=True)
        if r or h or m["caught"] != 9:
            ok = False
    print("  SOUNDNESS", "OK" if ok else "BROKEN - DO NOT READ VERDICTS", flush=True)
    if not ok:
        for kind in sound["mutations"]:
            for name, det in sound["mutations"][kind]["detail"].items():
                if not det["caught"]:
                    print(f"    UNCAUGHT {kind}/{name}: resolver={det['resolver']} hand={det['hand']}", flush=True)
        sys.exit(2)
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    byid = {e["id"]: e for e in cat["work_units"]}
    results = {}
    for u in UNITS:
        r = verify_unit(u, byid[u], sr)
        results[u] = r
        print(f"[{u}] {r['verdict']} state={r.get('state_seen')!r} findings={len(r['findings'])}", flush=True)
        for f in r["findings"][:8]:
            print("    -", f[:230], flush=True)
    n_pass = sum(1 for r in results.values() if r["verdict"] == "PASS")
    print(f"== TALLY: {n_pass}/{len(UNITS)} PASS  ({round(time.time()-t0,1)}s)", flush=True)
    (OUT / "_r4_results.json").write_text(json.dumps({"soundness": sound, "results": results}, indent=1), encoding="utf-8")
    print("wrote _r4_results.json", flush=True)


if __name__ == "__main__":
    main()

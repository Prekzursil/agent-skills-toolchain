#!/usr/bin/env python3
"""w3s23 review round r3 -- fresh independent verification instrument.

Checks per unit (fail-closed, contract order):
  C1  receipt artifact exists at catalog output_path, non-empty
  C2  receipt parses as JSON
  C3  receipt not self-declared BLOCKED/FAILED (top-level terminal state)
  C4  UNIT-ARTIFACT-MANIFEST.json: primary row for output_path, sha256 (CRLF->LF
      normalized) matches live bytes, bytes field matches on-disk size
  C5  every other manifest row re-hashes to its registered sha256 (integrity)
  C6  live probe re-run by THIS reviewer in pinned Git Bash: exit 0 AND final
      JSON protocol ok != false AND no line-anchored FAILED: marker
  C7  same probes in a second Windows shell (pwsh 7); exit-code divergence = finding
  C8  output_schema via estate-canonical platform/lib/schema_resolver.validate_artifact
  C9  output_schema via hand-derived targeted validator (second independent signal
      written directly from a read of the schema defs)
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
GITBASH = r"C:\Program Files\Git\bin\bash.exe"
PWSH = "pwsh"
CATALOG = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
ESTATE_LIB = r"C:\Users\Prekzursil\source\ast-integrate\platform\lib"

UNITS = ["TST-0195","TST-0197","TST-0202","TST-0204","TST-0206","TST-0215",
         "TST-0219","TST-0221","TST-0223","TST-0227","TST-0230","TST-0233"]

ROLE_ENUM = {"primary","supporting","log","fixture","control"}
EOL_ENUM = {"LF","CRLF","MIXED","BINARY","NOT-CHECKED"}
TEST_RESULT_ENUM = {"PASS","FAIL","ERROR","SKIP","NOT-RUN"}
VERDICT_ENUM = {"CONFIRMED","REFUTED","PARTIAL","NOT-CHECKED","BLOCKED"}
PROBE_METHOD_ENUM = {"command","file-read","http","process-table","byte-compare",
                     "schema-validate","static-analysis","manual-inspection","test-run","other"}
NC_KIND_ENUM = {"mutation","malformed-input","known-broken-fixture","absent-input",
                "adversarial-payload","other"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UNITID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]{4}$")
SENT_RE = re.compile(r"^(?:(?:SUCCESS|FAILED):[A-Z][A-Z0-9]*-[0-9]{4}(?:[\s:].*)?|SENTINEL:[A-Z][A-Z0-9]*-[0-9]{4}:[A-Z0-9][A-Z0-9-]*(?:[\s].*)?)$")
SUCCESS_SENT_RE = re.compile(r"^(?:SUCCESS:|SENTINEL:)")
ISO_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$")
FAILED_MARKER = re.compile(r"^FAILED:", re.M)


def lf_sha256(p: Path) -> str:
    b = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def run_bash(cmd: str, timeout: int = 300):
    return subprocess.run([GITBASH, "-lc", cmd], capture_output=True, text=True,
                          timeout=timeout, cwd=str(ROOT))


def run_pwsh(cmd: str, timeout: int = 300):
    return subprocess.run([PWSH, "-NoProfile", "-Command", cmd], capture_output=True,
                          text=True, timeout=timeout, cwd=str(ROOT))


def last_json_object(text: str):
    for line in reversed([l for l in text.strip().splitlines() if l.strip()]):
        s = line.strip()
        if s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                continue
    return None


def probe_gate(stdout: str, stderr: str, exit_code: int):
    if exit_code != 0:
        return False, "exit=%d stderr_tail=%r" % (exit_code, stderr[-300:])
    if FAILED_MARKER.search(stdout):
        return False, "line-anchored FAILED: marker in stdout"
    doc = last_json_object(stdout)
    if doc is not None and doc.get("ok") is False:
        return False, "final JSON protocol ok=false"
    return True, ""


def hand_validate(d: dict, expected_kind: str | None = None):
    errs = []

    def a(m):
        errs.append(m)

    if d.get("schema_version") != 1:
        a("schema_version must be const 1")
    if not isinstance(d.get("unit_id"), str) or not UNITID_RE.match(d.get("unit_id", "")):
        a("unit_id pattern")
    if d.get("state") not in {"SUCCESS", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT", "SUPERSEDED", "DROPPED-BY-OWNER"}:
        a("state enum")
    if not isinstance(d.get("sentinel"), str) or len(d["sentinel"]) < 8 or not SENT_RE.match(d["sentinel"]):
        a("sentinel pattern")
    if not isinstance(d.get("spec_anchor"), str) or len(d.get("spec_anchor", "")) < 3:
        a("spec_anchor")
    mbt = d.get("min_bytes_threshold")
    if not isinstance(mbt, int) or isinstance(mbt, bool) or mbt < 1:
        a("min_bytes_threshold")
    arts = d.get("artifacts")
    if not isinstance(arts, list) or len(arts) < 1:
        a("artifacts minItems 1")
    else:
        for i, ar in enumerate(arts):
            if not isinstance(ar, dict):
                a("artifacts/%d not object" % i)
                continue
            p = ar.get("path")
            if not isinstance(p, str) or not p or "\\" in p:
                a("artifacts/%d/path" % i)
            b = ar.get("bytes")
            if not isinstance(b, int) or isinstance(b, bool) or b < 1:
                a("artifacts/%d/bytes" % i)
            if not isinstance(ar.get("sha256"), str) or not SHA_RE.match(ar.get("sha256", "")):
                a("artifacts/%d/sha256" % i)
            if ar.get("exists") is not True:
                a("artifacts/%d/exists must be true" % i)
            if "eol" in ar and ar["eol"] not in EOL_ENUM:
                a("artifacts/%d/eol enum" % i)
            if "role" in ar and ar["role"] not in ROLE_ENUM:
                a("artifacts/%d/role %r not in enum" % (i, ar["role"]))
            extra = set(ar.keys()) - {"path", "bytes", "sha256", "exists", "eol", "role"}
            if extra:
                a("artifacts/%d additionalProperties %s" % (i, sorted(extra)))
    ev = d.get("evidence")
    if not isinstance(ev, list) or len(ev) < 1:
        a("evidence minItems 1")
    else:
        for i, e in enumerate(ev):
            if not isinstance(e, dict):
                a("evidence/%d not object" % i)
                continue
            for k in ("claim", "verdict", "anchor", "probes"):
                if k not in e:
                    a("evidence/%d missing %s" % (i, k))
            if e.get("verdict") not in VERDICT_ENUM:
                a("evidence/%d/verdict enum" % i)
            if e.get("verdict") in {"CONFIRMED", "REFUTED"}:
                pr = e.get("probes") or []
                if len(pr) < 2:
                    a("evidence/%d CONFIRMED/REFUTED needs >=2 probes" % i)
                else:
                    roles = {q.get("role") for q in pr}
                    if "source" not in roles or "verifier" not in roles:
                        a("evidence/%d needs source+verifier probe pair" % i)
            for j, q in enumerate(e.get("probes") or []):
                if not isinstance(q, dict):
                    a("evidence/%d/probes/%d not object" % (i, j))
                    continue
                if q.get("role") not in {"source", "verifier"}:
                    a("evidence/%d/probes/%d/role" % (i, j))
                if q.get("method") not in PROBE_METHOD_ENUM:
                    a("evidence/%d/probes/%d/method %r" % (i, j, q.get("method")))
                for k in ("command", "raw_output", "fingerprint"):
                    if not isinstance(q.get(k), str) or not q[k]:
                        a("evidence/%d/probes/%d missing %s" % (i, j, k))
                extra = set(q.keys()) - {"role", "method", "command", "raw_output", "fingerprint", "exit_code"}
                if extra:
                    a("evidence/%d/probes/%d additionalProperties %s" % (i, j, sorted(extra)))
    rep = d.get("report")
    if not isinstance(rep, dict) or len(rep) < 1:
        a("report minProperties 1")
    else:
        k = rep.get("kind")
        if not isinstance(k, str) or not k:
            a("report.kind required non-empty")
        elif expected_kind and k != expected_kind:
            a("report.kind const %s, got %r" % (expected_kind, k))
        obs = rep.get("observations")
        if not isinstance(obs, list) or len(obs) < 1:
            a("report.observations minItems 1")
        else:
            for i, o in enumerate(obs):
                for kk in ("name", "measured", "method", "anchor"):
                    if kk not in o:
                        a("report.observations/%d missing %s" % (i, kk))
                m = o.get("measured")
                if m is not None and not isinstance(m, (str, int, float, bool)):
                    a("report.observations/%d/measured type" % i)
        ci = rep.get("control_ids")
        if not isinstance(ci, list) or len(ci) < 1 or not all(isinstance(x, str) and x for x in ci):
            a("report.control_ids minItems 1 non-empty strings")
    for k in ("timestamps", "retry"):
        if k not in d:
            a("missing required %s" % k)
    ts = d.get("timestamps")
    if isinstance(ts, dict):
        for kk in ("started_at", "ended_at"):
            v = ts.get(kk)
            if not isinstance(v, str) or not ISO_RE.match(v):
                a("timestamps/%s iso" % kk)
    if d.get("state") == "SUCCESS":
        if not isinstance(ev, list) or len(ev) < 2:
            a("SUCCESS requires evidence minItems 2")
        tests = d.get("tests")
        if not isinstance(tests, list) or len(tests) < 1:
            a("SUCCESS requires tests minItems 1")
        else:
            for i, t in enumerate(tests):
                if t.get("result") in {"FAIL", "ERROR", "SKIP", "NOT-RUN"}:
                    a("SUCCESS forbids tests/%d result %s" % (i, t.get("result")))
                if not isinstance(t.get("id"), str) or not t.get("id"):
                    a("tests/%d id" % i)
                if not isinstance(t.get("command"), str) or not t.get("command"):
                    a("tests/%d command" % i)
                if t.get("result") not in TEST_RESULT_ENUM:
                    a("tests/%d/result enum" % i)
        ncs = d.get("negative_controls")
        if not isinstance(ncs, list) or len(ncs) < 1:
            a("SUCCESS requires negative_controls minItems 1")
        else:
            for i, c in enumerate(ncs):
                if c.get("fired_on_bad_state") is False:
                    a("negative_controls/%d fired_on_bad_state=false" % i)
                if c.get("silent_on_good_state") is False:
                    a("negative_controls/%d silent_on_good_state=false" % i)
                if c.get("kind") not in NC_KIND_ENUM:
                    a("negative_controls/%d/kind %r enum" % (i, c.get("kind")))
        rv = d.get("reviewer")
        if not isinstance(rv, dict) or rv.get("verdict") != "PASS" or rv.get("independent") is not True:
            a("SUCCESS requires reviewer.verdict=PASS and reviewer.independent=true")
        mr = d.get("manifest_registration")
        if not isinstance(mr, dict) or mr.get("registered") is not True:
            a("SUCCESS requires manifest_registration.registered=true")
        dc = d.get("downstream_consumers")
        if not isinstance(dc, list) or len(dc) < 1:
            a("SUCCESS requires downstream_consumers minItems 1")
        else:
            for i, c in enumerate(dc):
                if c.get("executed") is False:
                    a("downstream_consumers/%d executed=false under SUCCESS" % i)
                if c.get("read_ok") is False:
                    a("downstream_consumers/%d read_ok=false under SUCCESS" % i)
        defs_ = d.get("defects") or []
        for i, x in enumerate(defs_):
            if x.get("severity") in {"P0", "P1"} and x.get("status") == "open":
                a("defects/%d open P0/P1 under SUCCESS" % i)
        if not SUCCESS_SENT_RE.match(d.get("sentinel", "")):
            a("SUCCESS sentinel must start SUCCESS:/SENTINEL:")
    return errs


def main() -> int:
    sys.path.insert(0, ESTATE_LIB)
    import schema_resolver
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"]}
    results = {}
    for uid in UNITS:
        ce = byid[uid]
        out_path = ROOT / ce["output_path"].replace("/", os.sep)
        r = {"unit": uid, "output_path": ce["output_path"], "checks": {},
             "findings": [], "probe_runs": {}}
        if not out_path.is_file():
            r["checks"]["C1_exists_nonempty"] = (False, "missing")
            results[uid] = r
            continue
        size = out_path.stat().st_size
        r["checks"]["C1_exists_nonempty"] = (size > 0, "size=%d" % size)
        try:
            doc = json.loads(out_path.read_text(encoding="utf-8"))
            r["checks"]["C2_parses"] = (True, "json")
        except Exception as e:
            r["checks"]["C2_parses"] = (False, str(e)[:200])
            results[uid] = r
            continue
        st = doc.get("state")
        r["checks"]["C3_not_self_blocked"] = (st not in {"BLOCKED", "FAILED"}, "state=%s" % st)
        mdir = ROOT / "command-center" / "p2-wave" / "probes" / uid
        mpath = mdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not mpath.is_file():
            r["checks"]["C4_manifest_primary_row"] = (False, "manifest missing")
            results[uid] = r
            continue
        try:
            man = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception as e:
            r["checks"]["C4_manifest_primary_row"] = (False, "manifest parse: %s" % e)
            results[uid] = r
            continue
        rows = man.get("artifacts") or []
        prim = [x for x in rows if x.get("path") == ce["output_path"]]
        if not prim:
            r["checks"]["C4_manifest_primary_row"] = (False, "no row for %s" % ce["output_path"])
        else:
            prr = prim[0]
            live = lf_sha256(out_path)
            okh = live == prr.get("sha256")
            okb = prr.get("bytes") == size
            r["checks"]["C4_manifest_primary_row"] = (
                okh and okb and prr.get("present") is True,
                "sha_live=%s sha_row=%s bytes_ok=%s present=%s" % (
                    live[:12], str(prr.get("sha256"))[:12], okb, prr.get("present")))
            r["primary_sha_live"] = live
        bad_rows = []
        for x in rows:
            if x.get("path") == ce["output_path"]:
                continue
            fp = ROOT / x["path"].replace("/", os.sep)
            if not fp.is_file():
                bad_rows.append("%s MISSING" % x["path"])
                continue
            if lf_sha256(fp) != x.get("sha256"):
                bad_rows.append("%s sha-drift" % x["path"])
            elif fp.stat().st_size != x.get("bytes"):
                bad_rows.append("%s bytes-drift" % x["path"])
        r["checks"]["C5_manifest_all_rows"] = (not bad_rows, "; ".join(bad_rows) or "all rows verified")
        if bad_rows:
            r["findings"].append("manifest non-primary row drift: " + "; ".join(bad_rows))
        probes = [x for x in rows if x.get("role") == "named-probe"]
        if not probes:
            probes = [{"path": str(p.relative_to(ROOT)).replace(os.sep, "/")}
                      for p in sorted(mdir.glob("probe*.py"))]
            r["findings"].append("manifest had no named-probe rows; fell back to probe*.py glob")
        for prr in probes:
            rel = prr["path"]
            b = run_bash('PYTHONDONTWRITEBYTECODE=1 python3 -B "%s"' % rel)
            ok, why = probe_gate(b.stdout, b.stderr, b.returncode)
            p2 = run_pwsh('$env:PYTHONDONTWRITEBYTECODE="1"; python -B "%s"; exit $LASTEXITCODE' % rel)
            ok2, why2 = probe_gate(p2.stdout, p2.stderr, p2.returncode)
            div = b.returncode != p2.returncode
            r["probe_runs"][rel] = {
                "bash_exit": b.returncode, "bash_ok": ok, "bash_why": why,
                "pwsh_exit": p2.returncode, "pwsh_ok": ok2, "pwsh_why": why2,
                "divergence": div,
                "stdout_tail": b.stdout[-500:], "stderr_tail": b.stderr[-300:],
            }
        all_ok = all(v["bash_ok"] and v["pwsh_ok"] and not v["divergence"]
                     for v in r["probe_runs"].values())
        r["checks"]["C6_probes_live_bash"] = (all_ok, "%d probes" % len(r["probe_runs"]))
        r["checks"]["C7_second_shell_agree"] = (
            not any(v["divergence"] for v in r["probe_runs"].values()),
            "; ".join("%s: bash=%d pwsh=%d" % (k, v["bash_exit"], v["pwsh_exit"])
                      for k, v in r["probe_runs"].items()))
        try:
            errs_a = schema_resolver.validate_artifact(doc, ce["output_schema"])
        except Exception as e:
            errs_a = ["resolver raised: %s" % e]
        r["checks"]["C8_schema_estate_resolver"] = (
            not errs_a, "errors=%d: %s" % (len(errs_a), " | ".join(errs_a[:6])))
        _ptr = ce.get("output_schema") if isinstance(ce.get("output_schema"), str) else ""
        if "#/$defs/" in _ptr:
            exp_kind = _ptr.rsplit("#/$defs/", 1)[-1]
        else:
            _b = _ptr.rsplit("/", 1)[-1]
            exp_kind = _b[:-len(".schema.json")] if _b.endswith(".schema.json") else (_b or None)
        errs_b = hand_validate(doc, exp_kind)
        r["checks"]["C9_schema_hand_targeted"] = (
            not errs_b, "errors=%d: %s" % (len(errs_b), " | ".join(errs_b[:8])))
        results[uid] = r
    outp = Path(__file__).parent / "_r3_results.json"
    outp.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    npass = 0
    for uid in UNITS:
        r = results[uid]
        fails = [k for k, (ok, _why) in r["checks"].items() if not ok]
        for k, v in r["probe_runs"].items():
            if not (v["bash_ok"] and v["pwsh_ok"] and not v["divergence"]):
                fails.append("probe:" + k)
        verdict = "PASS" if not fails else "FAIL"
        if verdict == "PASS":
            npass += 1
        print("%s: %s%s" % (uid, verdict, (" (" + "; ".join(fails) + ")") if fails else ""))
    print("total %d/%d PASS; results -> %s" % (npass, len(UNITS), outp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

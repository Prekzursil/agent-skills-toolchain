#!/usr/bin/env python3
"""INDEPENDENT REVIEW wave-2 shard-6 (12 units) - fresh-context adversarial verify.

Per unit (contract):
 1 catalog entry with output_path/output_schema
 2 artifact at output_path: exists, non-empty, parses, not self-declared BLOCKED/FAILED
 3 receipt core: state=SUCCESS => reviewer.verdict=PASS + independent=true; sentinel in bytes
 4 live probes re-run HERE (both exit 0)
 5 sha256(CRLF->LF) of artifact recomputed == UNIT-ARTIFACT-MANIFEST.json row (present=true)
 6 output_schema validated with jsonschema
 ALL hold -> existing PASS closure confirmed, receipt untouched. Any fail -> FAIL.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
IDS = ["BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0031",
       "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037", "BLD-0040", "BLD-0042"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
OUT = REPO / "_rev-w2s6-indep"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def digest_file(p: Path):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def env_prefix_split(cmd: str):
    env = {}
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    return env, cmd


def probe_cmds_from_return(ret, probe_dir: Path):
    cmds = []
    if isinstance(ret, dict):
        for item in (ret.get("named_probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmds.append(item["command"].strip())
        for item in (ret.get("probes") or []):
            if isinstance(item, dict):
                c = item.get("command")
                if isinstance(c, str) and c.strip() and c.strip() not in cmds:
                    cmds.append(c.strip())
    if len(cmds) >= 2:
        return cmds
    p1 = sorted(probe_dir.glob("probe1*.py"))
    p2 = sorted(probe_dir.glob("probe2*.py"))

    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        return (named or paths or [None])[0]

    a, b = pick(p1), pick(p2)
    if a and b:
        return [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {a.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {b.relative_to(REPO).as_posix()}",
        ]
    return cmds


def run_probe(uid: str, cmd: str) -> dict:
    env0, rest = env_prefix_split(cmd)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    env.update(env0)
    toks = rest.split()
    script = None
    for t in toks:
        if t.endswith(".py"):
            script = t
            break
    t0 = time.time()
    try:
        if script:
            p = subprocess.run([sys.executable, "-B", str(REPO / script)],
                               cwd=str(REPO), capture_output=True, text=True,
                               timeout=2700, env=env)
        else:
            p = subprocess.run(rest, cwd=str(REPO), capture_output=True, text=True,
                               timeout=2700, env=env, shell=True)
        rc = p.returncode
        out = ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, out = 124, "TIMEOUT"
    return {"cmd": cmd, "exit_code": rc, "secs": round(time.time() - t0, 1),
            "tail": out[-600:]}


def verify(uid: str, wu) -> dict:
    r = {"unit_id": uid, "checks": [], "probe_runs": []}

    def chk(name, ok, detail=""):
        r["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:300]})
        return bool(ok)

    if not chk("catalog-entry", wu is not None):
        r["verdict"] = "FAIL"
        return r
    out_rel = str(wu.get("output_path") or "").replace("\\", "/")
    schema_rel = str(wu.get("output_schema") or "").replace("\\", "/")
    chk("catalog-output-path-set", bool(out_rel), out_rel)
    chk("catalog-output-schema-set", bool(schema_rel), schema_rel)
    op = REPO / out_rel if out_rel else None

    ok = op is not None and op.is_file() and op.stat().st_size > 0
    chk("artifact-exists-nonempty", ok,
        f"bytes={op.stat().st_size if op and op.is_file() else 0}")
    doc = text = None
    try:
        text = op.read_text(encoding="utf-8")
        doc = json.loads(text)
        chk("artifact-parses", True)
    except Exception as e:
        chk("artifact-parses", False, repr(e))
    st = str((doc or {}).get("state") or "").upper()
    chk("not-self-blocked", st not in NOT_DELIVERING, f"state={st}")

    sent = str(wu.get("completion_sentinel") or "")
    chk("sentinel-in-artifact-bytes", (not sent) or (sent in (text or "")),
        f"sentinel={sent}")
    rev = (doc or {}).get("reviewer") or {}
    verdict = str(rev.get("verdict") or "").upper()
    indep = rev.get("independent") is True
    if st == "SUCCESS":
        chk("receipt-core:PASS+independent", verdict == "PASS" and indep,
            f"verdict={verdict} independent={rev.get('independent')}")

    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    chk("probe-dir-exists", probe_dir.is_dir())
    ret = man = None
    try:
        ret = load_json(probe_dir / "SUBAGENT-RETURN.json")
        chk("subagent-return-parses", True)
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        chk("subagent-return-not-self-blocked", rst not in NOT_DELIVERING,
            f"status={rst}")
    except Exception as e:
        chk("subagent-return-parses", False, repr(e))
    try:
        man = load_json(probe_dir / "UNIT-ARTIFACT-MANIFEST.json")
        chk("unit-manifest-parses", True)
    except Exception as e:
        chk("unit-manifest-parses", False, repr(e))

    for cmd in probe_cmds_from_return(ret if isinstance(ret, dict) else None, probe_dir):
        run = run_probe(uid, cmd)
        r["probe_runs"].append(run)
        nm = cmd.split()[-1].split("/")[-1]
        chk(f"live-probe-exit0:{nm}", run["exit_code"] == 0,
            f"rc={run['exit_code']} secs={run['secs']} tail={run['tail'][-160:]}")

    if isinstance(man, dict) and op is not None:
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        chk("manifest-has-rows", bool(rows), f"rows={len(rows)}")
        if op.is_file():
            live_sha, live_bytes = digest_file(op)
            prim = [a for a in rows
                    if str(a.get("path") or "").replace("\\", "/") == out_rel]
            chk("manifest-primary-row-path", bool(prim), out_rel)
            if prim:
                chk("manifest-primary-sha-match", prim[0].get("sha256") == live_sha,
                    f"live={live_sha} man={prim[0].get('sha256')}")
                chk("manifest-primary-present", prim[0].get("present") is True)
            mism = []
            for a in rows:
                ap = REPO / str(a.get("path") or "").replace("\\", "/")
                if not ap.is_file():
                    mism.append(f"{a.get('path')}:absent")
                    continue
                s, _b = digest_file(ap)
                if s != a.get("sha256"):
                    mism.append(f"{a.get('path')}:sha-mismatch")
            chk("manifest-all-rows-sha-match", not mism, ";".join(mism)[:300])
            r["live_sha256"] = live_sha
            r["live_bytes"] = live_bytes

    try:
        import jsonschema
        schema = load_json(REPO / schema_rel)
        jsonschema.validate(doc, schema)
        chk("output-schema-valid", True, schema_rel)
    except Exception as e:
        chk("output-schema-valid", False, repr(e)[:300])

    r["verdict"] = "PASS" if all(c["ok"] for c in r["checks"]) else "FAIL"
    return r


def main() -> int:
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    wu = {w.get("id"): w for w in (cat.get("work_units") or [])}
    results = {uid: verify(uid, wu.get(uid)) for uid in IDS}
    (OUT / "reviewer-verdicts.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    fails = [u for u, x in results.items() if x["verdict"] != "PASS"]
    for u, x in results.items():
        bad = [c for c in x["checks"] if not c["ok"]]
        pr = [(p["exit_code"], p["secs"]) for p in x["probe_runs"]]
        line = f"{u}: {x['verdict']} checks={len(x['checks'])} probes={pr}"
        if bad:
            line += f" FAILED={[c['check'] for c in bad]}"
        print(line)
    print("ALL-PASS" if not fails else "FAILURES: " + ",".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery, wave 2 shard 24 (8 TST units). Fresh re-derivation.

Stages: static | probes | pwsh | post
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard24-w2-review"
UIDS = ["TST-0145", "TST-0150", "TST-0151", "TST-0155",
        "TST-0158", "TST-0161", "TST-0162", "TST-0163"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
CORE_REQUIRED = ["schema_version", "unit_id", "state", "sentinel", "spec_anchor",
                 "min_bytes_threshold", "artifacts", "evidence", "timestamps", "retry"]
REPORT_SHAPE = {
    "predicate_report": {"required": ["kind", "reducer_id", "conditions"],
                         "kind_const": "predicate_report", "conditions_min": 12},
    "monitor_report": {"required": ["kind", "observations", "control_ids"],
                       "kind_const": "monitor_report"},
    "concurrency_report": {"required": ["kind", "observations", "control_ids"],
                           "kind_const": "concurrency_report"},
}


def jload(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, type(exc).__name__ + ": " + str(exc)


def norm_sha(p):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_map():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def static_stage():
    catmap = catalog_map()
    report = {}
    for uid in UIDS:
        cu = catmap.get(uid)
        r = {"catalog": bool(cu),
             "declared_output_schema": (cu or {}).get("output_schema"),
             "output_path": (cu or {}).get("output_path")}
        art_path = REPO / (cu or {}).get("output_path", "command-center/receipts/" + uid + ".json")
        r["artifact_exists"] = art_path.is_file()
        raw = art_path.read_bytes() if art_path.is_file() else b""
        r["artifact_bytes"] = len(raw)
        art, perr = jload(art_path)
        r["parses"] = art is not None
        if perr:
            r["parse_error"] = perr
        if isinstance(art, dict):
            r["state"] = art.get("state")
            r["state_self_blocked"] = art.get("state") in NOT_DELIVERING
            r["sentinel"] = str(art.get("sentinel", ""))
            r["sentinel_failed_marker"] = bool(re.match(r"^\s*(FAILED|BLOCKED|SEVERED|TIMEOUT):", r["sentinel"]))
            r["completion_sentinel_ok"] = art.get("completion_sentinel") == (cu or {}).get("completion_sentinel")
            rev = art.get("reviewer") or {}
            r["prior_reviewer"] = {"verdict": rev.get("verdict"), "independent": rev.get("independent"),
                                   "reviewer_id": rev.get("reviewer_id")}
            r["core_missing"] = [k for k in CORE_REQUIRED if k not in art]
            prof = ((cu or {}).get("output_schema") or "").split("#/$defs/")[-1].strip()
            shape = REPORT_SHAPE.get(prof)
            rs = {"profile": prof}
            rep = art.get("report")
            if shape is None:
                rs["evaluable"] = False
            elif not isinstance(rep, dict):
                rs["evaluable"] = True
                rs["report_present"] = False
                rs["ok"] = False
            else:
                miss = [k for k in shape["required"] if k not in rep]
                ok = (not miss) and rep.get("kind") == shape["kind_const"]
                if "conditions" in shape["required"]:
                    conds = rep.get("conditions")
                    ok = ok and isinstance(conds, list) and len(conds) >= shape["conditions_min"]
                if "observations" in shape["required"]:
                    obs = rep.get("observations")
                    ok = ok and isinstance(obs, list) and len(obs) >= 1
                if "control_ids" in shape["required"]:
                    ci = rep.get("control_ids")
                    ok = ok and isinstance(ci, list) and len(ci) >= 1
                rs.update({"report_present": True, "missing": miss, "kind": rep.get("kind"), "ok": ok})
            r["report_shape"] = rs
            defects = art.get("defects") or []
            open_hi = [d for d in defects if isinstance(d, dict)
                       and str(d.get("status", "")).lower() == "open"
                       and str(d.get("severity", "")).upper() in ("P0", "P1")]
            r["open_high_defects"] = [{"id": d.get("id"), "severity": d.get("severity"),
                                       "summary": str(d.get("summary"))[:220]} for d in open_hi]
            r["contradiction"] = (art.get("state") == "SUCCESS"
                                  and (r["sentinel_failed_marker"] or bool(open_hi)))
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man, merr = jload(man_path)
        mres = {"manifest_parses": man is not None}
        if merr:
            mres["manifest_error"] = merr
        if isinstance(man, dict):
            rows = man.get("artifacts") or []
            prim = [x for x in rows if x.get("role") == "primary" and x.get("path") == r["output_path"]]
            if prim:
                row = prim[0]
                live_sha, live_n = norm_sha(art_path)
                mres["primary_sha_match"] = (row.get("sha256") == live_sha)
                mres["primary_bytes_match"] = (row.get("bytes") in (live_n, len(raw)))
                mres["live_norm_sha256"] = live_sha
                mres["manifest_sha256"] = row.get("sha256")
            else:
                mres["primary_row_present"] = False
            drift = []
            for row in rows:
                p2 = REPO / row.get("path", "")
                if not p2.is_file():
                    drift.append({"path": row.get("path"), "drift": "MISSING"})
                    continue
                sha, n = norm_sha(p2)
                if sha != row.get("sha256"):
                    drift.append({"path": row.get("path"), "drift": "HASH",
                                  "role": row.get("role"),
                                  "manifest_bytes": row.get("bytes"), "live_bytes": n})
            mres["drifted_rows"] = drift
            mres["row_count"] = len(rows)
        r["manifest"] = mres
        report[uid] = r
    (OUT / "static_facts.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for uid, r in report.items():
        print("== " + uid)
        for k in ["artifact_exists", "artifact_bytes", "parses", "state", "state_self_blocked",
                  "sentinel_failed_marker", "completion_sentinel_ok", "core_missing"]:
            print("   " + k + ": " + str(r.get(k)))
        print("   prior_reviewer: " + json.dumps(r.get("prior_reviewer")))
        print("   report_shape: " + json.dumps(r.get("report_shape"))[:260])
        print("   open_high_defects: " + str(len(r.get("open_high_defects") or [])))
        print("   contradiction: " + str(r.get("contradiction")))
        m = r.get("manifest", {})
        print("   manifest: parses=" + str(m.get("manifest_parses"))
              + " primary_sha_match=" + str(m.get("primary_sha_match"))
              + " primary_bytes_match=" + str(m.get("primary_bytes_match")))
        for d in m.get("drifted_rows") or []:
            print("     drift: " + json.dumps(d))


PROBE_TIMEOUT = 900


def g1_probe_env():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    py_path = os.pathsep.join([
        str(REPO / "command-center" / "p2-wave" / "seed-stage"), str(REPO),
        str(REPO / "tools"), str(REPO / "tools" / "measure-guard"),
        str(REPO / "platform" / "lib"), str(REPO / "tools" / "agentspec"),
        env.get("PYTHONPATH", "")])
    env["PYTHONPATH"] = py_path
    return env


def probe_commands(uid):
    cu = catalog_map()[uid]
    art, _ = jload(REPO / cu["output_path"])
    cmds = []
    ret_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    ret, _ = jload(ret_path)
    for src in (ret, art):
        if isinstance(src, dict):
            for item in (src.get("named_probes") or []) + (src.get("probes") or []):
                if isinstance(item, dict) and isinstance(item.get("command"), str):
                    c = item["command"].strip()
                    if c and c not in cmds:
                        cmds.append(c)
    if len(cmds) >= 2:
        return cmds
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid

    def pick(glob):
        paths = sorted(pdir.glob(glob))
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        return (named or paths)[0] if paths else None

    a, b = pick("probe1*.py"), pick("probe2*.py")
    if a and b:
        return ["PYTHONDONTWRITEBYTECODE=1 python3 -B " + a.relative_to(REPO).as_posix(),
                "PYTHONDONTWRITEBYTECODE=1 python3 -B " + b.relative_to(REPO).as_posix()]
    run = pdir / "run_probes.py"
    if run.is_file():
        return ["PYTHONDONTWRITEBYTECODE=1 python3 -B " + run.relative_to(REPO).as_posix()]
    return cmds


def probes_stage():
    out = {}
    for uid in UIDS:
        res = []
        for cmd in probe_commands(uid):
            c = cmd
            env = g1_probe_env()
            while True:
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
                if m is None:
                    break
                env[m.group(1)] = m.group(2).strip('"').strip("'")
                c = c[m.end():]
            parts = c.split(" ")
            try:
                cp = subprocess.run(parts, cwd=str(REPO), env=env,
                                    capture_output=True, text=True,
                                    timeout=PROBE_TIMEOUT, shell=False)
                rc = cp.returncode
                tail = (cp.stdout or "")[-420:] + "|ERR|" + (cp.stderr or "")[-260:]
            except Exception as exc:
                rc, tail = -999, type(exc).__name__ + ": " + str(exc)
            res.append({"cmd": cmd, "rc": rc, "tail": tail[-420:]})
        out[uid] = res
        for r_ in res:
            print(uid + " rc=" + str(r_["rc"]) + " :: " + r_["cmd"][:90])
            print("    tail: " + r_["tail"][-240:])
    (OUT / "probe_facts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def pwsh_stage():
    mon = ["TST-0150", "TST-0151", "TST-0155"]
    out = {}
    for uid in mon:
        res = []
        for cmd in probe_commands(uid):
            c = cmd
            sets = []
            while True:
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
                if m is None:
                    break
                q = chr(39)
                sets.append("$env:" + m.group(1) + "=" + q + m.group(2).strip('"').strip("'") + q)
                c = c[m.end():]
            ps = "; ".join(sets + [c]) if sets else c
            full = "Set-Location '" + str(REPO) + "'; " + ps
            try:
                cp = subprocess.run(["pwsh", "-NoProfile", "-Command", full], cwd=str(REPO),
                                    capture_output=True, text=True, timeout=PROBE_TIMEOUT)
                rc = cp.returncode
                tail = (cp.stdout or "")[-380:] + "|ERR|" + (cp.stderr or "")[-220:]
            except Exception as exc:
                rc, tail = -999, type(exc).__name__ + ": " + str(exc)
            res.append({"cmd": cmd, "rc": rc, "tail": tail[-380:]})
        out[uid] = res
        for r_ in res:
            print(uid + " PWSH rc=" + str(r_["rc"]) + " :: " + r_["cmd"][:80])
            print("    tail: " + r_["tail"][-220:])
    (OUT / "pwsh_facts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def post_stage():
    catmap = catalog_map()
    out = {}
    for uid in UIDS:
        p = REPO / catmap[uid]["output_path"]
        sha, n = norm_sha(p)
        out[uid] = {"post_sha": sha, "post_bytes": n}
    prev = json.loads((OUT / "static_facts.json").read_text(encoding="utf-8"))
    for uid in UIDS:
        pre = prev[uid].get("manifest", {}).get("live_norm_sha256")
        same = (pre == out[uid]["post_sha"])
        out[uid]["unmutated_by_probes"] = same
        print(uid + " post-sha stable: " + str(same))
    (OUT / "post_facts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "static"
    {"static": static_stage, "probes": probes_stage,
     "pwsh": pwsh_stage, "post": post_stage}[stage]()

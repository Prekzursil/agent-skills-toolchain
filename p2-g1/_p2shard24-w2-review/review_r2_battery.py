#!/usr/bin/env python3
"""Fresh independent verification battery, wave 2 shard 24 (8 TST units). r2.

Stages: static | probes | post | verdict
Written fresh by the shard-24 independent reviewer; does not reuse r1 lanes.
Schema lane: real jsonschema Draft2020-12 validation against the CATALOG
output_schema ref chain (file:// refs retrieved live).
Probe lane: canonical bash form (env-prefix commands stripped into env),
g1 PYTHONPATH env, list-argv subprocess, per-probe timeout.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

from pathlib import Path
import jsonschema
from urllib.parse import unquote, urlparse

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard24-w2-review"
UIDS = ["TST-0145", "TST-0150", "TST-0151", "TST-0155",
        "TST-0158", "TST-0161", "TST-0162", "TST-0163"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
CORE_REQUIRED = ["schema_version", "unit_id", "state", "sentinel", "spec_anchor",
                 "min_bytes_threshold", "artifacts", "evidence", "timestamps", "retry"]
CAT_SCHEMA = REPO / "command-center" / "schema" / "receipt.schema.json"
PROBE_TIMEOUT = 600


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def jload(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, type(exc).__name__ + ": " + str(exc)


def catalog_map() -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def _load_doc(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_pointer(doc: dict, pointer: str):
    cur = doc
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        cur = cur[part]
    return cur


def _deref_chain(uri: str):
    u = urlparse(uri)
    path = os.path.normpath(unquote(u.path))
    if len(path) > 2 and (path[0] == chr(92) or path[0] == chr(47)) and path[2] == ":":
        path = path[1:]
    frag = unquote(u.fragment)
    doc = _load_doc(path)
    node = _resolve_pointer(doc, frag) if frag else doc
    return doc, node


def _materialize(node, doc, depth: int = 0):
    if depth > 32:
        raise RecursionError("schema ref depth exceeded")
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#"):
                return _materialize(_resolve_pointer(doc, ref[1:]), doc, depth + 1)
            if ref.startswith("file:"):
                d2, t2 = _deref_chain(ref)
                return _materialize(t2, d2, depth + 1)
            raise ValueError("unhandled $ref form: " + ref)
        return {k: _materialize(v, doc, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_materialize(v, doc, depth + 1) for v in node]
    return node


def schema_validate(art: dict, profile_ref: str):
    """profile_ref: the raw catalog output_schema string. Returns (ok, errors)."""
    frag = profile_ref.split("#", 1)[1] if "#" in profile_ref else ""
    base = profile_ref.split("#", 1)[0]
    base_path = (REPO / base).resolve() if not os.path.isabs(base) else Path(base)
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [_materialize({"$ref": base_path.as_uri() + "#" + frag}, {})],
    }
    try:
        v = jsonschema.Draft202012Validator(wrapper)
        errs = [{"path": e.json_path, "msg": str(e.message)[:300]}
                for e in sorted(v.iter_errors(art), key=lambda e: e.json_path)]
        return (not errs), errs
    except Exception as exc:
        return False, [{"path": "<validator>", "msg": type(exc).__name__ + ": " + str(exc)[:300]}]


def g1_probe_env() -> dict:
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


def probe_commands(uid: str, cu: dict | None = None):
    cu = cu or catalog_map()[uid]
    art, _ = jload(REPO / cu["output_path"])
    cmds: list[str] = []
    cat_named = (cu or {}).get("probes") or []
    for item in cat_named:
        if isinstance(item, dict) and isinstance(item.get("command"), str) and item["command"].strip():
            cmds.append(item["command"].strip())
        elif isinstance(item, str) and item.strip():
            cmds.append(item.strip())
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


def split_env_prefix(cmd: str):
    env = {}
    c = cmd
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    return env, c


def static_stage() -> dict:
    catmap = catalog_map()
    report: dict = {}
    for uid in UIDS:
        cu = catmap.get(uid)
        r: dict = {"in_catalog": bool(cu)}
        if not cu:
            r["fail_reasons"] = ["no-catalog-entry"]
            report[uid] = r
            continue
        r["output_path"] = cu.get("output_path")
        r["output_schema"] = cu.get("output_schema")
        art_path = REPO / cu["output_path"]
        r["artifact_exists"] = art_path.is_file()
        raw = art_path.read_bytes() if art_path.is_file() else b""
        r["artifact_bytes"] = len(raw)
        art, perr = jload(art_path)
        r["parses"] = art is not None
        if perr:
            r["parse_error"] = perr
        reasons: list[str] = []
        if not r["artifact_exists"]:
            reasons.append("artifact-missing:" + cu["output_path"])
        elif len(raw) == 0:
            reasons.append("artifact-empty:" + cu["output_path"])
        elif art is None:
            reasons.append("artifact-unparsable:" + str(perr))
        if isinstance(art, dict):
            r["state"] = art.get("state")
            r["self_blocked"] = art.get("state") in NOT_DELIVERING
            if r["self_blocked"]:
                reasons.append("self-declared-" + str(art.get("state")))
            r["unit_id_matches"] = art.get("unit_id") == uid
            if not r["unit_id_matches"]:
                reasons.append("unit_id-mismatch:" + str(art.get("unit_id")))
            r["core_missing"] = [k for k in CORE_REQUIRED if k not in art]
            rev = art.get("reviewer") or {}
            r["prior_reviewer"] = {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent")}
            r["receipt_core_ok"] = (rev.get("verdict") == "PASS" and rev.get("independent") is True)
            if art.get("state") == "SUCCESS" and not r["receipt_core_ok"]:
                reasons.append("receipt_core-SUCCESS-without-PASS-independent-reviewer")
            ok, errs = schema_validate(art, cu.get("output_schema") or "")
            r["schema_ok"] = ok
            r["schema_errors"] = errs[:12]
            if not ok:
                reasons.append("output-schema-invalid:" + json.dumps(errs[:3])[:400])
            sent = str(art.get("sentinel", ""))
            r["sentinel"] = sent[:200]
            r["sentinel_failed_family"] = bool(re.match(r"^\s*(FAILED|BLOCKED|SEVERED|TIMEOUT):", sent))
            r["sentinel_names_unit"] = (uid in sent)
            r["sentinel_schema_pattern_ok"] = bool(re.match(
                r"^(?:(?:SUCCESS|FAILED):[A-Z][A-Z0-9]*-[0-9]{4}(?:[\s:].*)?|SENTINEL:[A-Z][A-Z0-9]*-[0-9]{4}:[A-Z0-9][A-Z0-9-]*(?:[\s].*)?)$", sent))
            defects = art.get("defects") or []
            open_hi = [d for d in defects if isinstance(d, dict)
                       and str(d.get("status", "")).lower() == "open"
                       and str(d.get("severity", "")).upper() in ("P0", "P1")]
            r["open_high_defects"] = [{"id": d.get("id"), "severity": d.get("severity")} for d in open_hi]
            r["catalog_completion_sentinel"] = cu.get("completion_sentinel")
            r["completion_sentinel_match"] = (
                art.get("completion_sentinel") == cu.get("completion_sentinel")
                or str(art.get("sentinel", "")).startswith("SUCCESS:" + uid + " ")
                or str(art.get("sentinel", "")) == "SUCCESS:" + uid)
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man, merr = jload(man_path)
        mres: dict = {"manifest_parses": man is not None, "manifest_path": str(man_path)}
        if merr:
            mres["manifest_error"] = merr
        if isinstance(man, dict):
            rows = man.get("artifacts") or []
            mres["row_count"] = len(rows)
            prim = [x for x in rows if x.get("role") == "primary" and x.get("path") == cu["output_path"]]
            if prim:
                row = prim[0]
                live_sha, live_n = norm_sha(art_path)
                mres["primary_sha_match"] = (row.get("sha256") == live_sha)
                mres["primary_bytes_match"] = (row.get("bytes") == live_n)
                mres["live_norm_sha256"] = live_sha
                mres["live_norm_bytes"] = live_n
                mres["manifest_sha256"] = row.get("sha256")
                if not mres["primary_sha_match"]:
                    reasons.append("manifest-primary-sha-mismatch")
                if not mres["primary_bytes_match"]:
                    reasons.append("manifest-primary-bytes-mismatch")
            else:
                mres["primary_row_present"] = False
                reasons.append("manifest-missing-primary-row-for-output_path")
            drift = []
            for row in rows:
                p2 = REPO / str(row.get("path", ""))
                if not p2.is_file():
                    drift.append({"path": row.get("path"), "drift": "MISSING", "role": row.get("role")})
                    continue
                sha, n = norm_sha(p2)
                if sha != row.get("sha256"):
                    drift.append({"path": row.get("path"), "drift": "HASH", "role": row.get("role"),
                                  "manifest_bytes": row.get("bytes"), "live_bytes": n})
            mres["drifted_supporting_rows"] = [d for d in drift if d.get("role") != "primary"]
            mres["drifted_primary_rows"] = [d for d in drift if d.get("role") == "primary"]
        else:
            reasons.append("manifest-unparsable:" + str(merr))
        r["manifest"] = mres
        r["probe_commands"] = probe_commands(uid, cu)
        r["fail_reasons_static"] = reasons
        report[uid] = r
    (OUT / "r2_static_facts.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for uid, r in report.items():
        print("==", uid, "| schema_ok:", r.get("schema_ok"),
              "| manifest_sha_match:", r.get("manifest", {}).get("primary_sha_match"),
              "| static_reasons:", r.get("fail_reasons_static"))
        for e in (r.get("schema_errors") or [])[:4]:
            print("   schema_err:", e["path"], "::", e["msg"][:180])
    return report


def probes_stage() -> dict:
    catmap = catalog_map()
    out: dict = {}
    for uid in UIDS:
        res = []
        for cmd in probe_commands(uid, catmap.get(uid)):
            pre, c = split_env_prefix(cmd)
            parts = c.split(" ")
            env = g1_probe_env()
            env.update(pre)
            try:
                cp = subprocess.run(parts, cwd=str(REPO), env=env,
                                    capture_output=True, text=True, timeout=PROBE_TIMEOUT,
                                    shell=False)
                rc = cp.returncode
                tail = (cp.stdout or "")[-420:] + "|ERR|" + (cp.stderr or "")[-300:]
            except subprocess.TimeoutExpired:
                rc, tail = -998, "TIMEOUT after %ss" % PROBE_TIMEOUT
            except Exception as exc:
                rc, tail = -999, type(exc).__name__ + ": " + str(exc)
            posix_req = "requires POSIX" in tail
            res.append({"cmd": cmd, "rc": rc, "posix_required": posix_req, "tail": tail[-420:]})
            print(uid, "rc=%s" % rc, "posix=%s" % posix_req, "::", cmd[-70:])
            print("    tail:", tail[-240:].replace("\n", " | ")[:240])
        out[uid] = res
    (OUT / "r2_probe_facts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def post_stage() -> dict:
    catmap = catalog_map()
    static = json.loads((OUT / "r2_static_facts.json").read_text(encoding="utf-8"))
    out: dict = {}
    for uid in UIDS:
        p = REPO / catmap[uid]["output_path"]
        sha, n = norm_sha(p)
        pre = static.get(uid, {}).get("manifest", {}).get("live_norm_sha256")
        out[uid] = {"post_sha": sha, "post_bytes": n, "unmutated_by_probes": (pre == sha)}
        print(uid, "post-sha stable:", pre == sha)
    (OUT / "r2_post_facts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def verdict_stage() -> dict:
    static = json.loads((OUT / "r2_static_facts.json").read_text(encoding="utf-8"))
    probes = json.loads((OUT / "r2_probe_facts.json").read_text(encoding="utf-8"))
    post = json.loads((OUT / "r2_post_facts.json").read_text(encoding="utf-8"))
    report = []
    for uid in UIDS:
        s = static[uid]
        reasons = list(s.get("fail_reasons_static") or [])
        details = {"static_fail_reasons": reasons}
        probe_list = probes.get(uid) or []
        for pr in probe_list:
            if pr["rc"] != 0:
                tag = "posix-required-on-win32" if pr.get("posix_required") else "probe-nonzero-exit"
                reasons.append(tag + ":" + pr["cmd"].split("/")[-1] + ":rc=%s" % pr["rc"])
        details["probe_results"] = [
            {"cmd": pr["cmd"], "rc": pr["rc"], "posix_required": pr.get("posix_required", False)}
            for pr in probe_list]
        if not post.get(uid, {}).get("unmutated_by_probes", True):
            reasons.append("artifact-mutated-by-probes")
        verdict = "PASS" if not reasons else "FAIL"
        report.append({"unit_id": uid, "verdict": verdict,
                       "fail_reasons": reasons, "details": details})
    (OUT / "r2_review_report.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    for u in report:
        print(u["unit_id"], u["verdict"])
        for fr in u["fail_reasons"]:
            print("   -", fr[:200])
    return report


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "static"
    {"static": static_stage, "probes": probes_stage, "post": post_stage,
     "verdict": verdict_stage}[stage]()

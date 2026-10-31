#!/usr/bin/env python3
"""Independent reviewer battery - wave 3 shard 19 (12 units).

Re-verifies each unit from scratch: catalog entry, artifact at output_path,
closure block, output_schema (local physical control plane), EVERY manifest
row (CRLF-normalized sha256), SUBAGENT-RETURN sanity, and re-runs every live
probe command. Coded independently of _measure_one_delivered.py; run_cmd env
handling mirrors the repo convention so named-probe commands execute verbatim.
Output: results JSON + one SUCCESS/FAILED line per unit on stdout.
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

REPO = Path("C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
PHYS_SCHEMA = REPO / "platform/schema/artifact-class-profiles.schema.json"
PROBES = REPO / "command-center/p2-wave/probes"
OUT_DIR = REPO / "_reviewer-w3s19"
UNITS = ["TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091",
         "TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113",
         "TST-0116", "TST-0124"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from jsonschema import Draft202012Validator  # noqa: E402
from referencing import Registry, Resource  # noqa: E402
from referencing.jsonschema import DRAFT202012  # noqa: E402


def sha_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return exc


def run_cmd(cmd: str):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    py_path = os.pathsep.join([
        str(REPO / "command-center/p2-wave/seed-stage"),
        str(REPO), str(REPO / "tools"), str(REPO / "tools/measure-guard"),
        str(REPO / "platform/lib"), str(REPO / "tools/agentspec"),
        env.get("PYTHONPATH", ""),
    ])
    env["PYTHONPATH"] = py_path
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center/p2-wave/seed-stage/g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = sys.executable.replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=2700, env=env)
        rc, out = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, out = 124, "TIMEOUT"
    return rc, out[-1500:], time.monotonic() - t0


def probe_commands(uid: str, ret, probe_dir: Path):
    cmds = []
    notes = []
    pc = probe_dir / "PROBE-CMDS.json"
    if pc.is_file():
        d = load_json(pc)
        if isinstance(d, list):
            cmds.extend(str(c).strip() for c in d if str(c).strip())
            notes.append(f"PROBE-CMDS.json: {len(cmds)}")
    if isinstance(ret, dict):
        n = 0
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
                    n += 1
        if n:
            notes.append(f"SUBAGENT-RETURN extra: {n}")
    if not cmds:
        found = []
        for g in ("probe1*.py", "probe2*.py"):
            hits = sorted(probe_dir.glob(g))
            named = [h for h in hits if h.name not in {"probe1.py", "probe2.py"}]
            found.append(named[0] if named else (hits[0] if hits else None))
        if found[0] and found[1]:
            cmds = [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {h.relative_to(REPO).as_posix()}" for h in found]
            notes.append("glob fallback")
    run_py = probe_dir / "run_probes.py"
    if run_py.is_file() and not cmds:
        cmds = [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {run_py.relative_to(REPO).as_posix()}"]
        notes.append("run_probes.py")
    return cmds, notes


def probe_sanity(uid: str, cmds, out_rel):
    """Vacuousness scan: every probe file must reference its unit or read the artifact."""
    problems = []
    for c in cmds:
        m = re.search(r"(command-center/p2-wave/probes/[^\"']+/probe[^\"']*\.py)", c)
        if not m:
            problems.append(f"probe-cmd-unrecognized: {c[:90]}")
            continue
        pf = REPO / m.group(1).replace("/", os.sep)
        if not pf.is_file():
            problems.append(f"probe-file-absent: {m.group(1)}")
            continue
        try:
            src = pf.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            problems.append(f"probe-unreadable: {exc}")
            continue
        refs_uid = uid in src
        art_name = out_rel.split("/")[-1]
        refs_art = art_name in src or "output_path" in src or "receipt" in src.lower()
        if len(src.splitlines()) < 8:
            problems.append(f"probe-suspiciously-thin ({len(src.splitlines())} lines): {pf.name}")
        if not (refs_uid or refs_art):
            problems.append(f"probe-references-neither-unit-nor-artifact: {pf.name}")
    return problems


_PHYS_CACHE = None
_RECEIPT_SCHEMA = REPO / "platform/schema/receipt.schema.json"


def physical_defs():
    global _PHYS_CACHE
    if _PHYS_CACHE is None:
        _PHYS_CACHE = load_json(PHYS_SCHEMA)
        if isinstance(_PHYS_CACHE, Exception):
            raise _PHYS_CACHE
    return _PHYS_CACHE


def schema_registry():
    """Register the LOCAL p2-g1 copies of the physical control-plane schemas
    under their canonical (absolute) $ids, so the shim chain resolves inside
    this worktree instead of reaching into ~/source/ast-integrate."""
    phys = physical_defs()
    receipt = load_json(_RECEIPT_SCHEMA)
    if isinstance(receipt, Exception):
        raise receipt
    registry = Registry()
    for doc in (phys, receipt):
        registry = registry.with_resource(
            doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
    return registry, phys


def schema_errors(receipt, shim_path: Path):
    shim = load_json(shim_path)
    if isinstance(shim, Exception):
        return [f"schema-shim-unreadable: {shim}"]
    ref = str(shim.get("$ref") or "")
    m = re.search(r"#/\$defs/([A-Za-z0-9_-]+)$", ref)
    xdef = str(shim.get("x-physical-definition") or "")
    mx = re.search(r"#/\$defs/([A-Za-z0-9_-]+)$", xdef)
    if not m:
        return [f"schema-shim-ref-unparsed: {ref[:120]}"]
    frag = m.group(1)
    if mx and mx.group(1) != frag:
        return [f"schema-shim-drift: $ref={frag} x-physical-definition={mx.group(1)}"]
    try:
        registry, phys = schema_registry()
    except Exception as exc:  # noqa: BLE001
        return [f"schema-registry-build-failed: {exc}"]
    if frag not in (phys.get("$defs") or {}):
        return [f"schema-fragment-absent-in-local-physical: {frag}"]
    validator = Draft202012Validator(
        {"$ref": phys["$id"] + "#/$defs/" + frag}, registry=registry)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in validator.iter_errors(receipt)]


def verify(uid: str) -> dict:
    res = {"unit": uid, "checks": {}, "probe_runs": [], "fail_reasons": []}

    def bad(reason: str):
        res["fail_reasons"].append(reason)

    # 1 catalog
    cat = load_json(CATALOG)
    unit = None
    if isinstance(cat, dict):
        for u in cat.get("work_units") or []:
            if isinstance(u, dict) and u.get("id") == uid:
                unit = u
                break
    if unit is None:
        bad("catalog-entry-absent")
        res["checks"]["catalog"] = False
        res["verdict"] = "FAIL"
        return res
    res["checks"]["catalog"] = True
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    shim_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    sentinel = str(unit.get("completion_sentinel") or "")
    res["output_path"] = out_rel
    res["output_schema"] = shim_rel

    # 2 artifact
    out = REPO / out_rel
    doc = None
    if not out.is_file():
        bad(f"artifact-absent: {out_rel}")
    elif out.stat().st_size <= 0:
        bad(f"artifact-empty: {out_rel}")
    if out.is_file():
        try:
            text = out.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            bad(f"artifact-not-utf8: {exc}")
            text = ""
        doc = load_json(out)
        if isinstance(doc, Exception):
            bad(f"artifact-unparseable: {type(doc).__name__}: {doc}")
            doc = None
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in NOT_DELIVERING:
                bad(f"artifact-self-declared: {st}")
            if sentinel and sentinel not in text:
                bad("completion-sentinel-absent-in-artifact")
            res["checks"]["artifact"] = True
        else:
            res["checks"]["artifact"] = False
    else:
        res["checks"]["artifact"] = False

    # 3 closure block
    if isinstance(doc, dict):
        rid = doc.get("id") or doc.get("unit_id")
        if rid != uid:
            bad(f"receipt-identity-mismatch: {rid}")
        rv = doc.get("reviewer") or {}
        if not isinstance(rv, dict) or rv.get("verdict") != "PASS":
            bad(f"reviewer-verdict-not-PASS: {rv.get('verdict')!r}")
        if not isinstance(rv, dict) or rv.get("independent") is not True:
            bad(f"reviewer-independent-not-true: {rv.get('independent')!r}")
        if str(doc.get("state") or "").upper() != "SUCCESS":
            bad(f"receipt-state-not-SUCCESS: {doc.get('state')!r}")
        ev = doc.get("evidence")
        if not isinstance(ev, list) or not ev:
            if isinstance(ev, dict) and ev:
                bad("evidence-not-array-form (schema requires array of {claim,verdict,anchor,probes,confidence})")
            else:
                bad("evidence-absent-or-empty")
        elif not all(isinstance(e, dict) and e.get("claim") for e in ev):
            bad("evidence-entries-missing-claim")
        res["checks"]["closure"] = True
    else:
        res["checks"]["closure"] = False

    # 4 schema (local physical control plane)
    if isinstance(doc, dict):
        errs = schema_errors(doc, REPO / shim_rel)
        if errs:
            for e in errs[:6]:
                bad(f"schema: {e}")
            res["schema_error_count"] = len(errs)
        res["checks"]["schema"] = not errs

    # 5 manifest: EVERY row must match live bytes
    man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(man_path) if man_path.is_file() else None
    if not isinstance(man, dict):
        bad("manifest-absent-or-unparseable")
        res["checks"]["manifest"] = False
    else:
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        if not rows:
            bad("manifest-unit-rows-absent")
            res["checks"]["manifest"] = False
        else:
            for row in rows:
                rp = REPO / str(row.get("path") or "").replace("\\", "/")
                if not rp.is_file():
                    bad(f"manifest-row-file-absent: {row.get('path')}")
                    continue
                if row.get("present") is not True:
                    bad(f"manifest-row-present-not-true: {row.get('path')}")
                live = sha_norm(rp)
                if live != str(row.get("sha256")):
                    bad(f"manifest-sha-mismatch: {row.get('path')} row={str(row.get('sha256'))[:12]} live={live[:12]}")
                lb_norm = len(rp.read_bytes().replace(b"\r\n", b"\n"))
                if isinstance(row.get("bytes"), int) and row["bytes"] != lb_norm:
                    bad(f"manifest-bytes-mismatch: {row.get('path')} row={row['bytes']} live_lf_normalized={lb_norm}")
            res["manifest_row_count"] = len(rows)
            res["checks"]["manifest"] = not res["fail_reasons"]

    # 6 SUBAGENT-RETURN
    ret_path = PROBES / uid / "SUBAGENT-RETURN.json"
    ret = load_json(ret_path) if ret_path.is_file() else None
    if not isinstance(ret, dict):
        bad("subagent-return-absent-or-unparseable")
        res["checks"]["subagent_return"] = False
    else:
        st = str(ret.get("status") or ret.get("state") or "").upper()
        if st in NOT_DELIVERING:
            bad(f"subagent-return-status: {st}")
        res["checks"]["subagent_return"] = True

    # 7 probes: re-run everything myself
    if isinstance(ret, dict) or (PROBES / uid).is_dir():
        cmds, notes = probe_commands(uid, ret, PROBES / uid)
        res["probe_source_notes"] = notes
        if not cmds:
            bad("named-probes-absent")
        else:
            for p in probe_sanity(uid, cmds, out_rel):
                bad(f"probe-sanity: {p}")
            for c in cmds:
                rc, tail, dt = run_cmd(c)
                res["probe_runs"].append({"cmd": c, "rc": rc, "secs": round(dt, 1)})
                if rc != 0:
                    bad(f"probe-exit-{rc}: {c[:110]} | tail: {tail[-220:]}")
            res["checks"]["probes_rerun_exit0"] = bool(res["probe_runs"]) and \
                all(r["rc"] == 0 for r in res["probe_runs"])

    res["verdict"] = "PASS" if not res["fail_reasons"] else "FAIL"
    return res


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    results = []
    for uid in UNITS:
        r = verify(uid)
        results.append(r)
        if r["verdict"] == "PASS":
            print(f"SUCCESS:review {uid}", flush=True)
        else:
            print(f"FAILED:review {uid} :: {r['fail_reasons']}", flush=True)
        (OUT_DIR / f"verify_{uid}.json").write_text(
            json.dumps(r, indent=1), encoding="utf-8")
    (OUT_DIR / "results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    npass = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"SUMMARY {npass}/{len(results)} PASS")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

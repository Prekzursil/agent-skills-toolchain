#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-3 shard-18 (12 units) - FINAL verification battery.

Written fresh by the wave-3 shard-18 reviewer agent (I did not build these
units; my PASS is what closes them). Per unit, mechanically verifies exactly
the checks the unit contract enumerates:

  A  artifact at catalog output_path: exists, non-empty, parses as JSON,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT (a receipt BLOCKED
     with failure.classification ["reviewer-absent"] is the expected
     builder terminal and is closable by this reviewer)
  F  live probes re-run HERE exactly as recorded: exit 0 required; the
     probes emit structured JSON verdicts, so the terminal-state signal
     is JSON pass==true AND red==[] (literal SUCCESS:/FAILED: text
     markers are honoured when present but are not the probes' design);
  D  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row (path ==
     output_path) present=true, sha256 + bytes match a live recompute
     over CRLF-normalized bytes; every other row digest-matched;
  C  artifact validates against the catalog output_schema via the repo's
     own platform/lib/schema_resolver.py (contract check 4);
  +  receipt terminal-state sanity: SUCCESS receipts must carry
     reviewer.verdict=PASS + independent=true; BLOCKED receipts are
     closable only with failure.classification ["reviewer-absent"].

Closure rule (fail-closed):
  - ALL contract checks hold on an already-SUCCESS unit with a valid
    PASS/independent closure => CONFIRMED, receipt untouched;
  - ALL contract checks hold on a BLOCKED/reviewer-absent unit => this
    reviewer stamps the closure (PASS/independent/SUCCESS);
  - ANY failed check => verdict FAIL with the precise failing check,
    receipt UNCHANGED.

Results go to _rev-w3s18/verify_out.json. The receipt-side schema
violations found by this battery are reported per unit as the precise
failing check; per the contract, "validate output_schema" is a closure
gate, so units whose receipt/artifact violates the declared schema are
FAIL and their receipts stay untouched.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT_JSON = REPO / "_rev-w3s18" / "verify_out.json"
REVIEWER_ID = "w3s18-independent-reviewer"
SELF_BAD = {"FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600
STAMP_TS = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
UNITS = ["RES-0179", "RES-0180", "RES-0182", "TST-0018", "TST-0028", "TST-0032",
         "TST-0057", "TST-0060", "TST-0066", "TST-0067", "TST-0068", "TST-0070"]


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load schema_resolver")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_core_validator() -> Draft202012Validator:
    sch = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8")
    )
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def probe_cmds(uid: str, pdir: Path) -> list[str]:
    cmds: list[str] = []
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = {}
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if len(cmds) < 2:
        for name in sorted(p.name for p in pdir.glob("probe[0-9]*.py")):
            c = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{name}"
            if c not in cmds:
                cmds.append(c)
    return cmds


def winify(cmd: str, env: dict) -> str:
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            return cmd
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]


def run_cmd(cmd: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # plain env: a PYTHONPATH carrying the repo root shadows the stdlib
    # `platform` module with the repo's platform/ namespace dir and crashes
    # imports inside probes (harness hazard, not a unit defect).
    env.pop("PYTHONPATH", None)
    env.pop("AST_INTEGRATE_ROOT", None)
    cmd = winify(cmd, env)
    parts = cmd.split(" ")
    if len(parts) > 2 and parts[1] == "-B":
        argv = [sys.executable, "-B"] + parts[2:]
    else:
        argv = [sys.executable] + parts[1:]
    cp = subprocess.run(
        argv, cwd=str(REPO), env=env, capture_output=True, text=True,
        timeout=PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
    )
    return cp.returncode, cp.stdout or "", cp.stderr or ""


def probe_verdict(rc: int, so: str, se: str) -> tuple[bool, str]:
    """Terminal-state signal for one live probe run.

    Accepts (a) a literal SUCCESS: marker (optionally trailing after a JSON
    document, e.g. `json\\nSUCCESS:ID-probeN ...`), or (b) a structured-JSON
    verdict with pass==true and red empty (the TST probes' design). Fails on
    rc!=0, FAILED: markers, pass!=true, or non-empty red[].
    """
    if rc != 0:
        return False, f"rc={rc}"
    if "FAILED:" in so or "FAILED:" in se:
        return False, "FAILED-marker"
    marker = "SUCCESS:" in so
    tail = so.strip()
    doc = None
    if tail.startswith("{"):
        try:
            doc = json.loads(tail)
        except json.JSONDecodeError as e:
            if e.pos and tail[: e.pos].rstrip().endswith("}"):
                try:
                    doc = json.loads(tail[: e.pos])
                except Exception:
                    doc = None
    if isinstance(doc, dict):
        # an EXPLICIT false verdict or non-empty red[] contradicts any marker
        if doc.get("pass") is False:
            return False, f"probe-pass=false"
        if doc.get("red") not in (None, []):
            return False, f"red={json.dumps(doc.get('red'))[:160]}"
    if marker:
        if isinstance(doc, dict) and doc.get("pass") is True:
            return True, "json-pass+SUCCESS-marker"
        return True, "SUCCESS-marker"
    if isinstance(doc, dict):
        if doc.get("pass") is True:
            return True, "json-pass (structured verdict; no SUCCESS: text marker by design)"
        return False, "no SUCCESS: marker and no pass=true in structured output"
    return False, "no SUCCESS: marker and no structured json verdict"


def verify_unit(uid: str, cu: dict, core_v, resolver) -> dict:
    rep: dict = {"fails": [], "notes": [], "probe_runs": []}
    out_rel = str(cu.get("output_path") or "").replace("\\", "/")
    rep["out_rel"] = out_rel
    out = REPO / out_rel
    is_tst = uid.startswith("TST")
    rcp = out if is_tst else REPO / "command-center" / "receipts" / f"{uid}.json"
    rep["receipt_path"] = str(rcp.relative_to(REPO)).replace("\\", "/")

    # ---------- A: artifact ----------
    if not out.is_file() or out.stat().st_size == 0:
        rep["fails"].append(f"artifact-absent-or-empty:{out_rel}")
        return rep
    try:
        art = json.loads(out.read_text(encoding="utf-8"))
    except Exception as exc:
        rep["fails"].append(f"artifact-unparseable:{type(exc).__name__}")
        return rep
    st = str(art.get("state") or "").upper() if isinstance(art, dict) else ""
    if st in SELF_BAD:
        rep["fails"].append(f"artifact-self-declared:{st}")
    rep["artifact_state"] = st or "<non-dict>"

    # ---------- receipt read ----------
    if not rcp.is_file() or rcp.stat().st_size == 0:
        rep["fails"].append(f"receipt-absent-or-empty:{rcp.name}")
        return rep
    receipt_raw = rcp.read_text(encoding="utf-8")
    try:
        receipt = json.loads(receipt_raw)
    except Exception as exc:
        rep["fails"].append(f"receipt-unparseable:{type(exc).__name__}")
        return rep
    rst = str(receipt.get("state") or "").upper()
    fcls = [str(x) for x in ((receipt.get("failure") or {}).get("classification") or [])]
    rep["receipt_state"] = rst
    rep["fcls"] = fcls
    rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
    if rst == "SUCCESS":
        rep["confirm_only"] = True
        if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
            rep["fails"].append(
                f"success-without-valid-closure verdict={rev.get('verdict')!r} independent={rev.get('independent')!r}")
    elif rst == "BLOCKED" and "reviewer-absent" in fcls and not is_tst:
        rep["closable"] = True
        rep["notes"].append("receipt=BLOCKED/reviewer-absent (closable by this reviewer)")
    else:
        rep["fails"].append(f"receipt-state-unexpected:{rst} fcls={fcls}")

    # ---------- E: catalog sentinel verbatim in receipt text ----------
    sentinel = str(cu.get("completion_sentinel") or "")
    if sentinel and sentinel not in receipt_raw:
        rep["fails"].append(f"sentinel-absent:{sentinel}")

    # ---------- C: artifact vs catalog output_schema ----------
    osch = str(cu.get("output_schema") or "")
    try:
        errs = resolver.validate_artifact(art, osch)
    except Exception as exc:
        errs = [f"<resolver-error> {type(exc).__name__}: {exc}"[:220]]
    rep["output_schema_violations"] = len(errs)
    if errs:
        rep["fails"].append(f"output-schema-violations:{len(errs)} first:{errs[0][:190]}")
        rep["schema_errors_head"] = errs[:12]
    else:
        rep["notes"].append(f"output_schema OK ({osch.rsplit('/', 1)[-1]})")

    # ---------- C2: receipt vs receipt_core (informational for report) ----------
    if core_v is not None:
        errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        rep["core_errors"] = len(errs)
        if errs:
            for e in errs[:6]:
                where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                rep["notes"].append(f"core:{where}::{e.message[:170]}")
            if len(errs) > 6:
                rep["notes"].append(f"core:...{len(errs) - 6} more")
    else:
        rep["notes"].append("jsonschema-unavailable (C2 skipped)")

    # ---------- D: manifest digest-match ----------
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    named_probe_rows: list[str] = []
    if not man_path.is_file():
        rep["fails"].append("manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            man = None
            rep["fails"].append(f"manifest-unparseable:{type(exc).__name__}")
        if isinstance(man, dict):
            rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
            prim = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
            if not prim:
                rep["fails"].append("manifest-primary-row-absent")
            else:
                p0 = prim[0]
                live_sha, live_n = digest(out)
                if p0.get("present") is not True:
                    rep["fails"].append("manifest-primary-present!=true")
                if str(p0.get("sha256") or "") != live_sha:
                    rep["fails"].append(
                        f"manifest-primary-sha-mismatch man={str(p0.get('sha256'))[:12]} live={live_sha[:12]}")
                if p0.get("bytes") != live_n:
                    rep["fails"].append(f"manifest-primary-bytes man={p0.get('bytes')} live={live_n}")
                rep["sha256_live"] = live_sha
                rep["bytes_live"] = live_n
            for a in rows:
                rel = str(a.get("path") or "").replace("\\", "/")
                if rel == out_rel:
                    continue
                if a.get("role") == "named-probe" and rel.endswith(".py"):
                    named_probe_rows.append(rel)
                fpp = REPO / rel
                if not fpp.is_file():
                    rep["fails"].append(f"manifest-row-absent:{rel}")
                    continue
                s2, n2 = digest(fpp)
                if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
                    rep["fails"].append(
                        f"manifest-row-digest:{rel} man={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}")
            rep["notes"].append(f"manifest-rows={len(rows)}")

    # ---------- F: live probes, run AS RECORDED ----------
    cmds = probe_cmds(uid, REPO / "command-center" / "p2-wave" / "probes" / uid)
    for r in named_probe_rows:
        c = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {r}"
        if not any(r in c0 for c0 in cmds):
            cmds.append(c)
    if not cmds:
        rep["fails"].append("no-live-probes-found")
    else:
        ok_runs = 0
        for cmd in cmds:
            t0 = time.time()
            try:
                rc, so, se = run_cmd(cmd)
            except subprocess.TimeoutExpired:
                rc, so, se = -1, "", f"TIMEOUT after {PROBE_TIMEOUT_S}s"
            ok, why = probe_verdict(rc, so, se)
            if not ok:
                rep["fails"].append(f"probe:{Path(cmd.split()[-1]).name} {why}")
            else:
                ok_runs += 1
                rep["notes"].append(f"probe-ok:{Path(cmd.split()[-1]).name} ({why})")
            rep["probe_runs"].append({
                "command": cmd, "rc": rc, "verdict": ok, "why": why,
                "seconds": round(time.time() - t0, 1),
                "stdout_head": so[:300],
                "stdout_tail": so[-1400:],
                "stderr_tail": se[-400:],
            })
        rep["notes"].append(f"probes-ok={ok_runs}/{len(cmds)}")

    return rep


def main() -> int:
    entries = json.loads((REPO / "_rev-w3s18-entries.json").read_text(encoding="utf-8"))
    core_v = load_core_validator()
    resolver = load_resolver()
    results: dict[str, dict] = {}
    for uid in UNITS:
        cu = entries.get(uid)
        if cu is None:
            results[uid] = {"fails": ["catalog-entry-absent"], "notes": []}
            continue
        t0 = time.time()
        rep = verify_unit(uid, cu, core_v, resolver)
        rep["seconds"] = round(time.time() - t0, 1)
        results[uid] = rep
        print(f"[battery] {uid}: fails={len(rep['fails'])} "
              f"receipt={rep.get('receipt_state')} probes={rep.get('probe_runs') and sum(1 for p in rep['probe_runs'] if p['verdict'])}ok",
              flush=True)

    OUT_JSON.write_text(
        json.dumps({"generated": STAMP_TS, "reviewer": REVIEWER_ID,
                    "units": UNITS, "results": results},
                   indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    n_pass = sum(1 for r in results.values() if not r.get("fails"))
    print(f"BATTERY: {n_pass}/{len(UNITS)} fully-clean; out={OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

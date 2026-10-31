#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-3 shard-18 (12 units) - r2, read-only verification.

This reviewer did not build these units. Every check below is re-derived from
live bytes THIS run. Probes are executed through the same transport the
program's own DELIVERED instrument uses (env-prefix parsing + g1_python wrapper
on Windows), but the ACCEPTANCE DECISIONS are this reviewer's.

Units:
  RES-0179 RES-0180 RES-0182
  TST-0018 TST-0028 TST-0032 TST-0057 TST-0060
  TST-0066 TST-0067 TST-0068 TST-0070

Checks per unit:
  A  catalog entry with output_path / output_schema / completion_sentinel
  B  artifact at output_path: exists, non-empty, parses, not self-blocked
  C  live probe re-run (SUBAGENT-RETURN named probes + probe[0-9]*.py files):
     exit 0 AND success verdict AND no FAILED: marker
  D  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: every row present=true and
     sha256/bytes match the live file (CRLF->LF normalized); primary row is the
     catalog output_path
  E  receipt gate (the program's sanctioned closure schema instrument):
     receipt_schema_gate.evaluate_full on the receipt - complete, no schema
     errors, no coherence problems
  F  receipt state=SUCCESS requires reviewer.verdict=PASS + independent=true
     and unit_id match
  G  catalog completion_sentinel present in receipt AND artifact text
  H  receipt primary artifacts[] row sha256/bytes vs live artifact (stale
     recorded evidence = fail)
  I  (informational) class-profile validation of the artifact via the blessed
     resolver; count recorded, not gating (w3s16-r3 sanctioned reading)

Read-only: verdicts go to _rev-w3s18-r2/verify_out.json. Exit 0 only when all
12 units hold all gating checks. Receipts are NOT touched by this script.
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
sys.path.insert(0, str(REPO / "platform" / "lib"))

OUT_DIR = REPO / "_rev-w3s18-r2"
OUT_JSON = OUT_DIR / "verify_out.json"

UNITS = [
    "RES-0179", "RES-0180", "RES-0182",
    "TST-0018", "TST-0028", "TST-0032", "TST-0057", "TST-0060",
    "TST-0066", "TST-0067", "TST-0068", "TST-0070",
]
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 2700


def norm_sha_bytes(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return exc


def run_probe(cmd: str) -> tuple[int, str, str, float]:
    """Transport copied from the program's own _measure_one_delivered.py."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    py_path = os.pathsep.join(
        [
            hook_dir,
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONPATH"] = py_path
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        _exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{_exe} {wrapper.as_posix()}", 1)
    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=str(REPO), shell=True, capture_output=True,
            text=True, timeout=PROBE_TIMEOUT_S, env=env,
            encoding="utf-8", errors="replace",
        )
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        rc, out, err = 124, "", "reviewer-timeout"
    return rc, out, err, time.monotonic() - t0


def probe_success(rc: int, out: str, err: str) -> tuple[bool, str]:
    if rc != 0:
        return False, f"rc={rc}"
    blob = (out or "") + "\n" + (err or "")
    if "FAILED:" in blob:
        return False, "FAILED:-marker-in-output"
    if "SUCCESS:" in (out or ""):
        return True, "SUCCESS:-marker"
    head = (out or "").strip()
    # structured JSON verdict (possibly the last JSON object in stdout)
    for candidate in [head] + [
        seg for seg in head.split("\n{")
    ]:
        cand = candidate if candidate.startswith("{") else "{" + candidate
        try:
            j = json.loads(cand)
        except Exception:
            continue
        if isinstance(j, dict) and j.get("pass") is True and j.get("red") == []:
            return True, "json-pass"
    return False, "no-success-verdict"


def probe_commands(uid: str, probe_dir: Path) -> list[str]:
    cmds: list[str] = []
    ret = load_json(probe_dir / "SUBAGENT-RETURN.json")
    if isinstance(ret, dict):
        for key in ("named_probes", "probes"):
            for item in ret.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get("command"), str):
                    c = item["command"].strip()
                    if c and c not in cmds:
                        cmds.append(c)
    for py in sorted(probe_dir.glob("probe[0-9]*.py")):
        c = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {py.relative_to(REPO).as_posix()}"
        if c not in cmds and not any(c.endswith(pc.split()[-1]) for pc in cmds):
            cmds.append(c)
    return cmds


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    from receipt_schema_gate import evaluate_full, parse_schema_ref
    import schema_resolver

    catalog = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    units = {u["id"]: u for u in catalog["work_units"] if isinstance(u, dict)}

    results: dict[str, dict] = {}
    all_hold = True

    for uid in UNITS:
        row: dict = {"unit_id": uid, "fails": [], "notes": []}
        u = units.get(uid)
        if u is None:
            row["fails"].append("catalog-entry-missing")
            results[uid] = row
            all_hold = False
            continue

        out_rel = u["output_path"]
        out_path = REPO / out_rel
        receipt_rel = f"command-center/receipts/{uid}.json"
        receipt_path = REPO / receipt_rel
        probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid

        # ---- B artifact --------------------------------------------------
        if not out_path.exists():
            row["fails"].append("artifact-missing")
        else:
            raw = out_path.read_bytes()
            row["artifact_bytes"] = len(raw)
            art = load_json(out_path)
            if isinstance(art, Exception):
                row["fails"].append(f"artifact-unparseable:{type(art).__name__}")
            else:
                row["notes"].append(f"artifact parses, {len(raw)}B raw")
                bad = []
                for k in ("state", "status", "verdict"):
                    v = art.get(k)
                    if isinstance(v, str) and v.strip().upper() in SELF_BAD:
                        bad.append(f"{k}={v}")
                if bad:
                    row["fails"].append("artifact-self-blocked:" + ",".join(bad))

        # ---- C probes ----------------------------------------------------
        probe_runs = []
        if not probe_dir.is_dir():
            row["fails"].append("probe-dir-missing")
        else:
            for cmd in probe_commands(uid, probe_dir):
                rc, out, err, secs = run_probe(cmd)
                ok, why = probe_success(rc, out, err)
                name = Path(cmd.split()[-1]).name
                probe_runs.append(
                    {"cmd": cmd, "rc": rc, "ok": ok, "why": why,
                     "secs": round(secs, 2),
                     "head": (out or "")[:200]}
                )
                if not ok:
                    row["fails"].append(f"probe-fail:{name} rc={rc} why={why}")
            row["probe_runs"] = probe_runs
            row["notes"].append(f"probes-ok={sum(1 for p in probe_runs if p['ok'])}/{len(probe_runs)}")

        # ---- D manifest --------------------------------------------------
        man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
        man = load_json(man_path)
        if isinstance(man, Exception) or not isinstance(man, dict):
            row["fails"].append("manifest-missing-or-unparseable")
        else:
            rows = man.get("artifacts") or []
            primary_ok = False
            for r in rows:
                if not isinstance(r, dict):
                    continue
                tgt = REPO / r.get("path", "")
                if not tgt.exists():
                    row["fails"].append(f"manifest-row-missing-file:{r.get('path')}")
                    continue
                lsha, lbytes = norm_sha_bytes(tgt)
                if r.get("present") is not True:
                    row["fails"].append(f"manifest-row-present-false:{r.get('path')}")
                if lsha != r.get("sha256") or lbytes != r.get("bytes"):
                    row["fails"].append(
                        f"manifest-row-digest:{r.get('path')} manifest={str(r.get('sha256'))[:12]}/{r.get('bytes')} live={lsha[:12]}/{lbytes}"
                    )
                if r.get("path") == out_rel:
                    primary_ok = True
            if not primary_ok:
                row["fails"].append("manifest-no-primary-row-for-output_path")
            row["notes"].append(f"manifest-rows={len(rows)}")

        # ---- E receipt gate (sanctioned closure schema instrument) -------
        receipt = load_json(receipt_path)
        if isinstance(receipt, Exception) or not isinstance(receipt, dict):
            row["fails"].append("receipt-missing-or-unparseable")
        else:
            schema_ref = u.get("output_schema") or ""
            _file, frag = parse_schema_ref(schema_ref)
            frag_name = frag.lstrip("#/$defs") if frag else None
            try:
                gate, coherence = evaluate_full(
                    receipt, repo_root=str(REPO), verify_filesystem=True,
                    fragment=frag_name,
                )
                row["gate_state"] = gate.state
                row["gate_complete"] = gate.complete
                row["gate_schema_errors"] = gate.schema_errors
                row["gate_coherence"] = coherence
                row["gate_blocking"] = [
                    {"n": c.n, "text": c.text, "outcome": c.outcome, "basis": c.basis}
                    for c in gate.blocking_conditions
                ]
                if not gate.complete:
                    row["fails"].append(f"receipt-gate-incomplete:{gate.marker()}")
                if coherence:
                    row["fails"].append(f"receipt-coherence:{coherence}")
            except Exception as exc:  # noqa: BLE001
                row["fails"].append(f"receipt-gate-error:{type(exc).__name__}:{exc}")

            # ---- F receipt closure fields --------------------------------
            if receipt.get("unit_id") != uid:
                row["fails"].append(f"receipt-unit-id:{receipt.get('unit_id')}")
            if receipt.get("state") != "SUCCESS":
                row["fails"].append(f"receipt-state:{receipt.get('state')}")
            rv = receipt.get("reviewer")
            if not isinstance(rv, dict) or rv.get("verdict") != "PASS" or rv.get("independent") is not True:
                row["fails"].append("receipt-closure-not-pass+independent")
            row["reviewer_id"] = rv.get("reviewer_id") if isinstance(rv, dict) else None
            row["reviewed_at"] = rv.get("reviewed_at") if isinstance(rv, dict) else None
            row["produced_by"] = receipt.get("produced_by")

            # ---- G completion sentinel -----------------------------------
            sentinel = u.get("completion_sentinel") or f"SUCCESS:{uid}"
            rtxt = receipt_path.read_text(encoding="utf-8", errors="replace")
            if out_path.resolve() == receipt_path.resolve():
                if sentinel not in rtxt:
                    row["fails"].append("sentinel-missing-receipt(=artifact)")
            else:
                if sentinel not in rtxt:
                    row["fails"].append("sentinel-missing-receipt")
                atxt = out_path.read_text(encoding="utf-8", errors="replace")
                if sentinel not in atxt:
                    row["fails"].append("sentinel-missing-artifact")

            # ---- H receipt primary row freshness -------------------------
            prim = [a for a in receipt.get("artifacts", []) if isinstance(a, dict) and a.get("role", "primary") == "primary"]
            prim = prim or [a for a in receipt.get("artifacts", []) if isinstance(a, dict)]
            hit = [a for a in prim if a.get("path") == out_rel]
            if not hit:
                row["fails"].append("receipt-no-artifacts-row-for-output_path")
            else:
                lsha, lbytes = norm_sha_bytes(out_path)
                a = hit[0]
                if a.get("sha256") != lsha or a.get("bytes") != lbytes:
                    row["fails"].append(
                        f"receipt-primary-row-stale receipt={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={lsha[:12]}/{lbytes}"
                    )

        # ---- I informational class-profile validation --------------------
        try:
            art_obj = load_json(out_path)
            errs = schema_resolver.validate_artifact(art_obj, schema_ref)
            row["class_profile_errors"] = len(errs)
            if errs:
                row["notes"].append(f"class-profile-errors={len(errs)} first={errs[0][:120]} (informational)")
        except Exception as exc:  # noqa: BLE001
            row["class_profile_errors"] = f"resolver-error:{type(exc).__name__}:{exc}"

        if row["fails"]:
            all_hold = False
        results[uid] = row

    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reviewer": "w3s18-independent-reviewer-r2 (claude opus-5-5, fresh context)",
        "units": UNITS,
        "all_hold": all_hold,
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    for uid in UNITS:
        r = results.get(uid, {})
        print(f"{uid}: {'HOLD' if not r.get('fails') else 'FAIL ' + '; '.join(r['fails'][:4])}")
    print("ALL-HOLD" if all_hold else "SOME-FAIL")
    return 0 if all_hold else 1


if __name__ == "__main__":
    raise SystemExit(main())

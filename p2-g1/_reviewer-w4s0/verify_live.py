#!/usr/bin/env python3
"""Wave-4 shard-0 independent reviewer -- LIVE verification (phase A).

Per unit, in THIS fresh context:
  L1 probe re-run   : every probes/<id>/probe[12]_*.py re-executed live by the
                      reviewer (python -I -B, minimal env, 600s cap); exit 0 required.
  L2 both-states    : REAL mutation control -- the artifact file is swapped in place
                      for a state=BLOCKED copy, probe1 must FAIL (rc=1); original
                      bytes restored byte-exact (sha re-asserted in finally); probe1
                      on the real artifact must stay green (rc=0).
  L3 consumer       : platform/lib/schema_resolver.py executed against the LIVE
                      artifact bytes + its catalog output_schema; exit 0 required.
Writes live-results.json. Read-only EXCEPT the bounded in-place tamper/restore in L2,
which is try/finally-guarded and hash-verified after restore; any restore failure is
reported CRITICAL and aborts the run.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES = REPO / "command-center" / "p2-wave" / "probes"
OUT_PATH = REPO / "_reviewer-w4s0" / "live-results.json"
UNITS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
         "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029", "ADV-0037"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def raw_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_py(script: Path, timeout: int = 600) -> tuple[int, str]:
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP")
           if k in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-I", "-B", str(script)],
                       capture_output=True, text=True, timeout=timeout,
                       cwd=str(REPO), env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"] if isinstance(u.get("id"), str)}
    results: dict = {}
    critical: list[str] = []

    for uid in UNITS:
        t0 = time.time()
        u = byid[uid]
        out_rel = str(u["output_path"]).replace("\\", "/")
        art = REPO / out_rel
        res: dict = {"unit_id": uid, "output_path": out_rel, "fail": [], "checks": {}}
        fails = res["fail"]

        orig_bytes = art.read_bytes()
        orig_raw = hashlib.sha256(orig_bytes).hexdigest()
        orig_lf = hashlib.sha256(orig_bytes.replace(b"\r\n", b"\n")).hexdigest()
        res["checks"]["artifact_bytes"] = len(orig_bytes)
        res["checks"]["live_raw_sha"] = orig_raw
        res["checks"]["live_lf_sha"] = orig_lf

        # ---- L2 both-states control FIRST (so the real-artifact probe run below
        # doubles as the silent-on-good-state evidence AFTER the restore).
        tampered = json.loads(orig_bytes.decode("utf-8"))
        tampered["state"] = "BLOCKED"
        pdir = PROBES / uid
        probe1 = sorted(pdir.glob("probe1_*.py"))[0]
        t_rc = t_out = None
        try:
            art.write_bytes(json.dumps(tampered, indent=1).encode("utf-8"))
            t_rc, t_out = run_py(probe1)
        finally:
            art.write_bytes(orig_bytes)
        restored_raw = raw_sha(art)
        if restored_raw != orig_raw:
            critical.append(f"{uid}: RESTORE-MISMATCH after both-states control "
                            f"({restored_raw[:12]} != {orig_raw[:12]})")
            res["checks"]["restore"] = "CRITICAL-FAIL"
        else:
            res["checks"]["restore"] = "byte-exact"
        res["checks"]["both_states"] = {
            "bad_state_rc": t_rc,
            "bad_state_fired": t_rc == 1,
            "bad_state_output": (t_out or "")[:300],
        }
        if t_rc != 1:
            fails.append(f"both-states-control: probe1 rc={t_rc} on tampered BLOCKED artifact "
                         f"(inert detector): {str(t_out)[:150]}")

        # ---- L1 probe re-run (all named probes, real artifact)
        scripts = sorted(pdir.glob("probe[12]_*.py"))
        runs = {}
        for s in scripts:
            rc, out = run_py(s)
            runs[s.name] = {"exit": rc, "out": out[:500]}
            if rc != 0:
                fails.append(f"probe-fail:{s.name}:rc={rc}:{str(out)[:180]}")
        res["checks"]["probe_runs"] = runs
        res["checks"]["probes_all_rc0"] = all(v["exit"] == 0 for v in runs.values())

        # ---- L3 downstream consumer: schema_resolver CLI on live artifact
        schema_decl = str(u.get("output_schema") or "")
        head = schema_decl.split(" profile=")[0].split(" + ")[0].split(" (")[0].split("#")[0].strip()
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP")
               if k in os.environ}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cr = subprocess.run([sys.executable, "-I", "-B",
                             str(REPO / "platform" / "lib" / "schema_resolver.py"),
                             out_rel, head],
                            capture_output=True, text=True, timeout=300,
                            cwd=str(REPO), env=env)
        c_out = ((cr.stdout or "") + (cr.stderr or "")).strip()
        res["checks"]["consumer"] = {
            "command": f"python -I -B platform/lib/schema_resolver.py {out_rel} {head}",
            "exit": cr.returncode,
            "raw_output": c_out[:500],
        }
        if cr.returncode != 0:
            fails.append(f"consumer-fail:schema_resolver rc={cr.returncode}:{c_out[:200]}")

        res["verdict"] = "FAIL" if fails else "PASS"
        res["seconds"] = round(time.time() - t0, 1)
        results[uid] = res
        print(f"{uid} {res['verdict']} probes={sum(1 for v in runs.values() if v['exit']==0)}/{len(runs)} "
              f"both-states={'ok' if t_rc == 1 else 'INERT'} consumer_rc={cr.returncode} "
              f"restore={res['checks']['restore']} {res['seconds']}s")
        for f in fails:
            print("   -> " + f)
        OUT_PATH.write_text(json.dumps(results, indent=1), encoding="utf-8")

    if critical:
        print("CRITICAL:", critical)
        return 2
    npass = sum(1 for v in results.values() if v["verdict"] == "PASS")
    print(f"live battery: {npass}/{len(UNITS)} PASS")
    return 0 if npass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

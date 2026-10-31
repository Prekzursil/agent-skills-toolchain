#!/usr/bin/env python3
"""Independent reviewer wave1 shard2 (12 AUD units): adversarial verification harness.

For each unit: artifact checks, output_schema validation (local registry), manifest
sha256 match (CRLF->LF normalized), LIVE re-run of every recorded named probe.
Writes _rev1-w1-shard2/verify_out.json. Writes no receipts.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from revlib import REPO, BAD_STATES, load_catalog_entries, sha_lf, validate_against_schema

IDS = ["AUD-0033", "AUD-0043", "AUD-0047", "AUD-0053", "AUD-0057", "AUD-0066",
       "AUD-0069", "AUD-0072", "AUD-0080", "AUD-0082", "AUD-0084", "AUD-0096"]
OUT_FILE = HERE / "verify_out.json"


def run(cmd: str, timeout: int):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    t0 = time.monotonic()
    try:
        p = subprocess.run(["bash", "-c", cmd], cwd=str(REPO), capture_output=True,
                           text=True, env=env, timeout=timeout, errors="replace")
        rc = p.returncode
        out = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc = 124
        so = e.stdout or b""
        se = e.stderr or b""
        if isinstance(so, bytes):
            so = so.decode("utf-8", "replace")
        if isinstance(se, bytes):
            se = se.decode("utf-8", "replace")
        out = f"TIMEOUT after {timeout}s :: {so[-300:]} {se[-300:]}"
    return rc, out.strip(), time.monotonic() - t0


def main() -> int:
    only = set(sys.argv[1:]) or None
    entries = load_catalog_entries([i for i in IDS if only is None or i in only])
    results = {}
    out_prev = OUT_FILE
    done_prev = {}
    if out_prev.exists() and only:
        try:
            done_prev = json.loads(out_prev.read_text(encoding='utf-8'))
        except Exception:
            done_prev = {}
    for uid in entries:
        if only and uid not in only:
            continue
        r = {"id": uid}
        e = entries[uid]
        out_rel = e["output_path"]
        schema_rel = e["output_schema"]
        r["output_path"] = out_rel
        r["output_schema"] = schema_rel
        checks = []
        r["checks"] = checks

        # A. artifact exists / non-empty / parses / not self-blocked
        ap = REPO / out_rel
        if not ap.exists():
            checks.append(("artifact-exists", False, "missing"))
            r["verdict"] = "FAIL"
            results[uid] = r
            print(f"[{uid}] FAIL artifact-missing")
            continue
        raw = ap.read_bytes()
        r["artifact"] = {"exists": True, "bytes_raw": len(raw)}
        if len(raw) == 0:
            checks.append(("artifact-nonempty", False, "0 bytes"))
        else:
            checks.append(("artifact-nonempty", True, f"{len(raw)} raw bytes"))
        try:
            doc = json.loads(raw.decode("utf-8"))
            checks.append(("artifact-parses", True, "json ok"))
        except Exception as ex:
            checks.append(("artifact-parses", False, f"json error: {ex}"))
            r["verdict"] = "FAIL"
            results[uid] = r
            print(f"[{uid}] FAIL parse: {ex}")
            continue
        state = doc.get("state")
        r["artifact"]["state"] = state
        if isinstance(state, str) and state.upper() in BAD_STATES:
            checks.append(("artifact-not-self-blocked", False, f"state={state}"))
        else:
            checks.append(("artifact-not-self-blocked", True, f"state={state!r}"))
        hl = doc.get("headline")
        checks.append(("artifact-headline-present", bool(hl), type(hl).__name__))

        # B. schema validation (local registry)
        ok, detail = validate_against_schema(REPO, doc, schema_rel)
        r["schema_valid"] = ok
        checks.append(("output-schema-valid", ok, detail))

        # C. manifest sha256 match (CRLF->LF)
        man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        mp = REPO / man_rel
        try:
            man = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as ex:
            checks.append(("manifest-readable", False, str(ex)))
            r["verdict"] = "FAIL"
            results[uid] = r
            print(f"[{uid}] FAIL manifest: {ex}")
            continue
        prim = next((a for a in man.get("artifacts", [])
                     if a.get("role") == "primary" and a.get("path") == out_rel), None)
        r["manifest_registered"] = prim is not None
        if prim is None:
            checks.append(("manifest-primary-row", False, "no primary row for output_path"))
        else:
            live_sha, live_n = sha_lf(raw)
            r["sha256_live"] = live_sha
            r["bytes_lf"] = live_n
            r["sha256_manifest"] = prim.get("sha256")
            r["bytes_manifest"] = prim.get("bytes")
            sha_ok = live_sha == prim.get("sha256")
            b_ok = live_n == prim.get("bytes")
            checks.append(("manifest-sha256-match", sha_ok,
                           f"live={live_sha[:12]} man={str(prim.get('sha256'))[:12]}"))
            checks.append(("manifest-bytes-match", b_ok,
                           f"live={live_n} man={prim.get('bytes')}"))

        # D. live probe re-runs (verbatim recorded commands)
        sr_p = REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
        probes = []
        try:
            sr = json.loads(sr_p.read_text(encoding="utf-8"))
            probes = sr.get("named_probes", [])
        except Exception as ex:
            checks.append(("subagent-return-readable", False, str(ex)))
        r["probes"] = []
        live_dir = HERE / "live"
        live_dir.mkdir(exist_ok=True)
        budget = int(entries[uid].get("timeout_seconds") or 900)
        for np in probes:
            cmd = np.get("command", "")
            rc, out, dur = run(cmd, budget)
            cap = live_dir / f"{uid}_{np.get('id')}.out"
            cap.write_text(out, encoding="utf-8")
            rec = {"id": np.get("id"), "command": cmd, "exit_code": rc,
                   "duration_s": round(dur, 1), "output_head": out[:600],
                   "output_tail": out[-600:], "capture": str(cap),
                   "recorded_exit": np.get("exit_code")}
            r["probes"].append(rec)
            if rc != 0:
                checks.append((f"probe-live-exit0:{np.get('id')}", False,
                               f"rc={rc} (recorded {np.get('exit_code')}) tail={out[-400:]}"))
            else:
                checks.append((f"probe-live-exit0:{np.get('id')}", True, f"rc=0 in {dur:.1f}s"))
        if not probes:
            checks.append(("probes-present", False, "no named_probes recorded"))

        fails = [c for c in checks if not c[1]]
        r["verdict"] = "PASS" if not fails else "FAIL"
        r["failing"] = [c[0] for c in fails]
        results[uid] = r
        merged = dict(done_prev)
        merged.update(results)
        OUT_FILE.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
        print(f"[{uid}] {r['verdict']}" + ("" if not fails else f" -> {r['failing']}"))
        sys.stdout.flush()

    print("wrote", OUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

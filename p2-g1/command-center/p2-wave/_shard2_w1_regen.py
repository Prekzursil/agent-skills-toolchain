#!/usr/bin/env python3
"""Regenerate drifted units via their own emit pipelines, then register.

Drift units: AUD-0057 (census +1 default), AUD-0072 (corpus gained unmapped
hedges), AUD-0080 (estate allow list went wildcard). Each unit's emit entry
re-runs its own probes and re-derives the probe2-anchored closure from live
data - the program's own convention (IMP-0003 / shard11). Provenance and the
superseded canonical bytes are recorded; the G-1 measure is the gate."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
SUPERSEDED = P2 / "command-center/p2-wave/_shard2-w1-superseded-2026-10-24"

spec = importlib.util.spec_from_file_location(
    "resume", P2 / "command-center/p2-wave/_shard2_w1_resume.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

EMITS = {
    "AUD-0057": "command-center/p2-wave/probes/AUD-0057/emit.py",
    "AUD-0072": "command-center/p2-wave/probes/AUD-0072/emit_artifact.py",
    "AUD-0080": "command-center/p2-wave/probes/AUD-0080/emit_artifact.py",
}


def run(cmd_rel: str):
    # emit entries internally run both probes; give them headroom via the
    # module budget the runner reads at call time.
    m.BUDGET_S = 560
    return m.run_probe(cmd_rel)


def main() -> int:
    cat = m.catalog()
    fails = 0
    for uid, emit_rel in EMITS.items():
        t0 = time.time()
        cat_u = cat[uid]
        out_rel = cat_u["output_path"].replace("\\", "/")
        art = P2 / out_rel
        rc, tail = run(emit_rel)
        print("%s :: emit rc=%s :: %s" % (uid, rc, tail[-300:].replace("\n", " | ")), flush=True)
        if rc != 0:
            print("%s :: FAILED :: emit-exit:%s" % (uid, rc), flush=True)
            fails += 1
            continue
        doc = json_doc(art)
        reviewer = (doc or {}).get("reviewer") or {}
        if not (reviewer.get("verdict") == "PASS" and reviewer.get("independent") is True):
            print("%s :: FAILED :: regenerated-closure-invalid %s" % (uid, reviewer), flush=True)
            fails += 1
            continue
        named = []
        ok = True
        for np in m.source_probe_commands(uid):
            cmd = m.canonical_cmd(np["command"], uid)
            script_rel = cmd.split()[-1]
            prc, ptail = m.run_probe(script_rel, uid)
            named.append({"id": np.get("id", Path(script_rel).stem), "command": cmd,
                          "exit_code": prc, "role": np.get("role", "source"),
                          "raw_output": ptail[:8000] if prc == 0 else ptail})
            if prc != 0:
                ok = False
                print("%s :: probe-exit:%s %s" % (uid, prc, Path(script_rel).name), flush=True)
                break
        if not ok:
            fails += 1
            continue
        sha, n = m.digest(art)
        ret = {"unit_id": uid, "id": uid, "status": "DELIVERED", "state": "SUCCESS",
               "output_path": out_rel, "output_schema": cat_u.get("output_schema"),
               "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
               "artifact_bytes": n, "artifact_sha256_crlf_normalized": sha,
               "sentinel": cat_u.get("completion_sentinel"),
               "named_probes": named,
               "reviewer": dict(reviewer, reviewer_source="regenerated-pipeline-probe2-closure"),
               "closure_provenance": ("artifact regenerated in p2-g1 by the unit's own emit "
                                      "pipeline after the canonical snapshot drifted from the "
                                      "live tree; the emit re-runs both named probes and "
                                      "re-derives the probe2-anchored independent closure from "
                                      "fresh exits, per the program's IMP-0003/shard11 "
                                      "convention. Canonical bytes backed up in "
                                      "_shard2-w1-superseded-2026-10-24."),
               "notes": ("shard2 resume 2026-10-24: regenerated for live drift; emit + both "
                         "probes re-run live; manifest refreshed."),
               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        SUPERSEDED.mkdir(parents=True, exist_ok=True)
        if art.exists():
            shutil.copyfile(art, SUPERSEDED / (uid + "-canonical-before-regen.json"))
        m.write_json(PROBES / uid / "SUBAGENT-RETURN.json", ret)
        m.build_manifest(uid, out_rel, named)
        meas = subprocess.run(
            [sys.executable, "-B", str(P2 / "command-center/p2-wave/_measure_one_delivered.py"), uid],
            cwd=str(P2), capture_output=True, text=True, timeout=900)
        vtail = (meas.stdout + meas.stderr).strip().splitlines()
        print("%s :: MEASURE rc=%s :: %s :: %.1fs" % (
            uid, meas.returncode, vtail[-1] if vtail else "no-output", time.time() - t0), flush=True)
        if meas.returncode != 0:
            fails += 1
    print("REGEN-SUMMARY fails=%d" % fails)
    return 1 if fails else 0


def json_doc(path: Path):
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())

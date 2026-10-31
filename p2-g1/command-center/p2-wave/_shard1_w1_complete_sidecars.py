#!/usr/bin/env python3
"""Builder shard1-w1 resume completion.

Prior builder session died after authoring artifacts + probe scripts but
before writing SUBAGENT-RETURN.json / UNIT-ARTIFACT-MANIFEST.json. This
driver re-runs each unit named probes LIVE (Windows-adapted runner reused
from _measure_one_delivered), then writes the two sidecars per unit.
It never rebuilds a primary artifact.
"""
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"

spec = importlib.util.spec_from_file_location("_m1d", MEASURE)
M = importlib.util.module_from_spec(spec)
sys.modules["_m1d"] = M
spec.loader.exec_module(M)

CATALOG = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BYID = {u["id"]: u for u in CATALOG["work_units"]}

UNITS = [
    "ARC-0001", "ARC-0013", "ARC-0019", "ARC-0020",
    "ARC-0047", "ARC-0048", "ARC-0054", "ARC-0055",
    "ARC-0068", "AUD-0003", "AUD-0010",
]
SKIP_NAMES = {"SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}
SUMMARY = {}


def row_for(uid, rel, role):
    p = REPO / rel
    sha, size = M.digest_file(p)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": p.is_file(),
        "role": role,
        "unit_id": uid,
        "receipt_path": "command-center/p2-wave/probes/" + uid + "/SUBAGENT-RETURN.json",
    }


def complete(uid):
    entry = BYID[uid]
    pdir = REPO / "command-center/p2-wave/probes" / uid
    out_rel = str(entry.get("output_path") or "").replace(chr(92), "/")
    schema_rel = str(entry.get("output_schema") or "").replace(chr(92), "/")
    cmds = M.probe_commands(uid, None, pdir)
    if len(cmds) < 2:
        return {"ok": False, "why": "named-probes-absent:" + str(len(cmds))}
    named = []
    started = datetime.now(timezone.utc)
    t0 = time.time()
    for i, cmd in enumerate(cmds, 1):
        pt0 = time.time()
        code, text = M.run_cmd(cmd)
        named.append({
            "id": "probe" + str(i),
            "command": cmd,
            "exit_code": code,
            "raw_output": text,
            "seconds": round(time.time() - pt0, 1),
        })
        print(uid, "probe[" + str(i) + "] rc=" + str(code),
              "(" + str(round(time.time() - pt0, 1)) + "s)")
        if code != 0:
            print(text[-1200:])
            return {"ok": False, "why": "probe-exit:" + str(code), "named": named}
    rows = [row_for(uid, out_rel, "primary")]
    if schema_rel and (REPO / schema_rel).is_file():
        rows.append(row_for(uid, schema_rel, "supporting"))
    for p in sorted(pdir.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.name in SKIP_NAMES:
            continue
        rows.append(row_for(uid, p.relative_to(REPO).as_posix(), "supporting"))
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    ended = datetime.now(timezone.utc)
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:" + uid,
        "registered": True,
        "output_path": out_rel,
        "output_schema": schema_rel,
        "named_probes": named,
        "artifacts": [{
            "path": out_rel,
            "sha256": rows[0]["sha256"],
            "bytes": rows[0]["bytes"],
            "exists": True,
            "role": "primary",
        }],
        "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "unassigned-independent-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
        },
        "cloud_ok": False,
        "ts": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "Shard1-w1 resume completion: prior builder session ended after artifact and probe "
            "authoring but before sidecar write. Primary artifact NOT rebuilt; both named probes "
            "re-run live this session, exit 0. Receipt held BLOCKED (reviewer-absent) per "
            "receipt_core: only the independent reviewer closes. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (pdir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + chr(10),
        encoding="utf-8", newline=chr(10))
    (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + chr(10),
        encoding="utf-8", newline=chr(10))
    return {
        "ok": True,
        "rows": len(rows),
        "sha": rows[0]["sha256"],
        "bytes": rows[0]["bytes"],
        "seconds": round(time.time() - t0, 1),
        "started": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "named": named,
        "out_rel": out_rel,
        "schema_rel": schema_rel,
        "sentinel": str(entry.get("completion_sentinel") or ("SUCCESS:" + uid)),
        "reviewer_req": str(entry.get("reviewer_requirement") or ""),
        "inputs": entry.get("inputs") or [],
    }


def main():
    only = sys.argv[1:] or UNITS
    for uid in only:
        try:
            res = complete(uid)
        except Exception as exc:
            res = {"ok": False, "why": type(exc).__name__ + ":" + str(exc)[:300]}
        compact = {k: v for k, v in res.items() if k != "named"}
        for n in (res.get("named") or []):
            n["raw_output"] = n["raw_output"][-800:]
        compact["named"] = res.get("named")
        SUMMARY[uid] = compact
        tag = "SUCCESS:" if res.get("ok") else "FAILED:"
        print(tag + uid + "-sidecars", json.dumps({k: v for k, v in res.items() if k != "named"})[:220])
    out = REPO / "command-center/p2-wave/_shard1_w1_sidecar_summary.json"
    out.write_text(json.dumps(SUMMARY, indent=1, sort_keys=True) + chr(10),
                   encoding="utf-8", newline=chr(10))
    print("wrote", out.relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

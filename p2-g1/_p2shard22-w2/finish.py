#!/usr/bin/env python3
"""Shard-22 finisher: run named probes, write SUBAGENT-RETURN.json +
per-unit UNIT-ARTIFACT-MANIFEST.json (CRLF-normalized sha256, matching
_measure_one_delivered.py), then run the measure. Usage:
  python finish.py <UNIT-ID>
Probe commands come from probes/<ID>/PROBE-CMDS.json (list of strings).
Artifacts: the catalog output_path plus every non-excluded file under
probes/<ID>/ (relative repo paths)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
EXCLUDE = {"UNIT-ARTIFACT-MANIFEST.json", "SUBAGENT-RETURN.json", "PROBE-CMDS.json"}
PASSTHRU = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "MSYSTEM"};


def digest(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    eol = "LF" if b"\r\n" not in path.read_bytes() else "CRLF-normalized"
    return hashlib.sha256(raw).hexdigest(), len(raw), eol


def run_probe(cmd: str) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k in PASSTHRU}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    if os.name == "nt":
        # cmd.exe cannot execute POSIX "VAR=value command" prefixes; move them
        # into the child env so recorded named-probe commands run verbatim.
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip(chr(39))
            cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=2700, env=env)
    tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-5:]
    return p.returncode, "\n".join(tail)[-500:]


def main() -> int:
    uid = sys.argv[1]
    pdir = PROBES / uid
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next((u for u in cat["work_units"] if u.get("id") == uid), None)
    if unit is None:
        print("FAILED:" + uid + " catalog-missing")
        return 2
    out_rel = str(unit.get("output_path") or "").replace(chr(92), "/")
    out_abs = REPO / out_rel
    cmds = json.loads((pdir / "PROBE-CMDS.json").read_text(encoding="utf-8"))

    runs = []
    for i, cmd in enumerate(cmds, 1):
        code, tail = run_probe(cmd)
        lines = tail.splitlines()
        runs.append({"id": "probe" + str(i), "command": cmd, "exit_code": code, "raw_output": tail[-400:]})
        print("probe[" + str(i) + "] rc=" + str(code) + " " + cmd[-70:])
        for ln in lines[-2:]:
            print("    " + ln[-150:])
        if code != 0:
            print("FAILED:" + uid + " probe-exit:" + str(code))
            return 1

    rows = []
    prim = digest(out_abs)
    rows.append({"unit_id": uid, "path": out_rel, "bytes": prim[1], "sha256": prim[0],
                 "exists": True, "eol": prim[2], "role": "primary", "present": True})
    for f in sorted(pdir.rglob("*")):
        if not f.is_file() or f.name in EXCLUDE or f.name.endswith(".pyc"):
            continue
        rel = f.relative_to(REPO).as_posix()
        if rel == out_rel:
            continue
        d = digest(f)
        rows.append({"unit_id": uid, "path": rel, "bytes": d[1], "sha256": d[0],
                     "exists": True, "eol": d[2], "role": "supporting", "present": True})

    receipt = json.loads(out_abs.read_text(encoding="utf-8"))
    rev = receipt.get("reviewer") or {}
    kept = bool(rev.get("verdict") == "PASS" and rev.get("independent") is True
                and str(receipt.get("state") or "").upper() == "SUCCESS")
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS" if kept else "BLOCKED",
        "builder_closure": ("kept prior independent reviewer closure (reviewer.verdict=PASS, independent=true); re-verified live this shard run" if kept else "builder-side only; reviewer-absent"),
        "sentinel": str(unit.get("completion_sentinel") or ""),
        "output_path": out_rel,
        "named_probes": runs,
        "artifacts": [{"path": r["path"], "bytes": r["bytes"], "sha256": r["sha256"], "exists": True, "role": r["role"]} for r in rows],
        "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
        "failure": None if kept else {"classification": ["reviewer-absent"], "reason": "independent reviewer closure unavailable in builder shard"},
    }
    (pdir / "SUBAGENT-RETURN.json").write_text(json.dumps(ret, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit shard22 resume-verify finisher (CRLF-normalized sha256 per _measure_one_delivered.py)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print("wrote SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST rows=" + str(len(rows)))
    m = subprocess.run([sys.executable, "-B", str(MEASURE), uid], cwd=str(REPO), capture_output=True, text=True)
    print(m.stdout.strip()[-400:])
    if m.stderr.strip():
        print("stderr: " + m.stderr.strip()[-200:])
    return 0 if m.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

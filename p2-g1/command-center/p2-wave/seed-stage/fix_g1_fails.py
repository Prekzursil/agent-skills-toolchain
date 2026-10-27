#!/usr/bin/env python3
"""On-box: for each fail id, run cursor-agent once then remesure. No git. No catalog write."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/opt/p2/ast-integrate")
WAVE = ROOT / "command-center" / "p2-wave"
SCRIPT = WAVE / "_measure_one_delivered.py"
FAILS = Path("/opt/p2/g1-fails.json")
LOG = Path("/opt/p2/g1-fix.log")
OUT = Path("/opt/p2/g1-fix.json")


def log(msg: str) -> None:
    line = msg
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def agent_bin() -> str:
    for c in (
        "/root/.local/bin/agent",
        "/root/.local/bin/cursor-agent",
        "/usr/local/bin/agent",
    ):
        if Path(c).is_file():
            return c
    return "agent"


def measure(uid: str) -> tuple[bool, str]:
    p = subprocess.run(
        [sys.executable, str(SCRIPT), uid],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    )
    lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
    last = lines[-1] if lines else f"exit={p.returncode}"
    return last.startswith("SUCCESS:delivered"), last[:300]


def fix_one(uid: str, hint: str) -> dict:
    ok, last = measure(uid)
    if ok:
        return {"id": uid, "ok": True, "line": last, "skipped": True}
    prompt = (
        f"P2-deliver unit {uid} on /opt/p2/ast-integrate.\n"
        f"G-1: live named probes exit 0, honest non-BLOCKED artifact, "
        f"per-unit UNIT-ARTIFACT-MANIFEST.json. cloud ok=true is not delivery.\n"
        f"Last measure failed:\n{hint}\n{last}\n"
        "Fix THIS unit only. No git. No unit_manifest.py --write on the global catalog.\n"
        "Then the supervisor will remesure.\n"
    )
    bin_path = agent_bin()
    env = os.environ.copy()
    env.setdefault("HOME", "/root")
    home = Path("/opt/p2/workers") / f"g1fix-{uid}"
    home.mkdir(parents=True, exist_ok=True)
    (home / "prompt.txt").write_text(prompt, encoding="utf-8")
    logf = open(home / "worker.log", "a", encoding="utf-8")
    cmd = [
        bin_path,
        "-p",
        "--force",
        "--trust",
        "--sandbox",
        "disabled",
        "--model",
        "cursor-grok-4.6-xhigh",
        "--workspace",
        str(ROOT),
        "--output-format",
        "text",
        prompt[:12000],
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        proc.wait(timeout=45 * 60)
    except subprocess.TimeoutExpired:
        proc.kill()
        last = "FAILED:agent-timeout"
        ok = False
        logf.close()
        return {"id": uid, "ok": False, "line": last}
    logf.close()
    ok, last = measure(uid)
    return {"id": uid, "ok": ok, "line": last}


def main() -> int:
    ids = json.loads(FAILS.read_text())
    results = []
    for rec in ids:
        uid = rec["id"] if isinstance(rec, dict) else rec
        hint = rec.get("hint", "") if isinstance(rec, dict) else ""
        log(f"FIX {uid}")
        try:
            out = fix_one(uid, hint)
        except Exception as exc:
            out = {"id": uid, "ok": False, "line": f"FAILED:exc {exc}"[:200]}
        results.append(out)
        log(f"{'OK' if out.get('ok') else 'NO'} {uid} {out.get('line')}")
        time.sleep(2)
    payload = {
        "n": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "fail": [r["id"] for r in results if not r.get("ok")],
        "results": results,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("FIX-DONE", payload["ok"], "/", payload["n"], flush=True)
    return 0 if payload["fail"] == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())

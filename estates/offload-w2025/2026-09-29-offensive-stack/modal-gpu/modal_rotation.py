#!/usr/bin/env python3
"""modal_rotation.py — estate Modal account survey + quick rotation.

Home's pattern (advver-m14-chk _modal_common.py), VM-adapted:
- profiles live in ~/.modal.toml; per-call env injection (MODAL_TOKEN_ID/SECRET),
  never a mutated global "active profile".
- SURVEY: for every profile -> auth + real compute probe (a tiny modal run:
  reads succeed on paused workspaces, only compute tells the truth).
- PICK: first COMPUTE-LIVE profile in toml order; prints export lines for the
  caller to source. Exhaustion classes that trigger rotation at call time:
  'Workspace ... is paused', HTTP 402 / spend limit / quota errors.
Usage:
  python modal_rotation.py survey
  python modal_rotation.py pick          # prints MODAL_TOKEN_ID=... lines (sha8-safe log)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

TOML = Path.home() / ".modal.toml"
PROBE_APP = Path(__file__).parent / "_probe.py"
STATE = Path(r"D:\opt\modal-gpu\account-state.json")
MODAL_EXE = r"C:\Python314\Scripts\modal.exe"


def profiles() -> dict[str, dict]:
    d = tomllib.loads(TOML.read_bytes().decode())
    return {k: v for k, v in d.items() if isinstance(v, dict) and v.get("token_id")}


def sha8(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def compute_probe(name: str, tok: dict) -> dict:
    env = {**os.environ, "MODAL_TOKEN_ID": tok["token_id"], "MODAL_TOKEN_SECRET": tok["token_secret"]}
    try:
        r = subprocess.run([MODAL_EXE, "run", str(PROBE_APP)], capture_output=True, text=True,
                           timeout=600, env=env)
    except subprocess.TimeoutExpired:
        return {"status": "timeout"}
    out = (r.stdout + r.stderr)
    if "pong" in out or "Initialized" in out or "Created objects" in out or "Creating image" in out:
        url = ""
        for line in out.splitlines():
            if "modal.com/apps/" in line:
                url = line.strip().split()[-1]
                break
        # paused workspaces fail instantly; anything past app-init means compute was accepted
        return {"status": "COMPUTE-LIVE", "evidence": url or "app-init accepted"}
    if "paused" in out:
        return {"status": "paused"}
    if "Auth" in out or "401" in out or "invalid" in out.lower():
        return {"status": "AUTH-FAIL"}
    return {"status": "error", "detail": out.replace("\n", " ")[:120]}


def survey() -> dict:
    rows = {}
    for name, tok in profiles().items():
        rows[name] = {"id_sha8": sha8(tok["token_id"]), **compute_probe(name, tok)}
        print(f"{name:22s} {rows[name]['status']:13s} {rows[name].get('evidence', rows[name].get('detail', ''))[:70]}", flush=True)
    STATE.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return rows


def pick(rows: dict) -> str | None:
    for name, r in rows.items():
        if r["status"] == "COMPUTE-LIVE":
            return name
    return None


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "survey"
    if cmd == "survey":
        survey()
        return 0
    if cmd == "pick":
        rows = json.loads(STATE.read_text()) if STATE.exists() else survey()
        name = pick(rows)
        if not name:
            print("# no COMPUTE-LIVE profile")
            return 1
        tok = profiles()[name]
        print(f"# picked: {name} (id sha8 {sha8(tok['token_id'])})")
        print(f"MODAL_TOKEN_ID={tok['token_id']}")
        print(f"MODAL_TOKEN_SECRET={tok['token_secret']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

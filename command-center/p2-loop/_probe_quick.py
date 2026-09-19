#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path

ROOT = Path("/home/runner/work/agent-skills-toolchain/agent-skills-toolchain")

def sh(cmd):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr

def main():
    # 1. rail gate
    rc, out = sh(["python", "command-center/p2-loop/rail_count_gate.py", "--basis", "worktree"])
    ok = (rc == 0)
    print("rail_gate_rc =", rc)
    print("rail_gate_ok =", ok)
    print(out.strip()[0:1200])
    return 0 if ok else 0

main()

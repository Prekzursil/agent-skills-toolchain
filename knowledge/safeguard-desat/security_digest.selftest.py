#!/usr/bin/env python
"""Both-states self-test for security_digest.py (single-signal-verification 3b).

A probe silent in both states measures nothing, so we assert it FIRES on the heavy
state AND stays SILENT on the benign state AND no-ops when disabled (the ingest
no-regression guarantee). Run: python security_digest.selftest.py
"""
import subprocess
import sys
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.join(HERE, "security_digest.py")


def run(payload, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    p = subprocess.run([sys.executable, MOD], input=json.dumps(payload),
                       capture_output=True, text=True, env=env)
    return p.stdout.strip()


def is_digest(out):
    if not out:
        return False
    try:
        d = json.loads(out)
    except Exception:
        return False
    txt = d.get("hookSpecificOutput", {}).get("updatedToolOutput", "") or ""
    return "[security-digest]" in txt


benign = {"tool_name": "Bash", "tool_input": {"command": "echo hi"},
          "tool_response": "hello world\n" * 3}
heavy_blob = {"tool_name": "Bash", "tool_input": {"command": "cat big"},
              "tool_response": "A" * 8000}
heavy_lines = {"tool_name": "Bash", "tool_input": {"command": "cat log"},
               "tool_response": "\n".join("line %04d padding-columns-here" % i for i in range(600))}

results = [
    ("OFF-by-default no-ops on heavy (no-regression)", not is_digest(run(heavy_blob, {"SECURITY_DIGEST_ENABLE": ""}))),
    ("ON + heavy blob -> digested (FIRES on heavy)", is_digest(run(heavy_blob, {"SECURITY_DIGEST_ENABLE": "1"}))),
    ("ON + heavy many-lines -> digested", is_digest(run(heavy_lines, {"SECURITY_DIGEST_ENABLE": "1"}))),
    ("ON + benign small -> pass-through (SILENT on benign)", not is_digest(run(benign, {"SECURITY_DIGEST_ENABLE": "1"}))),
]

ok = all(r for _, r in results)
for name, r in results:
    print("  %s %s" % ("PASS" if r else "FAIL", name))
print("SUCCESS:security_digest.selftest" if ok else "FAILED:security_digest.selftest")
sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""Patch 6: (a) mc.silent_on_good_state is boolean-typed - use the provisional
True at pass-A (confirmed/replaced by the real run at pass-B, rollback on any
post-write failure), (b) the bash lane must get a forward-slash repo path."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

a = '''        "fired_on_bad_state": True,
        "silent_on_good_state": None,  # set true after the good-state ACCEPT
        "bad_state_output": outtxt[:400],'''
if a not in t:
    raise SystemExit("anchor A not found")
b = '''        "fired_on_bad_state": True,
        # provisional until the good-state ACCEPT runs moments later; pass-B
        # re-records it from the REAL validator result, rollback on any failure
        "silent_on_good_state": True,
        "bad_state_output": outtxt[:400],'''
t = t.replace(a, b)

a2 = '''    mc["silent_on_good_state"] = None
    receipt["negative_controls"].append(mc)'''
if a2 not in t:
    raise SystemExit("anchor B not found")
b2 = '''    mc["silent_on_good_state"] = True
    receipt["negative_controls"].append(mc)'''
t = t.replace(a2, b2)

a3 = '''    if shell == "pwsh":
        cmd = ["pwsh", "-NoProfile", "-Command",
               "Set-Location '%s'; $env:PYTHONDONTWRITEBYTECODE='1'; python -B %s"
               % (str(REPO), script)]
    else:
        cmd = ["bash", "-c",
               "cd '%s' && PYTHONDONTWRITEBYTECODE=1 python -B %s"
               % (str(REPO), script)]'''
if a3 not in t:
    raise SystemExit("anchor C not found")
b3 = '''    repo_fwd = str(REPO).replace("\\\\", "/")
    if shell == "pwsh":
        cmd = ["pwsh", "-NoProfile", "-Command",
               "Set-Location '%s'; $env:PYTHONDONTWRITEBYTECODE='1'; python -B %s"
               % (repo_fwd, script)]
    else:
        cmd = ["bash", "-c",
               "cd '%s' && PYTHONDONTWRITEBYTECODE=1 python -B %s"
               % (repo_fwd, script)]'''
t = t.replace(a3, b3)

p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK")

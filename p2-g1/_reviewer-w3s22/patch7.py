#!/usr/bin/env python3
"""Patch 7: pin the bash lane to Git Bash explicitly - a bare 'bash' resolves to
C:\Windows\system32\bash.exe (WSL) where C:/... paths do not exist."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

a = '''    repo_fwd = str(REPO).replace("\\\\", "/")
    if shell == "pwsh":'''
if a not in t:
    raise SystemExit("anchor A not found")
b = '''    repo_fwd = str(REPO).replace("\\\\", "/")
    git_bash = r"C:\\Program Files\\Git\\bin\\bash.exe"
    if shell == "pwsh":'''
t = t.replace(a, b)

a2 = '''        cmd = ["bash", "-c",
               "cd '%s' && PYTHONDONTWRITEBYTECODE=1 python -B %s"
               % (repo_fwd, script)]'''
if a2 not in t:
    raise SystemExit("anchor B not found")
b2 = '''        cmd = [git_bash, "-c",
               "cd '%s' && PYTHONDONTWRITEBYTECODE=1 python -B %s"
               % (repo_fwd, script)]'''
t = t.replace(a2, b2)

p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK")

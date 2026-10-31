#!/usr/bin/env python3
"""Patch 9: second-shell output comparison normalizes hex runs of length 8-64
(random per-run throwaway-repo SHAs appear in 40- and 12-hex forms)."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

a = 'norm_p = re.sub(r"\\b[0-9a-f]{40}\\b", "<sha>", out_p)'
if a not in t:
    raise SystemExit("anchor A not found")
b = 'norm_p = re.sub(r"\\b[0-9a-f]{8,64}\\b", "<sha>", out_p)'
t = t.replace(a, b)
a2 = 'norm_b = re.sub(r"\\b[0-9a-f]{40}\\b", "<sha>", out_b)'
if a2 not in t:
    raise SystemExit("anchor B not found")
b2 = 'norm_b = re.sub(r"\\b[0-9a-f]{8,64}\\b", "<sha>", out_b)'
t = t.replace(a2, b2)
p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK")

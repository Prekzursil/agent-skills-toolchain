#!/usr/bin/env python3
"""Surgical fix for the two injected defects in probe2_order_and_slowdown.py.

(1) `case["input_size_bytes"] if False else case["bytes"]` -> `case["bytes"]`
(2) walrus garbage token in the OUT.write_text call -> sort_keys=True

Exact-match, run-once script; asserts both targets present exactly once.
"""
from pathlib import Path

P = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\CNF-0180\probe2_order_and_slowdown.py")

OLD_A = '        "input_size_bytes": case["input_size_bytes"] if False else case["bytes"],\n'
NEW_A = '        "input_size_bytes": case["bytes"],\n'
OLD_C = '    OUT.write_text(json.dumps(doc, indent=2, smallfix_marker := None) + "\\n", encoding="utf-8")\n'
NEW_C = '    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8")\n'

t = P.read_text(encoding="utf-8")
for name, old in (("A", OLD_A), ("C", OLD_C)):
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"FAILED:defect-fix target {name} found {n} times (want 1)")
t = t.replace(OLD_A, NEW_A).replace(OLD_C, NEW_C)
P.write_text(t, encoding="utf-8")
import ast

ast.parse(t)
print("SUCCESS:defect-fix both defects patched, syntax OK")

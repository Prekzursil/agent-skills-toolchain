#!/usr/bin/env python3
"""Patch 5: sentinel consistency compares SUCCESS:<uid>-probeN PREFIXES (numbers
inside the line vary per run); a full-line containment check would false-negative."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

old = '''    builder_sentinels = {}
    for np in CUR_CTX["ret"].get("named_probes", []):
        m = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
        if m:
            builder_sentinels[m[-1]] = [
                ln for ln in (np.get("raw_output") or "").splitlines()
                if ln.startswith("SUCCESS:")]'''
if old not in t:
    raise SystemExit("anchor A not found")
new = '''    builder_sentinels = {}
    for np in CUR_CTX["ret"].get("named_probes", []):
        m = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
        if m:
            builder_sentinels[m[-1]] = [
                ln.split()[0] for ln in (np.get("raw_output") or "").splitlines()
                if ln.startswith("SUCCESS:")]'''
t = t.replace(old, new)

old2 = '''        consistent = all(
            any(bs in probe_outs[s][-1] for bs in builder_sentinels.get(s, ["__none__"]))
            or not builder_sentinels.get(s)
            for s in scripts if s in probe_outs)'''
if old2 not in t:
    raise SystemExit("anchor B not found")
new2 = '''        def live_prefixes(s: str) -> set:
            return {ln.split()[0] for ln in probe_outs.get(s, [""])[-1].splitlines()
                    if ln.startswith("SUCCESS:")}

        consistent = all(
            (live_prefixes(s) & set(builder_sentinels.get(s, [])))
            or not builder_sentinels.get(s)
            for s in scripts if s in probe_outs)'''
t = t.replace(old2, new2)
p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK")

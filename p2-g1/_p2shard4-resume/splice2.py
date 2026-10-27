"""Splice region.txt into finalize() and helpers.txt over the old _valid_dc_row."""
from pathlib import Path
import ast

base = Path.home() / "p2-g1" / "_p2shard4-resume" / "parts"
lib = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1" / "lib_shard4.py"
t = lib.read_text(encoding="utf-8")

# 1) replace finalize stash region
start = t.index("    # Resume 2026-10-24: legacy rows in pre-resume shapes")
end = t.index("    # preserve prior test/probe/control rows as history; live rows replace them")
region = (base / "region.txt").read_text(encoding="utf-8")
if not region.endswith("\n"):
    region += "\n"
t = t[:start] + region + t[end:]

# 2) replace old _valid_dc_row .. def finalize( with helpers + def finalize(
hstart = t.index("def _valid_dc_row(r: dict) -> bool:")
hend = t.index("def finalize(")
helpers = (base / "helpers.txt").read_text(encoding="utf-8")
t = t[:hstart] + helpers + "\n\n" + t[hend:]

lib.write_text(t, encoding="utf-8", newline="\n")
ast.parse(t)
print("splice2 OK; syntax valid")

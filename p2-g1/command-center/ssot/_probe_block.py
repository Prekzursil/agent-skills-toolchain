"""Throwaway probe: dump the exact bytes of the SSOT-WIRE block in CLAUDE.md so the
count regexes anchor on what is really there, not on a context-window paraphrase.
Read-only.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

START = "<!-- SSOT-WIRE:start -->"
END = "<!-- SSOT-WIRE:end -->"
i, j = text.find(START), text.find(END)
print(f"start={i} end={j}")
if i < 0 or j < 0:
    print("BLOCK MARKERS ABSENT")
    sys.exit(1)
block = text[i + len(START) : j]
print(f"block chars={len(block)}")
print("--- repr of every line carrying a digit ---")
for n, line in enumerate(block.split("\n")):
    if re.search(r"\d", line):
        print(f"{n:3d} {line!r}")
print("--- integers in block order ---")
print([m.group(0) for m in re.finditer(r"\d+", block)])

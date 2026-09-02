#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parents[1] / "probes"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-08.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
SNIP_RE = re.compile(r"find_line\(\s*([^\n,]+),\s*(['\"])(.+?)\2", re.S)
PATH_RE = re.compile(r'(DETECTOR|THRESH|PART|WF|SUPPORTING|TAXONOMY|LIB|GATE|MOD)\s*=\s*"([^"]+)"')
REL_RE = re.compile(r'"(tools/[^"]+\.py|command-center/[^"]+\.py)"')

for uid in IDS:
    pdir = PROBES / uid
    texts = []
    for p in sorted(pdir.glob("*.py")):
        if p.name.startswith("probe"):
            continue
        texts.append((p.name, p.read_text(encoding="utf-8", errors="replace")))
    snips = []
    paths = []
    for name, text in texts:
        for m in SNIP_RE.finditer(text):
            snips.append((name, m.group(1).strip(), m.group(3)[:120]))
        for m in PATH_RE.finditer(text):
            paths.append((name, m.group(1), m.group(2)))
        for m in REL_RE.finditer(text):
            if "p2-wave/probes" not in m.group(1):
                paths.append((name, "rel", m.group(1)))
    if snips or paths:
        print(f"\n## {uid}")
        for row in paths[:20]:
            print(" path", row)
        for row in snips[:20]:
            print(" snip", row)

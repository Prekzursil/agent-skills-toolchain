"""Targeted read-only scan of claude.exe for the Workflow runtime API surface:
does the runner inject pipeline()? what other globals / options does it document?
Prints JSON with de-duplicated context windows."""

import json
import re
from pathlib import Path

BIN = Path(r"C:/Users/Prekzursil/.local/bin/claude.exe")
CHUNK = 8 << 20
OVERLAP = 8192

PATS = {
    "agent_parallel_pipeline_phase": re.compile(
        rb"agent\(\)/parallel\(\)/pipeline\(\)/phase\(\)"
    ),
    "pipeline_paren": re.compile(rb"pipeline\("),
    "workflow_api_doc": re.compile(rb"parallel\(thunks|parallel\(\[|thunks"),
    "isolation_worktree": re.compile(rb"isolation.{0,20}worktree"),
    "maxConcurrency": re.compile(rb"maxConcurrenc|concurrency"),
}

hits = {k: [] for k in PATS}
counts = {k: 0 for k in PATS}
seen = {k: set() for k in PATS}

with BIN.open("rb") as fh:
    prev = b""
    pos = 0
    while True:
        buf = fh.read(CHUNK)
        if not buf:
            break
        data = prev + buf
        base = pos - len(prev)
        for name, rx in PATS.items():
            for m in rx.finditer(data):
                counts[name] += 1
                if len(hits[name]) >= 6:
                    continue
                s = max(0, m.start() - 700)
                e = min(len(data), m.end() + 900)
                ctx = data[s:e].decode("utf-8", "replace")
                # keep only printable-dense windows (skip binary noise)
                printable = sum(1 for c in ctx if 32 <= ord(c) < 127 or c in "\n\t")
                if printable / max(1, len(ctx)) < 0.85:
                    continue
                key = ctx[300:500]
                if key in seen[name]:
                    continue
                seen[name].add(key)
                hits[name].append({"offset": base + m.start(), "ctx": ctx})
        pos += len(buf)
        prev = data[-OVERLAP:]

print(json.dumps({"counts": counts, "hits": hits}, indent=2))

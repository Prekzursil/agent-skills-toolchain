"""Find the Workflow sandbox's global-injection site in claude.exe: the code that
throws on Date.now()/Math.random() should sit next to the list of globals handed to
the script body. Read-only, chunked."""

import json
import re
from pathlib import Path

BIN = Path(r"C:/Users/Prekzursil/.local/bin/claude.exe")
CHUNK = 8 << 20
OVERLAP = 8192

PATS = {
    "date_now_unavailable": re.compile(
        rb"Date\.now\(\)[^\"'`]{0,80}(unavailable|not available|banned|disabled)", re.I
    ),
    "would_break_resume": re.compile(rb"break resume|breaks resume", re.I),
    "workflow_sandbox_globals": re.compile(
        rb"\bphase\b[^{}]{0,60}\blog\b[^{}]{0,60}\bbudget\b"
    ),
    "new_AsyncFunction_globals": re.compile(
        rb"AsyncFunction\)\(|new\s+\w{1,3}\(\"agent\""
    ),
    "settimeout_unavailable": re.compile(
        rb"setTimeout[^\"'`\n]{0,60}(unavailable|not available|is not defined)", re.I
    ),
}

hits = {k: [] for k in PATS}
counts = {k: 0 for k in PATS}

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
                if len(hits[name]) >= 4:
                    continue
                s = max(0, m.start() - 900)
                e = min(len(data), m.end() + 900)
                ctx = data[s:e].decode("utf-8", "replace")
                printable = sum(1 for c in ctx if 32 <= ord(c) < 127 or c in "\n\t")
                if printable / max(1, len(ctx)) < 0.85:
                    continue
                hits[name].append({"offset": base + m.start(), "ctx": ctx})
        pos += len(buf)
        prev = data[-OVERLAP:]

print(json.dumps({"counts": counts, "hits": hits}, indent=2))

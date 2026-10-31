"""Read-only scan of the bundled claude binary for the Workflow-runner source, to
answer: which globals does the runner inject into a saved workflow body?
Chunked so it never holds the 287 MB file in RAM. Prints JSON."""

import json
import re
from pathlib import Path

BIN = Path(r"C:/Users/Prekzursil/.local/bin/claude.exe")
CHUNK = 8 << 20
OVERLAP = 4096

# Patterns that would appear in the runner's function-constructor / wrapper.
PATS = {
    # the injected-globals triple, in either quote style, any order-ish
    "triple_agent_parallel_phase": re.compile(
        rb"""["'`]agent["'`]\s*,\s*["'`]parallel["'`]\s*,\s*["'`]phase["'`]"""
    ),
    "AsyncFunction_ctor": re.compile(rb"AsyncFunction"),
    "workflows_dir_literal": re.compile(rb"\.claude[/\\]{1,2}workflows"),
    "workflow_meta_export": re.compile(rb"export const meta"),
    "setTimeout_ident": re.compile(rb"\bsetTimeout\b"),
    "no_timeout_msg": re.compile(rb"per-agent timeout", re.I),
}

counts = {k: 0 for k in PATS}
samples = {k: [] for k in PATS}

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
                if len(samples[name]) < 3:
                    s = max(0, m.start() - 240)
                    e = min(len(data), m.end() + 240)
                    samples[name].append(
                        {
                            "offset": base + m.start(),
                            "ctx": data[s:e].decode("utf-8", "replace"),
                        }
                    )
        pos += len(buf)
        prev = data[-OVERLAP:]

print(
    json.dumps(
        {"file_bytes": BIN.stat().st_size, "counts": counts, "samples": samples},
        indent=2,
    )[:12000]
)

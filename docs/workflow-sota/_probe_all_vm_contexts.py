"""Find EVERY vm.createContext site in claude.exe whose sandbox literal mentions
budget/agent/parallel, to check whether the TOP-LEVEL workflow path (not just the
child workflow() path) also injects setTimeout/clearTimeout. Read-only."""
import json
import re
from pathlib import Path

BIN = Path(r"C:/Users/Prekzursil/.local/bin/claude.exe")
CHUNK = 8 << 20
OVERLAP = 16384

RX = re.compile(rb"createContext\(")

rows = []
with BIN.open("rb") as fh:
    prev = b""
    pos = 0
    while True:
        buf = fh.read(CHUNK)
        if not buf:
            break
        data = prev + buf
        base = pos - len(prev)
        for m in RX.finditer(data):
            s = max(0, m.start() - 1600)
            e = min(len(data), m.end() + 400)
            ctx = data[s:e].decode("utf-8", "replace")
            printable = sum(1 for c in ctx if 32 <= ord(c) < 127 or c in "\n\t")
            if printable / max(1, len(ctx)) < 0.9:
                continue
            rows.append(
                {
                    "offset": base + m.start(),
                    "has_budget": "budget:" in ctx,
                    "has_setTimeout": "setTimeout:" in ctx,
                    "has_clearTimeout": "clearTimeout:" in ctx,
                    "has_log": "log:" in ctx,
                    "has_phase": "phase:" in ctx,
                    "has_pipeline": "pipeline" in ctx,
                    "tail": ctx[-1100:],
                }
            )
        pos += len(buf)
        prev = data[-OVERLAP:]

# de-dup by offset proximity
seen = set()
uniq = []
for r in sorted(rows, key=lambda r: r["offset"]):
    k = r["offset"] // 64
    if k in seen:
        continue
    seen.add(k)
    uniq.append(r)

print(f"createContext sites (printable): {len(uniq)}")
for r in uniq:
    print(
        f"@{r['offset']} budget={r['has_budget']} setTimeout={r['has_setTimeout']} "
        f"clearTimeout={r['has_clearTimeout']} log={r['has_log']} phase={r['has_phase']} "
        f"pipeline={r['has_pipeline']}"
    )
interesting = [r for r in uniq if r["has_budget"] or r["has_setTimeout"]]
print("\n=== interesting sandboxes ===")
for r in interesting:
    print(f"--- @{r['offset']}")
    print(r["tail"])

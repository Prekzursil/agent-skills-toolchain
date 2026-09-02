#!/usr/bin/env python3
from pathlib import Path

HERE = Path(__file__).resolve().parent
log = (HERE / "_shard11_measure.log").read_text(encoding="utf-8", errors="replace")
rem = [ln.strip() for ln in (HERE / "shard-11.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
chunks = {}
cur = None
buf = []
for ln in log.splitlines():
    if ln.startswith("==== "):
        if cur:
            chunks[cur] = buf
        parts = ln.split()
        cur = parts[1] if len(parts) > 1 else None
        buf = [ln]
    else:
        buf.append(ln)
if cur:
    chunks[cur] = buf
for uid in rem:
    body = chunks.get(uid) or []
    interesting = []
    for x in body:
        s = x.strip()
        if not s:
            continue
        if s.startswith("FAILED:delivered"):
            continue
        if (
            s.startswith("FAILED:")
            or "Error:" in s
            or s.startswith("AttributeError")
            or s.startswith("ImportError")
            or s.startswith("ModuleNotFound")
            or s.startswith("TypeError")
            or s.startswith("ValueError")
            or s.startswith("KeyError")
            or s.startswith("FileNotFound")
            or s.startswith("StopIteration")
        ):
            interesting.append(s[:220])
    last = interesting[-1] if interesting else (body[-4].strip()[:220] if len(body) >= 4 else "NO-DETAIL")
    print(f"{uid}\t{last}")

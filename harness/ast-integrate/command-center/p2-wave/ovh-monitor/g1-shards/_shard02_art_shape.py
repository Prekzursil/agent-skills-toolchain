#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
dump = json.loads(Path(__file__).with_name("_shard02_dump.json").read_text(encoding="utf-8"))
lines = []
for r in dump:
    rel = r.get("output_path") or ""
    path = REPO / rel
    if not path.is_file():
        lines.append(f"{r['id']} MISSING {rel}")
        continue
    raw = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except Exception as exc:
        lines.append(f"{r['id']} UNPARSEABLE {type(exc).__name__}")
        continue
    tests = doc.get("tests")
    ttype = type(tests).__name__
    extra = ""
    if isinstance(tests, dict):
        extra = f" keys={list(tests)[:12]}"
    elif isinstance(tests, list):
        extra = f" n={len(tests)} first={tests[0] if tests else None}"
    st = doc.get("state")
    sent = (r.get("sentinel") or "")
    sent_ok = bool(sent) and sent in raw
    lines.append(
        f"{r['id']} state={st} tests={ttype}{extra} sentinel_in={sent_ok} sentinel={sent!r}"
    )
dest = Path(__file__).with_name("_shard02_art_shape.txt")
dest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {dest}")

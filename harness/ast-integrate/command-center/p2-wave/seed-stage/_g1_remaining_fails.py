#!/usr/bin/env python3
"""Emit remaining-fail IDs: latest g1-local-full.jsonl overlaid with repair-claude/*.jsonl.

02.09 cloud adaptation: paths come from _g1_paths (Windows mirror when present,
else the repo tree this file lives in).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import latest_rows  # noqa: E402

latest = latest_rows()

fails = sorted(uid for uid, rec in latest.items() if not rec.get("ok"))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
text = "\n".join(fails) + "\n"
if out:
    out.write_text(text, encoding="utf-8")
print(f"total={len(latest)} fails={len(fails)}", file=sys.stderr)
if not out:
    sys.stdout.write(text)

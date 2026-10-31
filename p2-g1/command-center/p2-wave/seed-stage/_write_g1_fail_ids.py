#!/usr/bin/env python3
"""Write leftover remaining_ids from the last local G-1 jsonl fails."""
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
OUT = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"


def main() -> int:
    fails: list[str] = []
    oks: list[str] = []
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if not uid:
                continue
            if rec.get("ok"):
                oks.append(uid)
            else:
                fails.append(uid)
    payload = {
        "ts": "2026-08-25T05:13:02Z",
        "source": "g1-local-full.jsonl",
        "ok_n": len(oks),
        "remaining_ids": fails,
        "n": len(fails),
        "note": "G-1 fail IDs only. Dispatcher must NOT skip because output_path exists.",
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": len(oks), "fail": len(fails), "out": str(OUT)}), flush=True)
    return 0 if fails else 1


if __name__ == "__main__":
    raise SystemExit(main())

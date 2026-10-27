#!/usr/bin/env python3
"""Split G-1 fail IDs into N equal shards (default 24)."""
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
OUT = WAVE / "ovh-monitor" / "g1-shards"
N = 24


def main() -> int:
    ids: list[str] = []
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("id") and not rec.get("ok"):
                ids.append(rec["id"])
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(N):
        (OUT / f"shard-{i:02d}.txt").write_text("", encoding="utf-8")
    for i, uid in enumerate(ids):
        p = OUT / f"shard-{i % N:02d}.txt"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(uid + "\n")
    sizes = [sum(1 for _ in (OUT / f"shard-{i:02d}.txt").read_text(encoding="utf-8").splitlines() if _) for i in range(N)]
    rec = {"n_ids": len(ids), "n_shards": N, "sizes": sizes, "dir": str(OUT)}
    (OUT / "manifest.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

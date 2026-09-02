#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

MON = Path(__file__).resolve().parents[1]
WAVE = MON.parent
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-01.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
want = set(IDS)

sources = [
    MON / "g1-local-full.jsonl",
    MON / "g1-fails-rerun.jsonl",
    MON / "g1-shards" / "class-other.measure.jsonl",
]


def load_jsonl(path: Path) -> dict:
    out = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = rec.get("id")
            if uid in want:
                out[uid] = rec
    return out


def main() -> None:
    merged = {uid: {"id": uid} for uid in IDS}
    for src in sources:
        data = load_jsonl(src)
        print(f"{src.name}: hits={len(data)}")
        for uid, rec in data.items():
            merged[uid][src.name] = {
                "ok": rec.get("ok"),
                "rc": rec.get("rc"),
                "line": rec.get("line"),
                "cls": rec.get("cls"),
                "tail": (rec.get("tail") or rec.get("line") or "")[-1500:],
            }
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard01_fails.json"
    dest.write_text(json.dumps([merged[i] for i in IDS], indent=2), encoding="utf-8")
    for uid in IDS:
        rec = merged[uid]
        # prefer rerun
        src = rec.get("g1-fails-rerun.jsonl") or rec.get("g1-local-full.jsonl") or {}
        print(f"{uid:10} {src.get('cls','?'):22} {(src.get('line') or '')[:90]}")
    print("wrote", dest)


if __name__ == "__main__":
    main()

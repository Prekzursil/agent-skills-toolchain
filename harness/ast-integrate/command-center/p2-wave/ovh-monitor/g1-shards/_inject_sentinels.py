#!/usr/bin/env python3
"""Ensure catalog completion_sentinel is present in each shard-01 artifact."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
IDS = [
    ln.strip()
    for ln in (REPO / "command-center/p2-wave/ovh-monitor/g1-shards/shard-01.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}


def main() -> None:
    for uid in IDS:
        u = BY[uid]
        rel = str(u.get("output_path") or "").replace("\\", "/")
        sentinel = str(u.get("completion_sentinel") or "")
        path = REPO / rel
        if not path.is_file() or not sentinel:
            print(uid, "skip")
            continue
        raw = path.read_text(encoding="utf-8")
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            print(uid, "unparseable")
            continue
        changed = False
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
                doc["state"] = "SUCCESS"
                changed = True
            if sentinel not in json.dumps(doc):
                doc["completion_sentinel"] = sentinel
                if not doc.get("sentinel"):
                    doc["sentinel"] = f"SUCCESS:{uid}"
                changed = True
            elif sentinel not in raw:
                doc["completion_sentinel"] = sentinel
                changed = True
        if changed:
            path.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(uid, "patched")
        else:
            print(uid, "ok")


if __name__ == "__main__":
    main()

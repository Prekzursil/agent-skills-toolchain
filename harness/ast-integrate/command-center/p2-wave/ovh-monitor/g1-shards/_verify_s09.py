#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SHARD = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (SHARD / "shard-09.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
JSONLS = [
    SHARD / "_shard09_measure.jsonl",
    SHARD / "_shard09_remeasure.jsonl",
]


def load_latest() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for p in JSONLS:
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            rec = json.loads(ln)
            uid = rec.get("id")
            if uid:
                latest[uid] = rec
    return latest


def fail_key(rec: dict) -> str:
    tail = rec.get("tail") or ""
    last = rec.get("last") or ""
    for line in reversed(str(tail).splitlines()):
        s = line.strip()
        if s.startswith("FAILED:") or "Error" in s or "TIMEOUT" in s or "ModuleNotFound" in s or "AttributeError" in s or "ImportError" in s or "KeyError" in s or "TypeError" in s:
            return s[:240]
    return last[:240]


def main() -> None:
    latest = load_latest()
    rows = []
    for uid in IDS:
        rec = latest.get(uid) or {}
        rows.append(
            {
                "id": uid,
                "ok": bool(rec.get("ok")),
                "last": rec.get("last"),
                "fail": None if rec.get("ok") else fail_key(rec),
                "in_jsonl": uid in latest,
            }
        )
    ok = [r["id"] for r in rows if r["ok"]]
    fail = [r for r in rows if not r["ok"]]
    missing = [r["id"] for r in rows if not r["in_jsonl"]]
    out = {
        "n": len(IDS),
        "jsonl_ok": ok,
        "jsonl_ok_n": len(ok),
        "jsonl_fail_n": len(fail),
        "missing_from_jsonl": missing,
        "fails": [{"id": r["id"], "fail": r["fail"], "last": r["last"]} for r in fail],
    }
    dest = SHARD / "_shard09_latest.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok_n": len(ok), "fail_n": len(fail), "ok": ok, "missing": missing}, indent=2))


if __name__ == "__main__":
    main()

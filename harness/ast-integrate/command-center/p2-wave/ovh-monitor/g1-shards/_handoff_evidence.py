#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

SHARDS = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave"
    r"\ovh-monitor\g1-shards"
)
JSONL = SHARDS / "class-envelope.measure.jsonl"
REMAINING = SHARDS / "class-predicate.remaining.txt"

WANT = [
    "CC-0009",
    "CNF-0004",
    "RES-0079",
    "ARC-0007",
    "ARC-0095",
    "CNF-0001",
    "CNF-0154",
    "RES-0014",
    "SYN-0016",
    "TST-0003",
    "TST-0080",
    "SYN-0005",
    "ADV-0005",
]
FAIL_SAMPLES = [
    "ADV-0003",
    "ADV-0028",
    "ADV-0009",
    "AUD-0087",
    "RES-0001",
    "TST-0144",
    "TST-0247",
]


def main() -> None:
    rows = [json.loads(ln) for ln in JSONL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    by = {r["id"]: r for r in rows}
    print("jsonl_n", len(rows), "unique", len(by))
    print("ok", sum(1 for r in rows if r.get("ok")), "fail", sum(1 for r in rows if not r.get("ok")))
    print("cls", Counter(r.get("cls") for r in rows))
    print("--- specials ---")
    for uid in WANT:
        r = by.get(uid) or {}
        print(uid, "ok=", r.get("ok"), "cls=", r.get("cls"), "line=", (r.get("line") or "")[:80])
    print("--- fail samples ---")
    for uid in FAIL_SAMPLES:
        r = by.get(uid) or {}
        print(uid, "cls=", r.get("cls"))
        print("  line", (r.get("line") or "")[:160])
        tail = (r.get("tail") or "")[-280:].replace("\n", " | ")
        print("  tail", tail)
    rem = [ln.strip() for ln in REMAINING.read_text(encoding="utf-8").splitlines() if ln.strip()]
    raw = REMAINING.read_bytes()
    print("remaining_n", len(rem), "fp", hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())
    missing = [u for u in rem if u not in by or by[u].get("ok")]
    print("remaining_not_fail_in_jsonl", missing[:8], "n", len(missing))
    unmeasured = [r["id"] for r in rows if r["id"] not in by]
    print("unmeasured_in_jsonl_dup_check", len(rows) - len(by))


if __name__ == "__main__":
    main()

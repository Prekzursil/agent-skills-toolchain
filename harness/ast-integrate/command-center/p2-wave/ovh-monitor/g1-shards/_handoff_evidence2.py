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


def ids(name: str) -> list[str]:
    p = SHARDS / name
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    pred = ids("class-predicate.txt")
    sha = ids("class-sha.txt")
    sent = ids("class-sentinel.txt")
    outp = ids("class-output.txt")
    assigned = []
    seen = set()
    for group in (pred, sha, sent, outp):
        for u in group:
            if u not in seen:
                assigned.append(u)
                seen.add(u)
    rows = [
        json.loads(ln)
        for ln in (SHARDS / "class-envelope.measure.jsonl").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    by = {r["id"]: r for r in rows}
    ok_ids = sorted(r["id"] for r in rows if r.get("ok"))
    fail_ids = [r["id"] for r in rows if not r.get("ok")]
    rem = [ln.strip() for ln in (SHARDS / "class-predicate.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    print("assigned", len(assigned), "pred", len(pred), "sha", len(sha), "sent", len(sent), "out", len(outp))
    print("jsonl", len(rows), "unique", len(by), "ok", len(ok_ids), "fail", len(fail_ids))
    missing = [u for u in assigned if u not in by]
    extra = [u for u in by if u not in seen]
    print("assigned_not_in_jsonl", missing)
    print("jsonl_not_assigned", extra)
    print("remaining_eq_fail", rem == sorted(fail_ids) or set(rem) == set(fail_ids), "rem_n", len(rem), "fail_n", len(fail_ids))
    print("remaining_sorted_match", rem == fail_ids)
    print("ok_ids", " ".join(ok_ids))
    print("ok_by_prefix", dict(Counter(u.split("-")[0] for u in ok_ids)))
    print("fail_by_prefix", dict(Counter(u.split("-")[0] for r in rows if not r.get("ok") for u in [r["id"]])))
    print("fail_cls_by_prefix")
    c = Counter()
    for r in rows:
        if not r.get("ok"):
            c[(r["id"].split("-")[0], r.get("cls"))] += 1
    for k, n in sorted(c.items()):
        print(" ", k, n)
    print("SUCCESS_LINES")
    for uid in pred + sha + outp:
        r = by[uid]
        print(" ", r.get("line"))
    # hash remaining as written
    raw = (SHARDS / "class-predicate.remaining.txt").read_bytes()
    print("remaining_bytes", len(raw), "sha256", hashlib.sha256(raw).hexdigest())
    print("remaining_lf_sha", hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())


if __name__ == "__main__":
    main()

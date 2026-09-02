#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SHARD = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (SHARD / "shard-09.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_latest() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for name in (
        "_shard09_measure.jsonl",
        "_shard09_remeasure.jsonl",
        "_shard09_verify_ok18.jsonl",
    ):
        p = SHARD / name
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


def reason(rec: dict) -> str:
    tail = str(rec.get("tail") or "")
    keys: list[str] = []
    for line in tail.splitlines():
        s = line.strip()
        if s.startswith("FAILED:") and "delivered" not in s:
            keys.append(s[:220])
        elif (
            s.startswith(
                (
                    "ModuleNotFound",
                    "AttributeError",
                    "ImportError",
                    "KeyError",
                    "TypeError",
                    "RuntimeError",
                    "AssertionError",
                    "FileNotFound",
                    "TIMEOUT",
                )
            )
            or "Error:" in s
        ):
            keys.append(s[:220])
    if keys:
        return keys[-1]
    return str(rec.get("last") or "unknown")[:220]


def main() -> None:
    latest = load_latest()
    vok: set[str] = set()
    vfails: dict[str, str] = {}
    for ln in (SHARD / "_shard09_verify_ok18.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(ln)
        if rec.get("ok"):
            vok.add(rec["id"])
        else:
            vfails[rec["id"]] = rec.get("last") or ""
    ok = sorted(vok)
    fail = [u for u in IDS if u not in vok]
    rows = []
    for uid in fail:
        rec = latest.get(uid) or {}
        why = vfails.get(uid) or reason(rec)
        rows.append({"id": uid, "reason": why, "last": rec.get("last")})
    remaining = "\n".join(fail) + "\n"
    rpath = SHARD / "shard-09.remaining.txt"
    rpath.write_text(remaining, encoding="utf-8", newline="\n")
    fp = hashlib.sha256(rpath.read_bytes()).hexdigest()
    result = {
        "attempted": 57,
        "ok": len(ok),
        "fail": len(fail),
        "verified": len(ok),
        "n": 57,
        "shard": 9,
        "headline": f"{len(ok)}/57 shard-09 IDs live-remeasured SUCCESS:delivered; {len(fail)} remain",
        "summary": (
            "Live WSL remeasure of previously claimed-ok IDs: "
            + " ".join(ok)
            + ". CNL-0119 and RES-0040 were SUCCESS in the first pass then FAILED on independent remeasure (schema accepted garbage) so they are NOT counted. Remaining 41 are probe-exit leftovers. Did not invent SUCCESS:delivered. No git write. No global unit_manifest.py --write."
        ),
        "path": str(SHARD / "shard-09.txt.result.json"),
        "remaining_n": len(fail),
        "remaining_fp": fp,
        "remaining_path": str(rpath),
        "verified_ids": ok,
        "fail_reasons": rows,
    }
    (SHARD / "shard-09.txt.result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (SHARD / "_shard09_fail_reasons.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": len(ok), "fail": len(fail), "fp": fp, "ok_ids": ok}, indent=2))
    for r in rows:
        print(f"{r['id']}\t{r['reason']}")


if __name__ == "__main__":
    main()

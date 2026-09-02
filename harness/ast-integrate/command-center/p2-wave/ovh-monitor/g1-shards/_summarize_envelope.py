#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

SH = Path(__file__).resolve().parent
MOD_RE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
FILE_RE = re.compile(r"No such file or directory: ['\"]([^'\"]+)['\"]")


def assigned() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        p = SH / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
    return out


def main() -> int:
    ids = assigned()
    rows: dict[str, dict] = {}
    jl = SH / "class-envelope.measure.jsonl"
    if not jl.is_file():
        jl = SH / "class-other.measure.jsonl"
    for ln in jl.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        rows[rec["id"]] = rec
    ok = fail = miss = 0
    cls: Counter[str] = Counter()
    mods: Counter[str] = Counter()
    files: Counter[str] = Counter()
    fail_ids: list[str] = []
    samples: dict[str, list] = {}
    for uid in ids:
        rec = rows.get(uid)
        if rec is None:
            miss += 1
            fail += 1
            fail_ids.append(uid)
            cls["UNMEASURED"] += 1
            continue
        if rec.get("ok"):
            ok += 1
            cls["SUCCESS"] += 1
            continue
        fail += 1
        fail_ids.append(uid)
        c = rec.get("cls") or "?"
        cls[c] += 1
        tail = rec.get("tail") or ""
        for m in MOD_RE.findall(tail):
            mods[m] += 1
        for m in FILE_RE.findall(tail):
            files[m] += 1
        samples.setdefault(c, []).append({"id": uid, "line": rec.get("line"), "tail": tail[-500:]})
    payload = {
        "assigned": len(ids),
        "ok": ok,
        "fail": fail,
        "unmeasured": miss,
        "jsonl": str(jl),
        "classes": dict(cls),
        "mods": dict(mods.most_common()),
        "files": dict(files.most_common(40)),
        "fail_ids": fail_ids,
        "samples": {k: v[:8] for k, v in samples.items()},
    }
    (SH / "class-other.pass1.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (SH / "class-other.fail-ids.txt").write_text("\n".join(fail_ids) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("assigned", "ok", "fail", "unmeasured", "classes", "mods", "files")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

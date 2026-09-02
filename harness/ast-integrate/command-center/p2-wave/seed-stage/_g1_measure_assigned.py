#!/usr/bin/env python3
"""Measure envelope-rest G-1 IDs. Must run under WSL with AST_INTEGRATE_ROOT set."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

STAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE))
import g1_remeasure_all as G  # noqa: E402

WIN_SHARDS = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
SHARDS = WIN_SHARDS if WIN_SHARDS.exists() else (G.WAVE / "ovh-monitor" / "g1-shards")
JSONL = SHARDS / "class-envelope.measure.jsonl"
HEART = SHARDS / "class-envelope.heartbeat.json"
SUMMARY = SHARDS / "class-envelope.measure.json"


def assigned_ids() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in (
        "class-predicate.txt",
        "class-sha.txt",
        "class-sentinel.txt",
        "class-output.txt",
        "class-other.txt",
    ):
        p = SHARDS / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
    return out


def main() -> int:
    os.chdir(str(G.REPO))
    os.environ["AST_INTEGRATE_ROOT"] = str(G.REPO)
    ids = assigned_ids()
    fail_file = os.environ.get("G1_FAILS_FILE", "").strip()
    only = [a.strip().replace("\r", "") for a in sys.argv[1:] if a.strip().replace("\r", "")]
    if fail_file:
        fp = Path(fail_file)
        if fp.is_file():
            only = [ln.strip().replace("\r", "") for ln in fp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    global JSONL, HEART, SUMMARY
    if only:
        ids = [u for u in ids if u in set(only)]
        if not ids:
            ids = list(only)
        JSONL = SHARDS / "class-envelope.pass2.jsonl"
        HEART = SHARDS / "class-envelope.pass2.heartbeat.json"
        SUMMARY = SHARDS / "class-envelope.pass2.json"
    workers = int(os.environ.get("G1_WORKERS", "8"))
    print(f"MEASURE n={len(ids)} workers={workers} repo={G.REPO} jsonl={JSONL}", flush=True)
    JSONL.write_text("", encoding="utf-8")
    n = len(ids)
    started = time.time()
    ok = fail = done = 0
    classes: Counter[str] = Counter()
    fail_ids: list[str] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=G._init_worker) as pool:
        futs = {pool.submit(G.one, uid): uid for uid in ids}
        for fut in as_completed(futs):
            rec = fut.result()
            done += 1
            classes[rec["cls"]] += 1
            if rec.get("ok"):
                ok += 1
            else:
                fail += 1
                fail_ids.append(rec["id"])
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"{done}/{n} ok={ok} fail={fail} {rec['id']} {rec['cls']}", flush=True)
            if done % 5 == 0 or done == n:
                HEART.write_text(
                    json.dumps(
                        {
                            "ts": G.utc_now(),
                            "done": done,
                            "n": n,
                            "ok": ok,
                            "fail": fail,
                            "elapsed_s": int(time.time() - started),
                            "classes": dict(classes.most_common(16)),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
    summary = {
        "ts": G.utc_now(),
        "n": n,
        "ok": ok,
        "fail": fail,
        "elapsed_s": int(time.time() - started),
        "classes": dict(classes),
        "fail_ids": sorted(fail_ids),
        "repo": str(G.REPO),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n", "ok", "fail", "elapsed_s", "classes")}, indent=2), flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

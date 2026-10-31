#!/usr/bin/env python3
"""Remesure only G-1 fail IDs from g1-local-full.jsonl."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STAGE = Path(__file__).resolve().parent
# reuse g1_remeasure_all workers
sys.path.insert(0, str(STAGE))
import g1_remeasure_all as G  # noqa: E402

JSONL_IN = G.OUT_DIR / "g1-local-full.jsonl"
JSONL = G.OUT_DIR / "g1-fails-rerun.jsonl"
SUMMARY = G.OUT_DIR / "g1-fails-rerun.json"
HEART = G.OUT_DIR / "g1-fails-heartbeat.json"
G.JSONL = JSONL
G.SUMMARY = SUMMARY
G.HEART = HEART


def main() -> int:
    ids = []
    with JSONL_IN.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("id") and not rec.get("ok"):
                ids.append(rec["id"])
    print(f"G1-FAILS n={len(ids)} workers={G.WORKERS}", flush=True)
    # monkeypatch catalog ids by wrapping main pieces
    os.chdir(str(G.REPO))
    os.environ["AST_INTEGRATE_ROOT"] = str(G.REPO)
    JSONL.write_text("", encoding="utf-8")
    from collections import Counter
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import time

    n = len(ids)
    started = time.time()
    ok = fail = done = 0
    classes: Counter[str] = Counter()
    fail_ids: list[str] = []
    with ProcessPoolExecutor(max_workers=G.WORKERS, initializer=G._init_worker) as pool:
        futs = {pool.submit(G.one, uid): uid for uid in ids}
        for fut in as_completed(futs):
            rec = fut.result()
            done += 1
            classes[rec["cls"]] += 1
            if rec["ok"]:
                ok += 1
            else:
                fail += 1
                fail_ids.append(rec["id"])
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"{done}/{n} ok={ok} fail={fail} {rec['id']} {rec['cls']}", flush=True)
            if done % 10 == 0 or done == n:
                HEART.write_text(
                    json.dumps(
                        {
                            "ts": G.utc_now(),
                            "done": done,
                            "n": n,
                            "ok": ok,
                            "fail": fail,
                            "elapsed_s": int(time.time() - started),
                            "classes": dict(classes.most_common(12)),
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
        "classes": dict(classes.most_common()),
        "fail_n": len(fail_ids),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

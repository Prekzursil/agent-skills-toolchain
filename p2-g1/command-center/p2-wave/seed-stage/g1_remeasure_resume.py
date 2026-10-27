#!/usr/bin/env python3
"""Resume a killed g1_remeasure_all run: measure catalog IDs missing from jsonl.

Does NOT wipe g1-local-full.jsonl. Appends remaining rows, then writes summary
from the full jsonl (latest row per id). Run from $HOME/p2-g1 so REPO is POSIX.
"""
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


def load_rows() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not G.JSONL.is_file():
        return out
    with G.JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if uid:
                out[uid] = rec
    return out


def write_summary(rows: dict[str, dict], catalog: list[str], elapsed_s: int, extra_fail: list[str]) -> dict:
    classes: Counter[str] = Counter()
    ok = fail = 0
    fail_ids: list[str] = []
    for uid in catalog:
        rec = rows.get(uid)
        if rec is None:
            fail += 1
            fail_ids.append(uid)
            classes["unmeasured"] += 1
            continue
        classes[rec.get("cls") or "?"] += 1
        if rec.get("ok"):
            ok += 1
        else:
            fail += 1
            fail_ids.append(uid)
    n = len(catalog)
    summary = {
        "ts": G.utc_now(),
        "n": n,
        "ok": ok,
        "fail": fail,
        "workers": G.WORKERS,
        "elapsed_s": elapsed_s,
        "classes": dict(classes.most_common()),
        "fail_ids_head": fail_ids[:80],
        "fail_n": len(fail_ids),
        "resume": True,
        "jsonl_unique": len(rows),
    }
    G.SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n", "ok", "fail", "elapsed_s", "classes")}), flush=True)
    if fail == 0:
        print(f"SUCCESS:g1-local-full {ok}/{n}", flush=True)
    else:
        print(f"FAILED:g1-local-full ok={ok} fail={fail} n={n}", flush=True)
    return summary


def main() -> int:
    os.chdir(str(G.REPO))
    os.environ["AST_INTEGRATE_ROOT"] = str(G.REPO)
    catalog = [u["id"] for u in json.loads(G.CATALOG.read_text(encoding="utf-8"))["work_units"]]
    rows = load_rows()
    todo = [uid for uid in catalog if uid not in rows]
    print(
        f"G1-RESUME catalog={len(catalog)} done={len(rows)} todo={len(todo)} "
        f"workers={G.WORKERS} python={sys.executable} repo={G.REPO}",
        flush=True,
    )
    started = time.time()
    if todo:
        ok = fail = 0
        classes: Counter[str] = Counter()
        for rec in rows.values():
            classes[rec.get("cls") or "?"] += 1
            if rec.get("ok"):
                ok += 1
            else:
                fail += 1
        done_base = len(rows)
        n = len(catalog)
        extra_fail: list[str] = []
        with ProcessPoolExecutor(max_workers=G.WORKERS, initializer=G._init_worker) as pool:
            futs = {pool.submit(G.one, uid): uid for uid in todo}
            finished = 0
            for fut in as_completed(futs):
                rec = fut.result()
                finished += 1
                classes[rec["cls"]] += 1
                if rec["ok"]:
                    ok += 1
                else:
                    fail += 1
                    extra_fail.append(rec["id"])
                with G.JSONL.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                total_done = done_base + finished
                print(
                    f"{total_done}/{n} ok={ok} fail={fail} {rec['id']} {rec['cls']}",
                    flush=True,
                )
                if finished % 10 == 0 or finished == len(todo):
                    G.HEART.write_text(
                        json.dumps(
                            {
                                "ts": G.utc_now(),
                                "done": total_done,
                                "n": n,
                                "ok": ok,
                                "fail": fail,
                                "elapsed_s": int(time.time() - started),
                                "classes": dict(classes.most_common(12)),
                                "resume_todo": len(todo),
                                "resume_finished": finished,
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
        rows = load_rows()
        write_summary(rows, catalog, int(time.time() - started), extra_fail)
    else:
        write_summary(rows, catalog, 0, [])
    rows = load_rows()
    missing = [uid for uid in catalog if uid not in rows]
    return 0 if not missing and all(rows[u].get("ok") for u in catalog) else 1


if __name__ == "__main__":
    raise SystemExit(main())

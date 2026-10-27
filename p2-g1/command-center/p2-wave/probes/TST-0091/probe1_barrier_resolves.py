#!/usr/bin/env python3
"""TST-0091 probe1: barrier resolves despite one hung unit (live).

Replays the receipt's cohort LIVE: n=12, unit-07 hung (sleeps far past
the 0.2s declared timeout), survivors sleep 0.05s. The per-unit
pipeline resolves the barrier on the survivors with the hung unit
classified timeout-0.2s and ALL 12 rows durable (write-as-you-go); the
naive parallel() control does NOT resolve inside its 0.55s watchdog and
writes zero durable rows. Asserts the receipt's cohort + both_states."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0091"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from pipeline import naive_parallel, per_unit_pipeline  # noqa: E402

UNIT = "TST-0091"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 2048, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk("SUCCESS:TST-0091" in text, "sentinel-absent")

    def mk(i: int):
        def fn() -> None:
            time.sleep(600.0) if i == 7 else time.sleep(0.05)
        return fn

    jobs = [{"id": "unit-%02d" % i, "fn": mk(i)} for i in range(12)]
    td = Path(tempfile.mkdtemp(prefix="tst0091-p1-"))
    try:
        fixed = per_unit_pipeline(jobs, 0.2, td / "out-fixed")
        hung_snapshot = dict(fixed["rows"]["unit-07"])
        chk(fixed["barrier_resolved"] is True, "fixed-barrier-must-resolve")
        chk(fixed["n_success"] == 11 and fixed["n_timeout"] == 1 and fixed["n_failed"] == 0, "fixed-cohort",
            json.dumps({k: fixed[k] for k in ("n_success", "n_timeout", "n_failed")}))
        chk(hung_snapshot.get("classification") == "timeout-0.2s", "hung-classified-timeout", json.dumps(hung_snapshot))
        chk(len(fixed["durable_rows"]) == 12, "all-rows-durable", str(len(fixed["durable_rows"])))
        chk(fixed["wall_s"] < 5.0, "wall-bounded", str(fixed["wall_s"]))
        naive = naive_parallel(jobs, 0.55)
        chk(naive.get("resolved") is False, "naive-must-block")
        chk(len(naive.get("durable_rows") or []) == 0, "naive-zero-durable")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    cohort = doc.get("cohort") or {}
    chk(int(cohort.get("n", -1)) == 12 and int(cohort.get("n_success", -1)) == 11 and int(cohort.get("n_timeout", -1)) == 1, "receipt-cohort")
    chk(cohort.get("barrier_resolved") is True and cohort.get("write_as_you_go") is True, "receipt-barrier-shape")
    chk(str(cohort.get("timeout_classification")) == "timeout-0.2s" and str(cohort.get("hung_unit_id")) == "unit-07", "receipt-hung-unit")
    bs = doc.get("both_states") or {}
    chk(bs.get("fixed_resolves") is True and bs.get("naive_blocks") is True and int(bs.get("naive_n_durable", -1)) == 0, "receipt-both-states")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print(json.dumps({"fixed": {k: fixed[k] for k in ("barrier_resolved", "wall_s", "n_success", "n_timeout", "n_failed")},
                      "hung_row": hung_snapshot,
                      "durable_rows": len(fixed["durable_rows"]),
                      "naive": {"resolved": naive.get("resolved"), "durable_rows": len(naive.get("durable_rows") or [])}}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 live cohort replay: barrier resolves in " + format(fixed["wall_s"], ".3f") + "s with 11 SUCCESS + unit-07 classified timeout-0.2s, 12 durable rows; naive parallel() control does not resolve in the 0.55s watchdog with zero durable rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

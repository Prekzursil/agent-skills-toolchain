#!/usr/bin/env python3
"""TST-0091 probe2: timeout attribution, survivor attribution, negative
control (live).

Mechanically different from probe1's barrier-timing view: asserts the
fan-in SET keeps the hung unit as a TYPED timeout row (present, not
silently dropped), every survivor row is attributed by unit_id and
complete, durable rows on disk match the barrier rows one-for-one, and
an all-healthy control batch (no hang) resolves with 12 SUCCESS. Also
asserts the naive watchdog would have zero durable rows for the same
cohort (the recorded defect)."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
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
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0091" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    inj = doc.get("injected_fault") or {}
    chk(inj.get("kind") == "deliberately-hung-unit" and str(inj.get("hung_unit_id")) == "unit-07", "receipt-fault-shape")

    def mk(i: int):
        def fn() -> None:
            time.sleep(600.0) if i == 7 else time.sleep(0.05)
        return fn

    jobs = [{"id": "unit-%02d" % i, "fn": mk(i)} for i in range(12)]
    td = Path(tempfile.mkdtemp(prefix="tst0091-p2-"))
    try:
        fixed = per_unit_pipeline(jobs, 0.2, td / "out")
        rows = fixed["rows"]
        hung = dict(rows["unit-07"])
        chk(hung["status"] == "TIMEOUT" and hung["classification"] == "timeout-0.2s", "hung-typed-timeout", json.dumps(hung))
        chk("unit-07" in [r["unit_id"] for r in rows.values()], "hung-present-in-fan-in-not-dropped")
        survivors = {k: v for k, v in rows.items() if k != "unit-07"}
        chk(len(survivors) == 11 and all(v["status"] == "SUCCESS" and v["unit_id"] == k for k, v in survivors.items()), "survivors-attributed-complete")
        disk = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (td / "out").glob("*.json")}
        chk(len(disk) == 12, "durable-count", str(len(disk)))
        chk(all(disk[k] == v for k, v in rows.items()), "durable-match-barrier")
        healthy = [{"id": "unit-%02d" % i, "fn": mk(0)} for i in range(12)]
        hres = per_unit_pipeline(healthy, 0.2, td / "out-healthy")
        chk(hres["n_success"] == 12 and hres["n_timeout"] == 0, "all-healthy-control-green", json.dumps({k: hres[k] for k in ("n_success", "n_timeout")}))
        naive = naive_parallel(jobs, 0.55)
        chk(naive.get("resolved") is False and len(naive.get("durable_rows") or []) == 0, "naive-control-zero-durable")
        ru = doc.get("residual_unknowns") or []
        chk(any(r.get("verdict") == "NOT-CHECKED" for r in ru), "residual-unknowns-recorded")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"hung_row": hung, "survivor_count": len(survivors),
                      "durable_rows_match": True, "healthy_control": {"n_success": hres["n_success"], "n_timeout": hres["n_timeout"]},
                      "naive_control": {"resolved": naive.get("resolved")}}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 hung unit attributed typed timeout-0.2s and PRESENT in the fan-in; 11 survivors complete and unit-attributed; 12 durable rows match the barrier; all-healthy control resolves 12 SUCCESS; naive control blocks with zero durable rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

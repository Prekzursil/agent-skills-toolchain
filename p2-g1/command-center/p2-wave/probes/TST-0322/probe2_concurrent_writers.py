#!/usr/bin/env python3
"""Named probe 2: two real concurrent writers must not tear a row.

Mechanically independent of probe 1 (does not copy or tamper the real
ledger). Starts two subprocesses that wait on a go-file, then each
appends CONCURRENT_RECORDS_EACH rows through the exclusive-create lock.
After join: parsed count equals offered count, chain verifies, zero torn
rows. A truncated-tail copy must be reported and repair must name the
loss. Does not import probe1.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.results_ledger import (  # noqa: E402
    CONCURRENT_RECORDS_EACH,
    CONCURRENT_WRITERS,
    repair_ledger,
    verify_ledger,
)

UNIT = "TST-0322"
ART = REPO / "command-center" / "receipts" / "TST-0322.json"
WORKER = REPO / "tools" / "bench" / "results_ledger.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def spawn_writer(
    ledger: Path,
    writer_id: str,
    n: int,
    ready: Path,
    go: Path,
) -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(WORKER),
        "worker",
        "--ledger",
        str(ledger),
        "--n",
        str(n),
        "--writer-id",
        writer_id,
        "--ready-path",
        str(ready),
        "--go-path",
        str(go),
        "--pad",
        "128",
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(REPO),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_ready(paths: list[Path], timeout_s: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if all(p.is_file() for p in paths):
            return True
        time.sleep(0.005)
    return False


def main() -> int:
    if CONCURRENT_WRITERS != 2:
        return fail("contract is two writers")
    if not WORKER.is_file():
        return fail(f"worker missing {WORKER.relative_to(REPO)}")

    offered = CONCURRENT_WRITERS * CONCURRENT_RECORDS_EACH
    with tempfile.TemporaryDirectory(prefix="tst0322-p2-") as tmp:
        root = Path(tmp)
        ledger = root / "concurrent.jsonl"
        go = root / "go"
        ready_a = root / "ready-A"
        ready_b = root / "ready-B"
        t0 = time.perf_counter()
        proc_a = spawn_writer(ledger, "A", CONCURRENT_RECORDS_EACH, ready_a, go)
        proc_b = spawn_writer(ledger, "B", CONCURRENT_RECORDS_EACH, ready_b, go)
        if not wait_ready([ready_a, ready_b]):
            proc_a.kill()
            proc_b.kill()
            return fail("writers never reached the start barrier")
        go.write_text("go\n", encoding="utf-8")
        out_a, err_a = proc_a.communicate(timeout=120)
        out_b, err_b = proc_b.communicate(timeout=120)
        wall = time.perf_counter() - t0
        if proc_a.returncode != 0 or proc_b.returncode != 0:
            return fail(
                f"writer rc A={proc_a.returncode} B={proc_b.returncode} "
                f"errA={err_a[-500:]} errB={err_b[-500:]}"
            )
        report = verify_ledger(ledger, check_tip=True)
        if not report.ok:
            return fail(f"concurrent ledger chain broken: {report.findings}")
        if report.events != offered:
            return fail(f"parsed={report.events} offered={offered}")
        if report.broken_tail or report.torn_bytes:
            return fail("torn row after concurrent append")

        writers = []
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            event = json.loads(raw)
            writers.append((event.get("payload") or {}).get("writer_id"))
        if writers.count("A") != CONCURRENT_RECORDS_EACH:
            return fail(f"writer A count={writers.count('A')}")
        if writers.count("B") != CONCURRENT_RECORDS_EACH:
            return fail(f"writer B count={writers.count('B')}")

        torn = root / "torn.jsonl"
        raw = ledger.read_bytes()
        if not raw.endswith(b"\n"):
            return fail("expected trailing NL before truncate control")
        # Drop the last 17 bytes of the final record, keep the prior complete rows.
        last_nl = raw.rfind(b"\n", 0, len(raw) - 1)
        if last_nl < 0:
            return fail("cannot locate previous newline for torn-tail control")
        cut = last_nl + 1 + max(8, (len(raw) - last_nl) // 3)
        torn.write_bytes(raw[:cut])
        torn_report = verify_ledger(torn, check_tip=False)
        if torn_report.ok or not torn_report.has_class("torn-tail"):
            return fail(
                f"torn tail not detected classes={torn_report.classes} "
                f"findings={torn_report.findings}"
            )
        repaired = repair_ledger(torn)
        after = verify_ledger(torn, check_tip=True)
        if not after.ok:
            return fail(f"repair left a broken ledger: {after.findings}")
        if repaired.get("lost", 0) < 1:
            return fail(f"repair did not report loss: {repaired}")
        if after.events != offered - 1:
            return fail(
                f"repair kept {after.events} want {offered - 1} (one torn record)"
            )

    src = WORKER.read_text(encoding="utf-8")
    fcntl_in_src = "import fcntl" in src or "from fcntl" in src
    if fcntl_in_src:
        return fail("results_ledger.py imports fcntl")

    if not ART.is_file():
        return fail(f"receipt missing {ART.relative_to(REPO)}")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    conc = (receipt.get("measured") or {}).get("concurrent") or {}
    if conc.get("writer_count") != CONCURRENT_WRITERS:
        return fail(f"receipt writer_count={conc.get('writer_count')}")
    if conc.get("parsed_records") != offered:
        return fail(f"receipt parsed_records={conc.get('parsed_records')} want={offered}")
    if conc.get("chain_ok") is not True:
        return fail("receipt concurrent.chain_ok is not true")
    if conc.get("torn_rows") != 0:
        return fail("receipt concurrent.torn_rows is not 0")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0322" not in text:
        return fail("receipt sentinel absent")

    out = {
        "pass": True,
        "probe": "probe2-concurrent-writers",
        "unit_id": UNIT,
        "writer_count": CONCURRENT_WRITERS,
        "records_per_writer": CONCURRENT_RECORDS_EACH,
        "parsed_records": report.events,
        "chain_ok": report.ok,
        "torn_rows": 0,
        "wall_clock_s": wall,
        "platform": sys.platform,
        "fcntl_in_worker_source": fcntl_in_src,
        "torn_tail_detected": True,
        "repair_lost": repaired.get("lost"),
        "repair_kept": repaired.get("kept"),
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"writers={CONCURRENT_WRITERS} parsed={report.events} "
        f"chain_ok={report.ok} torn=0 wall_clock_s={wall:.4f} "
        f"repair_lost={repaired.get('lost')}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 two real concurrent writers; "
        f"no torn row; chain intact; torn-tail control fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

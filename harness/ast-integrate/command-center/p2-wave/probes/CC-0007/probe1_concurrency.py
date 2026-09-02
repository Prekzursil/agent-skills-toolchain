#!/usr/bin/env python3
"""Probe 1: 8 concurrent writers × 500 records, hash chain intact, no fcntl."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import event_log as elog  # noqa: E402

OUT = HERE / "probe1-concurrency.json"
WRITERS = 8
EACH = 500
EXPECTED = WRITERS * EACH


def _fcntl_in(rel: str) -> bool:
    text = (REPO / rel).read_text(encoding="utf-8")
    for line in text.splitlines():
        code = line.split("#", 1)[0].strip()
        if code.startswith("import fcntl") or code.startswith("from fcntl"):
            return True
    return False


def main() -> int:
    fcntl_event_log = elog.uses_fcntl() or _fcntl_in("tools/command-center/event_log.py")
    fcntl_close = _fcntl_in("tools/command-center/close.py")
    tmp = Path(tempfile.mkdtemp(prefix="cc0007-probe1-"))
    log_path = tmp / "EVENTS.jsonl"
    run = elog.run_concurrent(log_path, writers=WRITERS, each=EACH, timeout=160.0)
    ok = (
        not fcntl_event_log
        and not fcntl_close
        and run["all_workers_ok"]
        and run["chain_ok"]
        and run["parsed"] == EXPECTED
        and run["intact_links"] == EXPECTED
        and run["interleaved_lines"] == 0
        and run["torn_tail"] is False
        and all(v == EACH for v in run["writer_counts"].values())
    )
    doc = {
        "probe": "probe1-concurrency",
        "unit_id": "CC-0007",
        "pass": ok,
        "fcntl_in_event_log": fcntl_event_log,
        "fcntl_in_close": fcntl_close,
        "lock_mechanism": "mkdir-exclusive (no POSIX fcntl)",
        "writers": WRITERS,
        "records_per_writer": EACH,
        "expected_records": EXPECTED,
        "parsed": run["parsed"],
        "intact_links": run["intact_links"],
        "interleaved_lines": run["interleaved_lines"],
        "torn_tail": run["torn_tail"],
        "writer_counts": run["writer_counts"],
        "wall_seconds": run["wall_seconds"],
        "exit_codes": run["exit_codes"],
        "errors": run["errors"],
        "path": run["path"],
        "platform": sys.platform,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"parsed={run['parsed']} intact_links={run['intact_links']} "
        f"interleaved={run['interleaved_lines']} wall_s={run['wall_seconds']} "
        f"fcntl={fcntl_event_log or fcntl_close}"
    )
    if not ok:
        print("FAILED:CC-0007-probe1 concurrent append did not yield 4000 intact chain links")
        return 1
    print("SUCCESS:CC-0007-probe1 8x500 parsed=4000 intact_links=4000 interleaved=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

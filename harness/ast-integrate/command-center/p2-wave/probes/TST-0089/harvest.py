#!/usr/bin/env python3
"""Post-mortem harvest after the monitor is gone.

Reads the durable ledger plus the atomically published result file. Does not
re-dispatch work that already recorded work-completed. Missing result with
work-died is a typed failure, not an unknown silence.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ledger import append_event, event_types, read_events  # noqa: E402


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def harvest(run_dir: Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    types = event_types(run_dir)
    result_path = run_dir / "result.json"
    out: dict[str, Any] = {
        "ok": False,
        "reason": "",
        "event_types": types,
        "has_monitor_died": "monitor-died" in types,
        "has_work_completed": "work-completed" in types,
        "has_work_died": "work-died" in types,
        "result_present": result_path.is_file(),
        "nonce": None,
        "result_sha256": None,
        "harvested_path": None,
        "would_redispatch": False,
    }
    if "work-completed" in types:
        if not result_path.is_file():
            out["reason"] = "work-completed in ledger but result.json absent"
            append_event(
                run_dir,
                {
                    "event": "harvest-failed",
                    "actor": "harvester",
                    "reason": out["reason"],
                },
            )
            return out
        raw = result_path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        harvested = run_dir / "harvested.json"
        harvested.write_bytes(raw.replace(b"\r\n", b"\n"))
        out.update(
            {
                "ok": True,
                "reason": "recovered work-completed result without redispatch",
                "nonce": doc.get("nonce"),
                "payload": doc.get("payload"),
                "result_sha256": sha256_bytes(raw),
                "harvested_path": "harvested.json",
                "would_redispatch": False,
            }
        )
        append_event(
            run_dir,
            {
                "event": "harvest-recovered",
                "actor": "harvester",
                "nonce": out["nonce"],
                "result_sha256": out["result_sha256"],
            },
        )
        return out
    if "work-died" in types:
        out["reason"] = "work-died; nothing to harvest; do not redispatch as success"
        append_event(
            run_dir,
            {
                "event": "harvest-empty",
                "actor": "harvester",
                "reason": out["reason"],
            },
        )
        return out
    out["reason"] = "no work-completed and no work-died; harvest refuses to invent"
    out["would_redispatch"] = False
    append_event(
        run_dir,
        {
            "event": "harvest-undecided",
            "actor": "harvester",
            "reason": out["reason"],
        },
    )
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: harvest.py RUN_DIR", file=sys.stderr)
        return 2
    doc = harvest(Path(sys.argv[1]))
    print(json.dumps(doc, indent=2, ensure_ascii=True))
    return 0 if doc.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

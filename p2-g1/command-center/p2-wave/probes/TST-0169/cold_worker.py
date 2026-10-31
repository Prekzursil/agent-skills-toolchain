#!/usr/bin/env python3
"""TST-0169 cold-resume worker (SUT).

Reads ONLY durable state: <DURABLE_ROOT>/checkpoint.json. Refuses to read
previous-session env traps or any session temp dir. Called with:
    cold_worker.py <durable_root> <workdir> [--plant-temp-dependency]
Exit 0 = resumed; nonzero = failed loudly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TRAPS = ("PREVIOUS_RUN_PID", "SESSION_CHECKPOINT", "HANDLED_LEDGER_PATH")


def main(argv: list[str]) -> int:
    durable_root = Path(argv[1])
    workdir = Path(argv[2])
    plant = "--plant-temp-dependency" in argv[3:]
    if plant:
        # planted dependency: a session temp file outside durable_root
        session_tmp = Path(os.environ.get("TST0169_SESSION_TMP", ""))
        if not session_tmp.is_file():
            print("FAILED:cold-worker planted temp dependency is gone (reboot)")
            return 3
    for trap in TRAPS:
        if trap in os.environ:
            # previous-session env present: the worker must not NEED it, but
            # reading it would be a durability violation -> detect and refuse
            print(f"FAILED:cold-worker previous-session env trap present: {trap}")
            return 2
    ck = durable_root / "checkpoint.json"
    if not ck.is_file():
        print("FAILED:cold-worker durable checkpoint missing")
        return 4
    try:
        doc = json.loads(ck.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:cold-worker checkpoint unparseable: {exc}")
        return 4
    if doc.get("schema_version") != 2:
        print(f"FAILED:cold-worker unexpected checkpoint version {doc.get('schema_version')}")
        return 4
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "resumed.json").write_text(
        json.dumps(
            {
                "resumed": True,
                "from": str(ck),
                "cursor": doc.get("cursor"),
                "traps_absent": True,
                "temp_plant_present": plant,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"resumed from {ck} cursor={doc.get('cursor')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

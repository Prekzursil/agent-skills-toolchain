#!/usr/bin/env python3
"""Emit RES-0163 prior-art teardown. No ADV schema rebuild."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402


def main() -> int:
    try:
        doc = L.emit()
    except Exception as exc:  # noqa: BLE001 — emit must fail loud
        print(f"FAILED:RES-0163-emit {type(exc).__name__}: {exc}")
        return 1
    systems = doc.get("systems") or []
    disq = doc.get("negative_control", {}).get("system_lock_disqualified") or []
    print(f"wrote {L.ARTIFACT_REL}")
    print(
        "systems="
        + str(len(systems))
        + " claims="
        + str(len(doc.get("claims") or []))
        + " disqualified_locks="
        + ",".join(disq)
        + " schema_present="
        + str(doc.get("schema_present_on_disk"))
    )
    print("SUCCESS:RES-0163 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

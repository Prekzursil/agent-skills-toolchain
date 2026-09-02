#!/usr/bin/env python3
"""Fresh-process instrument: load a receipt from disk and evaluate live C11.

Independent of the writer's in-memory derive() object. The reducer re-reads
the manifest FILE named by receipt.manifest_registration.manifest_path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import c11 as C  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in {2, 3}:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "usage: reread_manifest.py RECEIPT_JSON REPO_ROOT "
                        "[OUTPUT_SCHEMA_REL]"
                    ),
                }
            )
        )
        return 2
    receipt_path = Path(args[0])
    repo_root = Path(args[1])
    output_schema = args[2] if len(args) == 3 else None
    try:
        receipt = C.load_json(receipt_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"receipt unreadable:{type(exc).__name__}: {exc}",
                }
            )
        )
        return 1
    if not isinstance(receipt, dict):
        print(json.dumps({"ok": False, "error": "receipt is not an object"}))
        return 1
    live = C.live_evaluate(receipt, repo_root, output_schema=output_schema)
    print(
        json.dumps(
            {
                "ok": True,
                "instrument": "fresh-process-manifest-reread",
                "pid_note": "separate python process; no writer locals",
                "receipt_path": str(receipt_path),
                "result": live["c11"],
                "c2": live["c2"]["outcome"],
                "c4": live["c4"]["outcome"],
                "c5": live["c5"]["outcome"],
                "reducer_id": live["reducer_id"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

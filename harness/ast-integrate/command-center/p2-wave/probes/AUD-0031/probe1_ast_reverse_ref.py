#!/usr/bin/env python3
"""Probe 1: AST reverse-reference of tools/lib salvage, excluding tests.

A module named only in a docstring or comment must not count as a consumer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

UNIT = "AUD-0031"


def main() -> int:
    rows = E.roster()
    refs = E.reverse_refs(rows)
    mention = E.mention_control(rows)
    payload = {
        "probe": "probe1-ast-reverse-ref",
        "unit_id": UNIT,
        "method": refs.get("method"),
        "used_grep": refs.get("used_grep"),
        "files_scanned": refs.get("files_scanned"),
        "test_files_excluded": refs.get("test_files_excluded"),
        "consumers_by_module": refs.get("consumers_by_module"),
        "mention_control": mention,
        "lib_home_exists": E.LIB_HOME.is_dir(),
        "roster": [
            {"rel": r["rel"], "present_on_disk": r["present_on_disk"]} for r in rows
        ],
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if refs.get("used_grep"):
        print(f"FAILED:{UNIT}-probe1 used grep")
        return 1
    if not mention.get("passed"):
        print(
            f"FAILED:{UNIT}-probe1 mention control "
            f"silent={mention.get('silent_on_mention')} "
            f"fired={mention.get('fired_on_import')}"
        )
        return 1
    if mention.get("mention_hits"):
        print(f"FAILED:{UNIT}-probe1 mention-only counted as consumer")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe1 ast-reverse-ref files={refs.get('files_scanned')} "
        f"mention_control=pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

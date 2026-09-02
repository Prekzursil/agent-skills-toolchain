#!/usr/bin/env python3
"""Probe 1: 15 isolated shards, unique indexes, red-to-green, no repair commit."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from executor import run_batch  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0087-repair-batch-execution.json"
SENTINEL = "SUCCESS:WFA-0087"


def main() -> int:
    batch = run_batch()
    print(
        json.dumps(
            {
                "n": batch["n"],
                "ok": batch["ok"],
                "indexes_unique": batch["indexes_unique"],
                "all_red_to_green": batch["all_red_to_green"],
                "all_canary_held": batch["all_canary_held"],
                "all_scoped": batch["all_scoped"],
                "any_repair_commit": batch["any_repair_commit"],
                "failed": [r["id"] for r in batch["rows"] if not r["ok"]],
            },
            sort_keys=True,
        )
    )
    if batch["n"] != 15:
        print(f"FAILED:WFA-0087-probe1 n={batch['n']}")
        return 1
    if not batch["indexes_unique"]:
        print("FAILED:WFA-0087-probe1 shared index among shards")
        return 1
    if not batch["all_red_to_green"]:
        print("FAILED:WFA-0087-probe1 not all red-to-green")
        return 1
    if not batch["all_canary_held"]:
        print("FAILED:WFA-0087-probe1 canary broken")
        return 1
    if not batch["all_scoped"]:
        print("FAILED:WFA-0087-probe1 unscoped diff")
        return 1
    if batch["any_repair_commit"]:
        print("FAILED:WFA-0087-probe1 repair committed")
        return 1
    if not batch["ok"]:
        print("FAILED:WFA-0087-probe1 batch not ok")
        return 1
    if OUT.is_file():
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:WFA-0087-probe1 artifact state={doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:WFA-0087-probe1 artifact sentinel absent")
            return 1
        if int(doc.get("candidate_count") or 0) != 15:
            print("FAILED:WFA-0087-probe1 artifact candidate_count")
            return 1
        print("artifact_ok=True")
    print("indexes_unique=True red_to_green=15/15 repair_commits=0")
    print("SUCCESS:WFA-0087-probe1 isolated batch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

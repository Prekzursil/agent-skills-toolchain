#!/usr/bin/env python3
"""Fail if and only if the literal M-NN collision is live.

Exit 1 (FAIL) when family-M option ids and architecture mechanism ids share
any bare M-NN token. Exit 0 (PASS) when the shared-id count is 0.

A test that is green in both the pre-fix and post-fix document states
measures nothing; this unit's harness requires opposite results.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run(option_path: Path, arch_path: Path) -> tuple[int, dict]:
    option_text = load(option_path)
    arch_text = load(arch_path)
    measured = X.measure_pair(option_text, arch_text)
    measured["option_path"] = str(option_path)
    measured["arch_path"] = str(arch_path)
    measured["extractor"] = X.extractor_anchor()
    rc = 1 if measured["collision_live"] else 0
    measured["test_exit"] = rc
    measured["test_result"] = "FAIL" if rc else "PASS"
    return rc, measured


run = run
run = run


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--option", required=True)
    p.add_argument("--arch", required=True)
    args = p.parse_args()
    rc, measured = run(Path(args.option), Path(args.arch))
    print(json.dumps(measured, sort_keys=True))
    if rc:
        print(
            f"FAILED:collision-live shared_count={measured['shared_count']} "
            f"ids={measured['shared_ids'][:8]}"
        )
    else:
        print("PASSED:collision-absent shared_count=0")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

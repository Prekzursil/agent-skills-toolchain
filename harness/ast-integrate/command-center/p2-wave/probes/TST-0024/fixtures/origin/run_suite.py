#!/usr/bin/env python3
"""Run the fixture unittest tree and emit JSON members to stdout."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TESTS = HERE / "tests"


def _nid(test: unittest.TestCase) -> str:
    parts = test.id().split(".")
    method = parts[-1] if parts else test.id()
    cls = parts[-2] if len(parts) >= 2 else "Case"
    return f"test_profile_suite.py::{cls}::{method}"


def _iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def run_members() -> list[dict]:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS), pattern="test_*.py")
    tests = list(_iter_tests(suite))
    result = unittest.TestResult()
    suite.run(result)
    failed = {t.id() for t, _ in result.failures}
    errors = {t.id() for t, _ in result.errors}
    skipped = {t.id() for t, _ in result.skipped}
    members: list[dict] = []
    seen: set[str] = set()
    for test in tests:
        tid = _nid(test)
        if tid in seen:
            continue
        seen.add(tid)
        raw_id = test.id()
        if raw_id in failed:
            outcome = "failed"
        elif raw_id in errors:
            outcome = "error"
        elif raw_id in skipped:
            outcome = "skipped"
        else:
            outcome = "passed"
        members.append({"id": tid, "outcome": outcome})
    members.sort(key=lambda m: m["id"])
    return members


def main() -> int:
    members = run_members()
    print(json.dumps({"members": members}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

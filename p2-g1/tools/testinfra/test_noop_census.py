#!/usr/bin/env python3
"""No-op census runner used by TST-0126 probe1: planted shapes must be found."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from testinfra.noop_census import census_noop_tests  # noqa: E402


def _ends(bucket: list[str], name: str) -> bool:
    return any(entry.endswith(f"::{name}") for entry in bucket)


def test_census_finds_a_planted_assertionless_test(doc: dict[str, Any]) -> None:
    assert _ends(doc["planted"]["assertionless"], "test_planted_assertionless_tst0126")


def test_census_finds_a_planted_unconditional_skip(doc: dict[str, Any]) -> None:
    bucket = doc["planted"]["unconditional_skip"]
    assert _ends(bucket, "test_planted_unconditional_skip_tst0126")
    assert _ends(bucket, "test_planted_skipif_true_tst0126")
    assert _ends(bucket, "test_planted_unittest_skip_tst0126")


def test_census_finds_a_planted_always_xfail(doc: dict[str, Any]) -> None:
    bucket = doc["planted"]["always_xfail"]
    assert _ends(bucket, "test_planted_always_xfail_tst0126")
    assert _ends(bucket, "test_planted_unittest_expected_failure_tst0126")


TESTS = (
    test_census_finds_a_planted_assertionless_test,
    test_census_finds_a_planted_unconditional_skip,
    test_census_finds_a_planted_always_xfail,
)


def run_all(repo: Path) -> dict[str, Any]:
    doc = census_noop_tests(Path(repo))
    tests = []
    failed = 0
    for fn in TESTS:
        try:
            fn(doc)
            tests.append({"id": fn.__name__, "result": "PASS"})
        except AssertionError as exc:
            failed += 1
            tests.append({"id": fn.__name__, "result": "FAIL", "detail": str(exc)})
    live_disjoint = set(doc["live"]["union"]).isdisjoint(set(doc["planted"]["union"]))
    if not live_disjoint:
        failed += 1
        tests.append({"id": "planted_excluded_from_live_union", "result": "FAIL"})
    return {
        "pass": failed == 0,
        "tests": tests,
        "live": doc["live"],
        "planted": doc["planted"],
        "files_scanned": doc["files_scanned"],
        "parse_failures": doc["parse_failures"],
        "method": doc["method"],
    }


def main() -> int:
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else TOOLS.parent
    result = run_all(repo)
    for row in result["tests"]:
        print(f"{row['result'].lower()} {row['id']}")
    print(("SUCCESS" if result["pass"] else "FAILED") + ":test_noop_census")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

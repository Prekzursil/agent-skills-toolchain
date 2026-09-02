#!/usr/bin/env python3
"""Three-fixture + mutation + adversarial-fourth tests for IMP-0455.

Runnable as a script (prints SUCCESS:IMP-0455-tests) and as pytest nodeids.
Does not import pytest: this worktree may not have it.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(PKG))

from downstream_readability import (  # noqa: E402
    consume,
    condition_12,
    decorative_parse_and_key,
    mutant_exists_only,
)

FIX = REPO / "command-center" / "p2-wave" / "probes" / "IMP-0455" / "fixtures"
READABLE = FIX / "01-readable.json"
UNPARSEABLE = FIX / "02-exists-unparseable.json"
MISSING = FIX / "03-parseable-missing-field.json"
ADVERSARIAL = FIX / "04-adversarial-unusable-field.json"
LIB = PKG / "downstream_readability.py"


def test_readable_fixture_extracts_sentinel() -> None:
    result = consume(READABLE)
    assert result.ok is True
    assert result.code == "READABLE"
    assert result.extracted == "SENTINEL:FIXT-0001:READABLE"
    via_c12 = condition_12(READABLE)
    assert via_c12.ok is True
    assert via_c12.extracted == result.extracted


def test_unparseable_fixture_fails_despite_existing() -> None:
    assert UNPARSEABLE.is_file()
    assert mutant_exists_only(UNPARSEABLE) is True
    result = consume(UNPARSEABLE)
    assert result.ok is False
    assert result.code == "UNPARSEABLE"
    assert result.extracted is None


def test_missing_field_fails_and_exists_mutation_would_green_it() -> None:
    assert MISSING.is_file()
    result = consume(MISSING)
    assert result.ok is False
    assert result.code == "MISSING_REQUIRED_FIELD"
    assert result.detail == "sentinel"
    exists_only = mutant_exists_only(MISSING)
    assert exists_only is True
    # Catalog mutation: reducing the probe to os.path.exists greens fixture 3
    # and thereby reds the three-fixture battery.
    assert exists_only and not result.ok


def test_adversarial_fourth_passes_decorative_key_check_fails_consumer() -> None:
    assert ADVERSARIAL.is_file()
    deco = decorative_parse_and_key(ADVERSARIAL)
    real = consume(ADVERSARIAL)
    assert deco is True
    assert real.ok is False
    assert real.code == "REQUIRED_FIELD_UNUSABLE"
    assert "type=dict" in real.detail
    assert "usable=false" in real.detail


def test_absent_path_is_not_readable() -> None:
    missing = FIX / "00-does-not-exist.json"
    assert not missing.exists()
    result = consume(missing)
    assert result.ok is False
    assert result.code == "ABSENT"
    assert result.code != "READABLE"
    assert mutant_exists_only(missing) is False


def test_consume_does_not_consult_exists_as_its_answer() -> None:
    src = LIB.read_text(encoding="utf-8")
    body = src[src.index("def consume(") : src.index("\ndef condition_12(")]
    if '"""' in body:
        first = body.index('"""')
        second = body.index('"""', first + 3)
        body_no_doc = body[:first] + body[second + 3 :]
    else:
        body_no_doc = body
    assert "os.path.exists" not in body_no_doc
    assert "path.exists(" not in body_no_doc
    assert "json.loads" in body
    assert "required_field" in body


TESTS = [
    test_readable_fixture_extracts_sentinel,
    test_unparseable_fixture_fails_despite_existing,
    test_missing_field_fails_and_exists_mutation_would_green_it,
    test_adversarial_fourth_passes_decorative_key_check_fails_consumer,
    test_absent_path_is_not_readable,
    test_consume_does_not_consult_exists_as_its_answer,
]


def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 — script runner reports then exits
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"FAILED:IMP-0455-tests {failed}/{len(TESTS)}")
        return 1
    print(f"ran={len(TESTS)} failed=0")
    print("SUCCESS:IMP-0455-tests three-fixture + mutation + adversarial-fourth")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

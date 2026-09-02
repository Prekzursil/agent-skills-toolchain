#!/usr/bin/env python3
"""Probe 1: required TST-0006 tests (absent downgrade + fenced use-vs-mention)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from path_linter import UNVERIFIED, VERIFIED, lint_file, lint_payload  # noqa: E402

ABSENT_REL = "command-center/p2-wave/probes/TST-0006/fixtures/ABSENT-NEVER-WRITTEN.json"
ILLUS_REL = "command-center/p2-wave/probes/TST-0006/fixtures/ILLUSTRATIVE-ONLY-ABSENT.json"
PRESENT_REL = "command-center/p2-wave/probes/TST-0006/fixtures/real-present.txt"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0006-probe1 {msg}")
    return 1


def test_absent_path_downgrades_result() -> str | None:
    # Text citation.
    text = lint_file(HERE / "fixtures" / "absent_citation.txt", REPO)
    if text.status != UNVERIFIED:
        return f"text citation status={text.status} want={UNVERIFIED}"
    if ABSENT_REL not in text.flagged_paths and not any(
        ABSENT_REL in p for p in text.flagged_paths
    ):
        return f"text citation did not flag {ABSENT_REL}: {text.flagged_paths}"
    # Structured JSON citation.
    js = lint_file(HERE / "fixtures" / "absent_citation.json", REPO)
    if js.status != UNVERIFIED:
        return f"json citation status={js.status} want={UNVERIFIED}"
    if not any(ABSENT_REL in p for p in js.flagged_paths):
        return f"json citation did not flag {ABSENT_REL}: {js.flagged_paths}"
    # Present control must not be flagged.
    present = lint_file(HERE / "fixtures" / "present_citation.txt", REPO)
    if any(PRESENT_REL in p for p in present.flagged_paths):
        return f"present citation wrongly flagged: {present.flagged_paths}"
    if present.status != VERIFIED:
        return f"present citation status={present.status} want={VERIFIED}"
    return None


def test_illustrative_path_in_fenced_code_is_not_flagged() -> str | None:
    md = lint_file(HERE / "fixtures" / "fenced_mention.md", REPO)
    if any(ILLUS_REL in p for p in md.flagged_paths):
        return f"markdown fence flagged illustrative path: {md.flagged_paths}"
    if ILLUS_REL not in md.mention_paths and not any(ILLUS_REL in p for p in md.mention_paths):
        return f"markdown fence did not classify mention: {md.mention_paths}"
    if md.status != VERIFIED:
        return f"markdown-only example status={md.status} want={VERIFIED}"
    mixed = lint_file(HERE / "fixtures" / "mixed_use_and_mention.json", REPO)
    if any(ILLUS_REL in p for p in mixed.flagged_paths):
        return f"json fence flagged illustrative path: {mixed.flagged_paths}"
    if mixed.status != VERIFIED:
        return f"mixed fixture status={mixed.status} want={VERIFIED} flagged={mixed.flagged_paths}"
    # Mutation control: stripping disabled MUST flag the illustrative path.
    raw = (HERE / "fixtures" / "fenced_mention.md").read_text(encoding="utf-8")
    mutant = lint_payload(raw, REPO, strip_fences=False)
    if mutant.status != UNVERIFIED or not any(ILLUS_REL in p for p in mutant.flagged_paths):
        return (
            "fence-strip mutation did not flag illustrative path "
            f"status={mutant.status} flagged={mutant.flagged_paths}"
        )
    return None


def main() -> int:
    tests = [
        ("test_absent_path_downgrades_result", test_absent_path_downgrades_result),
        (
            "test_illustrative_path_in_fenced_code_is_not_flagged",
            test_illustrative_path_in_fenced_code_is_not_flagged,
        ),
    ]
    rows = []
    failed = False
    for name, fn in tests:
        err = fn()
        result = "FAIL" if err else "PASS"
        print(f"{name} {result}" + (f" {err}" if err else ""))
        rows.append({"id": name, "result": result, "error": err})
        if err:
            failed = True
    (HERE / "probe1-results.json").write_text(
        json.dumps({"tests": rows, "failed": failed}, indent=1) + "\n",
        encoding="utf-8",
    )
    if failed:
        return _fail("required tests red")
    print("SUCCESS:TST-0006-probe1 absent-downgrade and fenced use-vs-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

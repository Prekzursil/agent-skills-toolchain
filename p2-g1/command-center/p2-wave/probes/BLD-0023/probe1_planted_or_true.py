#!/usr/bin/env python3
"""Probe 1: plant || true in a scratch CI step and prove the census reports it.

Also the use-vs-mention control: continue-on-error in documentation is not a
suppression. Both-states: the clean CI copy without || true is silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

PLANTED = HERE / "fixtures" / "ci-scratch" / "quality.yml"
CLEAN = HERE / "fixtures" / "ci-clean" / "quality.yml"
MENTION = HERE / "fixtures" / "mention" / "docs.md"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0023-probe1 {msg}")
    return 1


def main() -> int:
    planted = C.scan_paths(REPO, [PLANTED])
    or_true = [f for f in planted if f.construct == "or-true"]
    if not or_true:
        return fail("planted || true not reported")
    if not any("|| true" in f.snippet or "||true" in f.snippet.replace(" ", "") for f in or_true):
        return fail("reported or-true without || true snippet")
    rel = C._rel(REPO, PLANTED)
    if not any(f.path == rel for f in or_true):
        return fail(f"planted hit path mismatch {or_true[0].path}")

    clean = C.scan_paths(REPO, [CLEAN])
    if any(f.construct == "or-true" for f in clean):
        return fail("clean CI copy reported or-true (both-states leak)")

    mention = C.scan_paths(REPO, [MENTION])
    if any(f.construct == "continue-on-error" for f in mention):
        return fail("documentation continue-on-error counted as a suppression")
    text = MENTION.read_text(encoding="utf-8")
    if "continue-on-error" not in text:
        return fail("mention fixture lost the continue-on-error string")

    cat = CATALOG.read_text(encoding="utf-8")
    if "continue-on-error" not in cat:
        return fail("catalog no longer mentions continue-on-error")
    live = C.scan_tree(REPO, skip_own_unit=True)
    if any(
        f.construct == "continue-on-error" and "WORK-UNIT-CATALOG.json" in f.path
        for f in live
    ):
        return fail("catalog description counted as continue-on-error use")

    doc = {
        "probe": "probe1-planted-or-true",
        "unit_id": "BLD-0023",
        "planted_or_true": len(or_true),
        "planted_path": rel,
        "clean_or_true": 0,
        "mention_continue_on_error_counted": 0,
        "catalog_continue_on_error_counted": 0,
        "pass": True,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        f"planted={len(or_true)} clean=0 mention_counted=0 "
        f"path={rel}:{or_true[0].line}"
    )
    print("SUCCESS:BLD-0023-probe1 planted || true reported; mention excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

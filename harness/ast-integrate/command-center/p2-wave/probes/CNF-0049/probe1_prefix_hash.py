#!/usr/bin/env python3
"""Named probe 1: pre-rollback ledger is an exact byte prefix of post-rollback.

Different field than probe 2 (which mutates copies and never calls rollback).
Re-runs the isolated rollback through close.append_event and checks the
confirmation artifact recorded the same prefix hashes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import recorded_from_artifact, run_rollback_prefix  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0049-ledger-append-only.json"
SENTINEL = (
    "SUCCESS:CNF-0049 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the prefix-hash comparison ran "
    "and the one-line truncation control failed as designed. Any other terminal "
    "state is FAILED:CNF-0049 <classification> with the diagnostic tail attached."
)


def main() -> int:
    live = run_rollback_prefix()
    print(json.dumps({k: live[k] for k in sorted(live) if k != "appended_lines"}, sort_keys=True))
    if not live.get("pass") or not live.get("pre_is_byte_prefix_of_post"):
        print("FAILED:CNF-0049-probe1 rollback rewrote or truncated the prefix")
        return 1
    if live.get("appended_line_count") != 1:
        print("FAILED:CNF-0049-probe1 expected exactly one appended line")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0049-probe1 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0049-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0049-probe1 completion sentinel absent")
        return 1
    rec = recorded_from_artifact(doc)
    before = (rec["ledger"] or {}).get("before") or {}
    after = (rec["ledger"] or {}).get("after") or {}
    if before.get("prefix_hash") != live["before"]["prefix_hash"]:
        print("FAILED:CNF-0049-probe1 artifact before prefix_hash != live")
        return 1
    if after.get("prefix_hash") != live["after"]["prefix_hash"]:
        print("FAILED:CNF-0049-probe1 artifact after retained prefix_hash != live")
        return 1
    if before.get("line_count") != live["before"]["line_count"]:
        print("FAILED:CNF-0049-probe1 artifact before line_count != live")
        return 1
    tests = (rec["tests"] or {}).get("byte_prefix") or {}
    if tests.get("pass") is not True:
        print("FAILED:CNF-0049-probe1 artifact byte_prefix.pass is not true")
        return 1
    if not (rec["verdict"] or {}).get("prefix_hash_comparison_ran"):
        print("FAILED:CNF-0049-probe1 artifact did not record prefix-hash comparison")
        return 1
    print(
        "prefix_ok=True before_lines="
        f"{live['before']['line_count']} after_lines={live['after']['line_count']} "
        f"appended={live['appended_line_count']}"
    )
    print("SUCCESS:CNF-0049-probe1 prefix-hash comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

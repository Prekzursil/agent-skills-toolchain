#!/usr/bin/env python3
"""Probe 1: extraction control + both-states execution of documented commands.

Signal: the extractor finds the hand-counted set, those commands run clean,
use-vs-mention is silent, and a planted typo is caught. Live named docs are
scanned (absence is a measurement, not a crash).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import discover  # noqa: E402
from execute import execute_rows, reset_subprocess_log  # noqa: E402
from extract import extract_file, live_only, skipped_only  # noqa: E402

FIX = HERE / "fixtures"
HAND = FIX / "hand-counted.md"
MENTION = FIX / "use-vs-mention.md"
BROKEN = FIX / "known-broken.md"
TREE = FIX / "dir-tree.md"
HAND_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/hand-counted.md"
MENTION_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/use-vs-mention.md"
BROKEN_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/known-broken.md"
TREE_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/dir-tree.md"
HAND_COUNT = 5


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0191-probe1 {msg}")
    return 1


def main() -> int:
    reset_subprocess_log()
    if not HAND.is_file() or not MENTION.is_file() or not BROKEN.is_file():
        return fail("control fixtures missing")
    if not TREE.is_file():
        return fail("dir-tree fixture missing")

    hand = extract_file(HAND, HAND_REL)
    live = live_only(hand)
    if len(live) != HAND_COUNT:
        return fail(f"hand-counted extract={len(live)} want={HAND_COUNT}")
    if skipped_only(hand):
        return fail("hand-counted file produced skips")

    results = execute_rows(live)
    bad = [r for r in results if r.outcome != "PASS"]
    if bad:
        return fail(
            "both-states good commands did not run clean: "
            + json.dumps(
                [
                    {
                        "cmd": r.command,
                        "outcome": r.outcome,
                        "exit": r.exit_code,
                        "diff": r.output_diff,
                        "stderr": r.stderr[-200:],
                    }
                    for r in bad
                ]
            )
        )

    mentions = extract_file(MENTION, MENTION_REL)
    if live_only(mentions):
        return fail(
            "use-vs-mention leaked live commands: "
            + str([r.command for r in live_only(mentions)])
        )
    if len(skipped_only(mentions)) < 2:
        return fail(
            f"use-vs-mention skips={len(skipped_only(mentions))} want>=2"
        )

    tree = extract_file(TREE, TREE_REL)
    tree_live = live_only(tree)
    if any("schema/" in r.command or r.command.startswith("mkt/") for r in tree_live):
        return fail("dir-tree fence leaked as live commands")
    if [r.command for r in tree_live] != ["echo cnf0191-dir-tree-live"]:
        return fail(f"dir-tree live={ [r.command for r in tree_live]!r }")
    tree_run = execute_rows(tree_live)[0]
    if tree_run.outcome != "PASS":
        return fail("dir-tree live echo did not run clean")

    broken = live_only(extract_file(BROKEN, BROKEN_REL))
    if len(broken) != 1:
        return fail(f"known-broken extract={len(broken)} want=1")
    br = execute_rows(broken)[0]
    if br.outcome == "PASS" or br.exit_code == 0:
        return fail("known-broken control did not catch the planted typo")
    if br.refused_before_exec:
        return fail("known-broken was refused instead of executed")

    census = discover(REPO)
    if len(census["present"]) > 40:
        return fail(f"corpus explosion present={len(census['present'])}")
    live_docs = []
    for rel in census["present"]:
        live_docs.extend(live_only(extract_file(REPO / rel, rel)))
    if len(live_docs) > 250:
        return fail(f"corpus explosion live_cmds={len(live_docs)}")

    payload = {
        "probe": "probe1-extract-and-execute",
        "hand_counted": HAND_COUNT,
        "extracted": [r.command for r in live],
        "good_pass": len(results),
        "mention_skips": len(skipped_only(mentions)),
        "typo_caught": True,
        "typo_exit": br.exit_code,
        "live_docs_present": census["present"],
        "live_docs_absent_named": census["absent_named"],
        "live_commands_extracted": len(live_docs),
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"extracted={HAND_COUNT} good_pass={len(results)} "
        f"mention_skips={payload['mention_skips']} typo_exit={br.exit_code} "
        f"live_present={len(census['present'])} live_cmds={len(live_docs)}"
    )
    print("SUCCESS:CNF-0191-probe1 extraction both-states typo-caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

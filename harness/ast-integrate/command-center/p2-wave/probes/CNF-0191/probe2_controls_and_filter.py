#!/usr/bin/env python3
"""Probe 2: independent hand-count + destructive filter + schema garbage.

Mechanically different from probe1: a dollar-prompt regex that does not share
extract.py's heading skipper, a frozen hand-count, and an assertion that the
reviewed refusal list is applied before any subprocess.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from execute import SUBPROCESS_LOG, execute_rows, reset_subprocess_log  # noqa: E402
from extract import extract_file, live_only, skipped_only  # noqa: E402
from refuse import REVIEWED_REFUSAL_LIST, classify  # noqa: E402

FIX = HERE / "fixtures"
HAND = FIX / "hand-counted.md"
MENTION = FIX / "use-vs-mention.md"
DEST = FIX / "destructive.md"
HAND_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/hand-counted.md"
MENTION_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/use-vs-mention.md"
DEST_REL = "command-center/p2-wave/probes/CNF-0191/fixtures/destructive.md"
SCHEMA = REPO / "command-center/schema/program-gate-report.schema.json"

# Frozen hand-count of fixtures/hand-counted.md (read independently of extract.py).
HAND_COUNTED = [
    "python3 -c \"print('cnf0191-hello')\"",
    "echo documented-ok",
    "true",
    "printf '%s\\n' 'cnf0191-printf'",
    "python3 -c \"import sys; sys.exit(0)\"",
]

GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)

PROMPT = re.compile(r"^(?:PS>|\$)\s+(.*)$")


def independent_dollar_extract(text: str) -> list[str]:
    """Second extractor: every `$ ` line inside a fence, no heading skipper."""
    cmds: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            m = PROMPT.match(line.rstrip())
            if m:
                cmds.append(m.group(1).strip())
    return cmds


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0191-probe2 {msg}")
    return 1


def main() -> int:
    reset_subprocess_log()
    if not HAND.is_file() or not DEST.is_file() or not SCHEMA.is_file():
        return fail("fixtures or schema missing")

    indep_hand = independent_dollar_extract(HAND.read_text(encoding="utf-8"))
    if indep_hand != HAND_COUNTED:
        return fail(
            f"independent dollar extract != frozen hand-count: {indep_hand!r}"
        )
    main_hand = [r.command for r in live_only(extract_file(HAND, HAND_REL))]
    if main_hand != HAND_COUNTED:
        return fail(f"main extractor != frozen hand-count: {main_hand!r}")

    indep_mention = independent_dollar_extract(MENTION.read_text(encoding="utf-8"))
    if len(indep_mention) < 2:
        return fail(
            "independent extractor found no mentions; use-vs-mention control is vacuous"
        )
    main_mention_live = live_only(extract_file(MENTION, MENTION_REL))
    if main_mention_live:
        return fail("main extractor treated mentions as live")
    if len(skipped_only(extract_file(MENTION, MENTION_REL))) < 2:
        return fail("main extractor did not skip mentions")

    dest_rows = live_only(extract_file(DEST, DEST_REL))
    if len(dest_rows) != 5:
        return fail(f"destructive fixture live extract={len(dest_rows)} want=5")
    results = execute_rows(dest_rows)
    safe = [r for r in results if r.command.startswith("echo cnf0191-filter-safe")]
    refused = [r for r in results if r.outcome == "NOT-CHECKED"]
    if len(safe) != 1 or safe[0].outcome != "PASS" or safe[0].exit_code != 0:
        return fail("destructive fixture safe command did not run clean")
    if len(refused) != 4:
        return fail(f"refusal count={len(refused)} want=4")
    if any(not r.refused_before_exec for r in refused):
        return fail("a refused command was not marked refused-before-exec")
    if any(r.subprocess_attempted for r in refused):
        return fail("a refused command still attempted a subprocess")
    log = list(SUBPROCESS_LOG)
    for r in refused:
        # Redacted form is stored on Outcome.command; original may contain secrets.
        if "rm -rf" in r.command or "git push" in r.command or "| sh" in r.command:
            pass
        if any(
            needle in item
            for item in log
            for needle in ("rm -rf", "git push", "install.sh", "AWS_SECRET_ACCESS_KEY")
        ):
            return fail(f"refused command leaked into subprocess log: {log!r}")
    if log != ["echo cnf0191-filter-safe"]:
        return fail(f"subprocess log={log!r} want only the safe echo")

    if classify("echo cnf0191-filter-safe") is not None:
        return fail("refusal list matched a known-safe command")
    if len(REVIEWED_REFUSAL_LIST) < 8:
        return fail("reviewed refusal list is too thin to be the reviewed filter")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for i, garbage in enumerate(GARBAGE):
        errs = list(validator.iter_errors(garbage))
        if not errs:
            return fail(f"schema accepted garbage probe {i}")

    payload = {
        "probe": "probe2-controls-and-filter",
        "hand_count_agree": True,
        "independent_mention_count": len(indep_mention),
        "main_mention_live": 0,
        "refused": len(refused),
        "safe_pass": True,
        "subprocess_log": log,
        "schema_rejects_garbage": 3,
        "refusal_rules": len(REVIEWED_REFUSAL_LIST),
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "hand_count_agree=True refused=4 safe_pass=True "
        f"schema_garbage_rejected=3 rules={len(REVIEWED_REFUSAL_LIST)}"
    )
    print("SUCCESS:CNF-0191-probe2 independent-count destructive-filter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regression tests for stubscan.find_stubs against the use-vs-mention false-positive class.

Every SILENT case below is a real false positive the scanner emitted on 2026-07-19 (F9, the
INPUT defect doc, the D1/D2 evaluation artifacts, the FAILURE-REPLAY-CORPUS fixtures). Every FIRE
case is a genuine stub the scanner MUST still catch -- proof the negation guard / markdown-bold /
corpus-exemption fixes did not over-correct into blindness. This is the D1b "shared discriminator +
regression suite" finding realised for the stub scanner specifically.

Run:  python test_stubscan_regression.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stubscan  # noqa: E402

# (label, text, path_or_None, expect_fire)
CASES = [
    # ---- SILENT: negation-blind _PHRASE (the F9 / INPUT class) ----
    (
        "neg: nothing to be added",
        "Fortunately §3.2 means nothing needs to be added to it.\n",
        None,
        False,
    ),
    ("neg: no work to be done", "There is no work to be done here.\n", None, False),
    (
        "neg: never implemented (assertion)",
        "This path is never implemented on purpose.\n",
        None,
        False,
    ),
    # ---- SILENT: markdown bold misread as a `* comment` (the D1 class) ----
    ("md bold **Stub**", "**Stub** of the verdict follows below.\n", None, False),
    (
        "md bold **Why.** with 'stub' in prose",
        "**Why.** The stub-vs-real distinction is the whole point.\n",
        None,
        False,
    ),
    # ---- SILENT: prose idiom "written down" (the D2 class) ----
    (
        "prose written down",
        "The verdict must be written down as a decision.\n",
        None,
        False,
    ),
    # ---- SILENT: regression-corpus fixture file is test data ----
    (
        "corpus jsonl exempt",
        '{"id":"x","text":"# TODO: implement"}\n',
        "harness-recovery/FAILURE-REPLAY-CORPUS/use-vs-mention.jsonl",
        False,
    ),
    # ---- FIRE: genuine stubs the fixes must NOT blind ----
    ("real TODO comment", "# TODO: implement the ranking pass\n", None, True),
    ("real FIXME", "// FIXME broken on empty input\n", None, True),
    ("NotImplementedError", "def f():\n    raise NotImplementedError\n", None, True),
    ("real to-be-implemented", "# this parser is to be implemented\n", None, True),
    ("real filled in later", "# config to be filled in later\n", None, True),
    ("pass-only body", "def handler(req):\n    pass\n", None, True),
    ("real placeholder comment", "x = 1  # placeholder until wired\n", None, True),
    ("block-comment star line", " * stub: returns fake data for now\n", None, True),
    # ---- SILENT: a GitHub issue ref must not make a line look like a comment ----
    (
        "md table row w/ issue ref + weak word",
        "| a native lazy-spawn flag exists | **FALSE** | 7 requests (#7336, #13805) all CLOSED "
        "NOT_PLANNED, consolidated into #17668 — still OPEN, unimplemented, last comment 2026-06-03 |\n",
        None,
        False,
    ),
    (
        "prose citing an issue number near 'stub'",
        "See #4821 for why the stub approach was rejected upstream.\n",
        None,
        False,
    ),
    # ---- FIRE: a real hash-comment must still be caught after the (?!\\d) narrowing ----
    (
        "real hash comment still fires",
        "# placeholder until the real parser lands\n",
        None,
        True,
    ),
]


def main() -> int:
    fails = 0
    for label, text, path, want in CASES:
        exempt = bool(path) and stubscan.is_test_file(path)
        got = False if exempt else bool(stubscan.find_stubs(text))
        ok = got == want
        if not ok:
            fails += 1
        print(
            f"  {'OK ' if ok else 'XX '} {label}: fired={got} want={want}"
            + (f" (exempt={exempt})" if path else "")
        )
    print(
        f"\nRESULT: {'ALL PASS' if not fails else str(fails) + ' FAIL'}  ({len(CASES)} cases)"
    )
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())

"""Blast radius: does ANY other tracked markdown page still assert the retracted rail verdict?

Residual 3 of the round-4 artifact said the scan set is one document and that I had surveyed only
three candidates. This closes it over the whole tracked tree instead of disclosing it. AGENTS.md
§9b: remediate the WHOLE set a bad claim touched, not the first symptom.

Two-stage so it is fast and still controlled: `git grep` at HEAD narrows to lines that could
possibly assert a state, then the SAME predicate `rail_count_gate.py` uses classifies them --
imported from the gate, so this cannot drift from what the gate enforces.

WHY THIS IS A GATE AND NOT A ONE-SHOT PROBE. `rail_count_gate.py`'s C6 reads a DECLARED list
(`SECONDARY_DOCS`), so it is structurally blind to a page nobody declared. Round 4 disclosed that
as a prospective residual. A survey run once by hand does not close it -- the next page is written
after the survey ran. This runs on every push and pull_request via
`.github/workflows/p2next-rail-count.yml`, and `ci/tests/test_p2next_tree_survey_wiring.py` fails
if that step is ever removed.

WHY `--check` EXISTS. Round 2 of this lane fixed `vendor_satisfiability.py` because re-running it
REWROTE the artifact it was supposed to verify. This had the same shape: `main()` wrote
`K4-TREE-SURVEY.json` on every run. CI now runs `--check`, which derives and asserts but never
writes, so the gate cannot launder its own receipt. The bare form still regenerates the receipt.

Run:  python command-center/p2-next/_k4_tree_survey.py              # derive + write the receipt
      python command-center/p2-next/_k4_tree_survey.py --check      # derive + assert, no write
      python command-center/p2-next/_k4_tree_survey.py --self-test  # both-states control
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECLARED = "up"  # what CROSS-VENDOR-RAIL-STATUS.md's RAIL-COUNT block declares
#: Pages whose JOB is to record what a past round believed. A build/verify artifact narrating the
#: retracted verdict is a record, not a live claim -- the use-vs-mention distinction, applied by
#: PATH so it is inspectable rather than buried in a regex.
HISTORICAL_PREFIX = (
    "command-center/p2-next/",
    "command-center/ssot/salvaged-from-scratch/",
)

_spec = importlib.util.spec_from_file_location(
    "_rcg4", Path(__file__).with_name("rail_count_gate.py")
)
_g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_g)


def parse_grep(lines: list[str]) -> list[tuple[str, int, str]]:
    """`git grep -n HEAD -- *.md` output -> (relpath, lineno, text).

    Split from classification so the classifier can be exercised without git.
    """
    out: list[tuple[str, int, str]] = []
    for raw in lines:
        try:
            _rev, rest = raw.split(":", 1)
            rel, rest2 = rest.split(":", 1)
            lineno, text = rest2.split(":", 1)
            out.append((rel, int(lineno), text))
        except ValueError:
            continue
    return out


def classify(
    records: list[tuple[str, int, str]], declared: str = DECLARED
) -> tuple[dict, dict]:
    """-> (live, historical). A record is a hit when it asserts a state OTHER than `declared`
    and does not carry the gate's dated exemption marker."""
    per_doc: dict[str, list] = defaultdict(list)
    for rel, lineno, text in records:
        for _ln, state, _t in _g.state_assertions(text):
            if state != declared and not _g.EXEMPT_MARKER.search(text):
                per_doc[rel].append((lineno, state, text.strip()[:110]))
    live = {k: v for k, v in per_doc.items() if not k.startswith(HISTORICAL_PREFIX)}
    historical = {k: v for k, v in per_doc.items() if k.startswith(HISTORICAL_PREFIX)}
    return live, historical


def git_grep() -> list[str]:
    grep = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "-i",
            "-e",
            "rail is",
            "-e",
            "rail are",
            "-e",
            "rail answers",
            "HEAD",
            "--",
            "*.md",
        ],
        cwd=REPO,
        capture_output=True,
    )
    return grep.stdout.decode("utf-8", "replace").splitlines()


#: Both-states cases. Every one names what it would mean if the classifier got it wrong, because a
#: self-test whose cases all expect SILENCE proves only that the instrument runs.
_SELFTEST = [
    # (label, records, want_live, want_historical)
    (
        "a live page asserting the retracted verdict FIRES",
        [
            (
                "command-center/NEW-OWNER-PAGE.md",
                7,
                "The rail is DOWN and it gates 42 units.",
            )
        ],
        1,
        0,
    ),
    (
        "a live page agreeing with the declaration is SILENT",
        [
            (
                "command-center/NEW-OWNER-PAGE.md",
                7,
                "The rail is up; two transports answered.",
            )
        ],
        0,
        0,
    ),
    (
        "the gate's dated exemption marker suppresses it",
        [
            (
                "command-center/NEW-OWNER-PAGE.md",
                7,
                "The rail is DOWN [superseded 2026-08-14] per round 3.",
            )
        ],
        0,
        0,
    ),
    (
        "a round artifact recording the retracted verdict is HISTORICAL, not live",
        [
            (
                "command-center/p2-next/P2NEXT-BUILD-R2.md",
                99,
                "The rail is DOWN, it was believed.",
            )
        ],
        0,
        1,
    ),
    (
        "a line naming no rail state is ignored entirely",
        [("command-center/NEW-OWNER-PAGE.md", 7, "The guard rail is painted green.")],
        0,
        0,
    ),
]


def self_test() -> int:
    ok = True
    fires = 0
    for label, records, want_live, want_hist in _SELFTEST:
        live, hist = classify(records)
        good = len(live) == want_live and len(hist) == want_hist
        fires += 1 if want_live or want_hist else 0
        ok = ok and good
        print(
            f"  {'ok ' if good else 'BAD'} {label}: live={len(live)} (want {want_live}) "
            f"historical={len(hist)} (want {want_hist})"
        )
    # The broken-detector path: an EMPTY survey must be reported as broken, not clean.
    empty_live, empty_hist = classify([])
    empty_good = not empty_live and not empty_hist
    ok = ok and empty_good
    print(
        f"  {'ok ' if empty_good else 'BAD'} an empty corpus yields an empty control "
        "(main() returns 2 on this, rather than SUCCESS)"
    )
    if not ok:
        print("FAILED:k4-tree-survey selftest a case did not discriminate")
        return 1
    print(
        f"selftest: PASS ({len(_SELFTEST) + 1} cases, {fires} of them expecting a hit, "
        "both states covered)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="derive and assert; never write the receipt",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()

    lines = git_grep()
    live, historical = classify(parse_grep(lines))

    print(f"candidate lines from git grep: {len(lines)}")
    print(
        f"tracked .md pages asserting {('down' if DECLARED == 'up' else 'up').upper()} unmarked:"
    )
    print(f"  LIVE (outside the historical record): {len(live)}")
    for rel, hits in sorted(live.items()):
        print(f"    {rel}: {[h[0] for h in hits]}")
        for h in hits[:3]:
            print(f"      L{h[0]} {h[2]!r}")
    print(f"  HISTORICAL round artifacts (record, not claim): {len(historical)}")
    for rel, hits in sorted(historical.items()):
        print(f"    {rel}: {len(hits)} line(s)")

    # CONTROL: the survey must be able to FIND one. If the historical bucket were also empty, the
    # zero above would be indistinguishable from a broken grep or a mis-split line.
    control = bool(historical)
    print(
        f"CONTROL the survey CAN find an assertion (historical bucket non-empty): {control}"
    )

    if not args.check:
        (REPO / "command-center/p2-next/K4-TREE-SURVEY.json").write_text(
            json.dumps(
                {
                    "declared": DECLARED,
                    "candidate_lines": len(lines),
                    "live": live,
                    "historical_counts": {k: len(v) for k, v in historical.items()},
                    "control_can_find": control,
                },
                indent=2,
            ),
            encoding="utf-8",
            newline="\n",
        )
    if not control:
        print(
            "FAILED:k4-tree-survey the survey found nothing at all; treat it as broken, not clean"
        )
        return 2
    print(
        "SUCCESS:k4-tree-survey"
        if not live
        else "FAILED:k4-tree-survey live pages still assert it"
    )
    return 0 if not live else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Blast radius: does ANY other tracked markdown page still assert the retracted rail verdict?

Residual 3 of the round-4 artifact said the scan set is one document and that I had surveyed only
three candidates. This closes it over the whole tracked tree instead of disclosing it. AGENTS.md
§9b: remediate the WHOLE set a bad claim touched, not the first symptom.

Two-stage so it is fast and still controlled: `git grep` at HEAD narrows to lines that could
possibly assert a state, then the SAME predicate `rail_count_gate.py` uses classifies them --
imported from the gate, so this cannot drift from what the gate enforces.

Run:  python command-center/p2-next/_k4_tree_survey.py
"""

from __future__ import annotations

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


def main() -> int:
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
    lines = grep.stdout.decode("utf-8", "replace").splitlines()

    per_doc: dict[str, list] = defaultdict(list)
    for raw in lines:
        try:
            _rev, rest = raw.split(":", 1)
            rel, rest2 = rest.split(":", 1)
            lineno, text = rest2.split(":", 1)
        except ValueError:
            continue
        for _ln, state, _t in _g.state_assertions(text):
            if state != DECLARED and not _g.EXEMPT_MARKER.search(text):
                per_doc[rel].append((int(lineno), state, text.strip()[:110]))

    live = {k: v for k, v in per_doc.items() if not k.startswith(HISTORICAL_PREFIX)}
    historical = {k: v for k, v in per_doc.items() if k.startswith(HISTORICAL_PREFIX)}

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

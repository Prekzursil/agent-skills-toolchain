#!/usr/bin/env python3
"""Probe 1: production linter on 50 confusable + 50 distinct pairs.

Signal (a): tools.marketplace.name_linter flags each confusable candidate with
confused_with equal to the intended installed name, and stays silent on the
distinct set. Reports precision, recall, and a false-positive ceiling.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from corpus import (  # noqa: E402
    CONFUSABLE,
    DISTINCT_CANDIDATES,
    INSTALLED,
    assert_corpus,
)
from marketplace.name_linter import lint_candidate  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0218-probe1 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    assert_corpus()
    installed = list(INSTALLED)

    tp = 0
    fn_rows: list[dict] = []
    confusable_hits: list[dict] = []
    for target, candidate, kind in CONFUSABLE:
        flags = lint_candidate(candidate, installed)
        names = [f.confused_with for f in flags]
        hit = target in names
        if hit:
            tp += 1
        else:
            fn_rows.append(
                {
                    "target": target,
                    "candidate": candidate,
                    "kind": kind,
                    "confused_with": names,
                }
            )
        confusable_hits.append(
            {
                "target": target,
                "candidate": candidate,
                "kind": kind,
                "flagged": bool(flags),
                "confused_with": names,
                "reasons": [f.reason for f in flags],
            }
        )

    fp_rows: list[dict] = []
    for candidate in DISTINCT_CANDIDATES:
        flags = lint_candidate(candidate, installed)
        if flags:
            fp_rows.append(
                {
                    "candidate": candidate,
                    "confused_with": [f.confused_with for f in flags],
                    "reasons": [f.reason for f in flags],
                }
            )

    fn = len(fn_rows)
    fp = len(fp_rows)
    n_pos = len(CONFUSABLE)
    n_neg = len(DISTINCT_CANDIDATES)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / n_pos if n_pos else 0.0
    fp_rate = fp / n_neg if n_neg else 0.0
    fp_ceiling = 0.0

    both_states = {
        "confusable_example": {
            "installed": CONFUSABLE[0][0],
            "candidate": CONFUSABLE[0][1],
            "kind": CONFUSABLE[0][2],
            "flagged": target_in_flags(CONFUSABLE[0][0], CONFUSABLE[0][1], installed),
        },
        "distinct_example": {
            "candidate": DISTINCT_CANDIDATES[0],
            "flagged": bool(lint_candidate(DISTINCT_CANDIDATES[0], installed)),
        },
    }

    payload = {
        "probe": "probe1-linter-corpus",
        "unit_id": "TST-0218",
        "installed_n": len(installed),
        "confusable_n": n_pos,
        "distinct_n": n_neg,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fp_rate,
        "false_positive_ceiling": fp_ceiling,
        "confused_with_always_reported": tp == n_pos and all(
            row["confused_with"] for row in confusable_hits if row["flagged"]
        ),
        "both_states": both_states,
        "fn_rows": fn_rows,
        "fp_rows": fp_rows,
        "pass": True,
    }

    if n_pos != 50 or n_neg != 50:
        return fail("corpus sizes are not 50/50", payload)
    if fn_rows:
        payload["pass"] = False
        return fail("confusable pair missed or wrong confused_with", payload)
    if fp_rows:
        payload["pass"] = False
        return fail("distinct pair flagged (false positive)", payload)
    if precision < 1.0 or recall < 1.0:
        payload["pass"] = False
        return fail("precision/recall below 1.0 on this corpus", payload)
    if fp_rate > fp_ceiling:
        payload["pass"] = False
        return fail("false-positive rate exceeds stated ceiling", payload)
    if not both_states["confusable_example"]["flagged"]:
        return fail("both-states: confusable example not flagged")
    if both_states["distinct_example"]["flagged"]:
        return fail("both-states: distinct example was flagged")

    print(json.dumps(payload, sort_keys=True))
    print(
        f"tp={tp} fp={fp} fn={fn} precision={precision:.2f} "
        f"recall={recall:.2f} fp_ceiling={fp_ceiling:.2f}"
    )
    print("SUCCESS:TST-0218-probe1 linter corpus 50/50 precision=1 recall=1")
    return 0


def target_in_flags(target: str, candidate: str, installed: list[str]) -> bool:
    return target in [f.confused_with for f in lint_candidate(candidate, installed)]


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe 2: independent direct recount + negative controls (verbatim)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import direct as D  # noqa: E402
import expr as E  # noqa: E402
import fixtures as F  # noqa: E402
import table as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0121-stopping-rule-both-states-simulation-across-all-six-requir.md"
)


def main() -> int:
    table = T.run_table()
    disagreements = []
    for spec in F.expressions():
        for label, fname in (("true", spec["true_fixture"]), ("false", spec["false_fixture"])):
            _, metrics = F.load_fixture(fname)
            public = {k: v for k, v in metrics.items() if not str(k).startswith("_")}
            parsed = E.evaluate(spec["expression"], public)
            recounted = D.evaluate_id(spec["id"], public)
            if parsed != recounted:
                disagreements.append(
                    {
                        "id": spec["id"],
                        "state": label,
                        "parser": parsed,
                        "direct": recounted,
                    }
                )
    negs = T.negative_controls()
    print(json.dumps(
        {
            "probe": "probe2-negative-and-recount",
            "disagreements": disagreements,
            "negative_pass": [n["id"] for n in negs if n["pass"]],
            "negative_fail": [n["id"] for n in negs if not n["pass"]],
            "table_fire_on_true": table["fire_on_true"],
            "table_silent_on_false": table["silent_on_false"],
        },
        sort_keys=True,
    ))
    for n in negs:
        print(n["verbatim"])
        print(f"  rejects={n['rejects']}")
        print(f"  observed={n['observed']} pass={n['pass']}")

    if disagreements:
        print("FAILED:CNL-0121-probe2 reviewer recount disagrees with parser")
        return 1
    if not all(n["pass"] for n in negs):
        print("FAILED:CNL-0121-probe2 negative control did not discriminate")
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0121-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_negs = doc.get("negative_controls") or []
    if len(art_negs) < 1:
        print("FAILED:CNL-0121-probe2 artifact missing negative_controls")
        return 1
    for n in art_negs:
        if not n.get("verbatim"):
            print(f"FAILED:CNL-0121-probe2 artifact control {n.get('id')} has empty verbatim")
            return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True or reviewer.get("verdict") != "PASS":
        print("FAILED:CNL-0121-probe2 reviewer not independent PASS")
        return 1
    print("SUCCESS:CNL-0121-probe2 recount and negative controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

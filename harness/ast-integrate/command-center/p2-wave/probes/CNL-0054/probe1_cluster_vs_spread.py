#!/usr/bin/env python3
"""Probe 1: clustered scores lower than spread; both-states + negative control.

Planted-bad = clustered (24 ideas in 2 categories) -> detector FIRES.
Known-good = spread (3 ideas x 8 categories) -> detector SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import measure as M  # noqa: E402

ART = (
    HERE.parents[3]
    / "command-center/design/council/CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md"
)


def _fmt(row: dict) -> str:
    j = row.get("joint")
    c = row.get("coverage")
    j_s = "null" if j is None else f"{j:.12f}"
    c_s = "null" if c is None else f"{c:.12f}"
    return (
        f"valid={row['valid']} n={row['n']} coverage={c_s} joint={j_s} "
        f"fires={row['fires']} reason={row['reason']}"
    )


def main() -> int:
    F.assert_counts()
    tax = M.load_taxonomy()
    clustered = M.score(F.clustered(), tax)
    spread = M.score(F.spread(), tax)
    token = M.score(F.token_coverage(), tax)
    invalid = M.score(F.invalid_label(), tax)

    print("PLANTED-BAD clustered: " + _fmt(clustered))
    print("KNOWN-GOOD spread: " + _fmt(spread))
    print("TOKEN-COVERAGE diagnostic: " + _fmt(token))
    print("INVALID-LABEL: " + _fmt(invalid))

    if clustered["joint"] is None or spread["joint"] is None:
        print("FAILED:CNL-0054-probe1 missing joint on clustered or spread")
        return 1
    if not (clustered["joint"] < spread["joint"]):
        print(
            f"FAILED:CNL-0054-probe1 clustered joint {clustered['joint']} "
            f"not lower than spread {spread['joint']}"
        )
        return 1
    if clustered["n"] != spread["n"]:
        print("FAILED:CNL-0054-probe1 raw counts differ")
        return 1

    if not clustered["fires"]:
        print("FAILED:CNL-0054-probe1 planted-bad did not FIRE")
        return 1
    if spread["fires"]:
        print("FAILED:CNL-0054-probe1 known-good was not SILENT")
        return 1
    if not invalid["fires"] or invalid["reason"] != "out-of-taxonomy-label":
        print("FAILED:CNL-0054-probe1 invalid label did not FIRE as out-of-taxonomy")
        return 1

    if token["coverage"] != spread["coverage"]:
        print("FAILED:CNL-0054-probe1 token coverage should equal spread coverage")
        return 1
    if token["coverage"] != 1.0:
        print(f"FAILED:CNL-0054-probe1 token coverage {token['coverage']} != 1.0")
        return 1
    if not token["fires"]:
        print("FAILED:CNL-0054-probe1 token-coverage did not FIRE on the joint gate")
        return 1
    if token["joint"] is None or not (token["joint"] < spread["joint"]):
        print("FAILED:CNL-0054-probe1 token joint not below spread")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec_c = doc.get("fixture_scores", {}).get("clustered", {})
        rec_s = doc.get("fixture_scores", {}).get("spread", {})
        if rec_c.get("fires") is not True or rec_s.get("fires") is not False:
            print("FAILED:CNL-0054-probe1 artifact both-states drift")
            return 1
        if abs(float(rec_c["joint"]) - float(clustered["joint"])) > 1e-12:
            print("FAILED:CNL-0054-probe1 artifact clustered joint drift")
            return 1
        if abs(float(rec_s["joint"]) - float(spread["joint"])) > 1e-12:
            print("FAILED:CNL-0054-probe1 artifact spread joint drift")
            return 1

    print(
        "NEGATIVE CONTROL verbatim: on the clustered bag the check FIRES "
        f"(joint={clustered['joint']:.12f} < threshold={clustered['threshold']}); "
        "it does not stay silent and it does not award high coverage as spread."
    )
    print(
        "BOTH-STATES: FIRED on planted-bad clustered; SILENT on known-good spread; "
        f"same n={clustered['n']}"
    )
    print("SUCCESS:CNL-0054-probe1 clustered<spread both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

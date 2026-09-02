#!/usr/bin/env python3
"""Probe 2: A10 parse unchanged + independent mechanism recount + identity disagree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import SPEC_EXPRESSIONS, accepted_unchanged  # noqa: E402
from census import census_completeness_score  # noqa: E402
from evaluate import bound_eval, mixed_unbound  # noqa: E402
from fixtures import FIXTURES, REQUIRED  # noqa: E402
from recount import recount  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0078-executable-stopping-example-unique-ideas-100-and-completen.schema.json"
)
EXPR = "unique_ideas >= 100 AND completeness_score >= 0.90"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:CNL-0078-probe2 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if "SUCCESS:CNL-0078" not in OUT.read_text(encoding="utf-8"):
        print("FAILED:CNL-0078-probe2 sentinel-absent")
        return 1

    fail = False
    for line, src in SPEC_EXPRESSIONS:
        info = accepted_unchanged(src)
        ok = info["accepted"] and info["tokens_match"] and info["src_preserved"]
        print(
            f"parse line={line} accepted={ok} tokens_match={info['tokens_match']} "
            f"src_preserved={info['src_preserved']} pretty={info['pretty']}"
        )
        if not ok:
            fail = True
        if src == EXPR and info["pretty"] != EXPR:
            print("FAILED:CNL-0078-probe2 CNL-0078 expression rewritten by pretty()")
            fail = True

    rows = doc.get("spec_anchor", {}).get("six_examples") or []
    if len(rows) != 6:
        print(f"FAILED:CNL-0078-probe2 expected 6 parse rows got {len(rows)}")
        return 1

    for name, builder in FIXTURES.items():
        ledger = builder()
        author = bound_eval(ledger, REQUIRED)
        indep = recount(ledger, REQUIRED)
        agree = (
            indep["unique_ideas"] == author["unique_ideas"]
            and indep["completeness_score"] == author["completeness_score"]
        )
        print(
            f"recount {name}: author unique={author['unique_ideas']} "
            f"score={author['completeness_score']} "
            f"indep unique={indep['unique_ideas']} score={indep['completeness_score']} "
            f"agree={agree} method={indep['method']}"
        )
        if not agree:
            print("FAILED:CNL-0078-probe2 independent recount disagreement")
            fail = True

    disagree = mixed_unbound(FIXTURES["disagree"](), REQUIRED)
    bound_d = bound_eval(FIXTURES["disagree"](), REQUIRED)
    print(
        f"disagree bound verdict={bound_d['verdict']} unique={bound_d['unique_ideas']} "
        f"score={bound_d['completeness_score']}"
    )
    print(
        f"disagree mixed verdict={disagree['verdict']} fired={disagree['fired']} "
        f"naive_and={disagree['naive_and']} unique={disagree['unique_ideas']} "
        f"score={disagree['completeness_score']}"
    )
    if bound_d["verdict"] != "SILENT" or bound_d["unique_ideas"] != 10:
        print("FAILED:CNL-0078-probe2 bound disagree should be SILENT unique=10")
        fail = True
    if disagree["verdict"] != "UNBOUND" or disagree["fired"] is not False:
        print("FAILED:CNL-0078-probe2 mixed identities must be UNBOUND")
        fail = True
    if disagree["naive_and"] is not True:
        print("FAILED:CNL-0078-probe2 naive conjunction should be satisfiable under disagreement")
        fail = True
    rec_mixed = ((doc.get("fixture_runs") or {}).get("disagree") or {}).get("mixed_raw_gamed") or {}
    if rec_mixed.get("naive_and") is not True or rec_mixed.get("verdict") != "UNBOUND":
        print(f"FAILED:CNL-0078-probe2 artifact mixed row {rec_mixed}")
        fail = True

    pop = census_completeness_score(REPO)
    print(
        f"census completeness_score hits={pop['hit_count']} "
        f"undefined={pop['undefined_component']} "
        f"unique_ideas_py={pop['tools_council_quota_unique_ideas_py']}"
    )
    if pop["hit_count"] != 0:
        print(f"FAILED:CNL-0078-probe2 unexpected producer {pop['completeness_score_hits_outside_catalog_and_this_unit']}")
        fail = True
    if doc.get("answer", {}).get("undefined_component") != "coverage_domain_identity":
        print("FAILED:CNL-0078-probe2 artifact missing undefined component")
        fail = True

    if fail:
        print("FAILED:CNL-0078-probe2 parse/recount/disagree")
        return 1
    print("SUCCESS:CNL-0078-probe2 parse-unchanged independent-recount identity-bind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

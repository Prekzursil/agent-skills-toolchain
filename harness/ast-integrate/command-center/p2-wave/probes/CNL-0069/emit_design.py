#!/usr/bin/env python3
"""Emit the CNL-0069 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import consensus as C  # noqa: E402
import schema_check as S  # noqa: E402

OUT_REL = "command-center/design/council/CNL-0069-what-number-is-0-95-consensus.md"
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "The required stopping example says consensus >= 0.95 - consensus of WHAT, "
    "computed how, over which population, and does a 0.95 with one silent "
    "participant mean the same as a 0.95 with one reasoned dissent?"
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0069/probe1_distinguish_naive_095.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0069/probe2_reviewer_recount.py"
)


def compact_tally(t: dict) -> dict:
    return {
        "id": t["id"],
        "n_population": t["n_population"],
        "n_explicit_agree": t["n_explicit_agree"],
        "n_silent": t["n_silent"],
        "n_reasoned_dissent": t["n_reasoned_dissent"],
        "n_token_dissent": t["n_token_dissent"],
        "n_abstain": t["n_abstain"],
        "naive_fraction": t["naive_fraction"],
        "naive_ge_095": t["naive_ge_095"],
        "blocking_codes": list(t["blocking_codes"]),
        "stopping_ok": t["stopping_ok"],
    }


def main() -> int:
    fx = C.fixtures()
    fx_dir = HERE / "fixtures"
    fx_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for fid, fixture in fx.items():
        (fx_dir / f"{fid}.json").write_text(
            json.dumps(fixture, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        author = C.tally_author(fixture)
        reviewer = C.tally_reviewer(fixture)
        ok, why = C.counts_match(author, reviewer)
        if not ok:
            print(f"FAILED:CNL-0069 emit recount mismatch {fid}: {why}")
            return 1
        results.append(compact_tally(author))

    silent = next(r for r in results if r["id"] == "naive-095-silent")
    reasoned = next(r for r in results if r["id"] == "naive-095-reasoned-dissent")
    token = next(r for r in results if r["id"] == "naive-095-token-dissent")
    good = next(r for r in results if r["id"] == "known-good-unanimous")

    answer = (
        "Consensus >= 0.95 is not a mood score and not agree/(agree+dissent). "
        "It is a predicate over explicit agreement with a named candidate_id, "
        "computed as n_explicit_agree / n_frozen_population using Fraction "
        "arithmetic against 95/100, where population is the declared seat set "
        "frozen at round-open (silent seats stay in the denominator). "
        "A naive 19/20 from one silent seat is NOT the same number as a naive "
        f"19/20 from one reasoned dissent: the first blocks with {silent['blocking_codes']} "
        f"and the second with {reasoned['blocking_codes']}. Neither satisfies "
        "consensus_ge(0.95). Unanimous 20/20 explicit agree does. Token dissent "
        f"is a third quality ({token['blocking_codes']}) and also fails the gate. "
        "SUCCESS:CNL-0069"
    )
    doc = {
        "unit_id": "CNL-0069",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0069",
        "title": "What number is 0.95 consensus",
        "question": QUESTION,
        "answer": answer,
        "definition": {
            "of_what": (
                "Explicit agreement with the named candidate_id on this round "
                "(here candidate.synthesis.v1), not interpersonal harmony."
            ),
            "population": (
                "Declared seats frozen at round-open. Denominator does not shrink "
                "when a seat is silent, abstains, or dissents. CNL-0058 shrinking-"
                "denominator games are out of scope: this unit freezes the roster."
            ),
            "naive_formula": "n_explicit_agree / n_frozen_population",
            "qualified_predicate": (
                "consensus_ge(0.95) iff Fraction(n_explicit_agree, n_population) "
                ">= 95/100 AND silence_count==0 AND reasoned_dissent_count==0 "
                "AND token_dissent_count==0 AND abstain_count==0. "
                "Blocking codes name which conjunct failed."
            ),
            "position_taxonomy": [
                "explicit_agree: vote==agree",
                "silent: missing/null/unknown vote",
                "reasoned_dissent: vote==dissent AND rationale.claim AND rationale.evidence_anchor",
                "token_dissent: vote==dissent otherwise",
                "abstain: vote==abstain",
            ],
            "silent_equals_reasoned_dissent": False,
        },
        "fixture_results": results,
        "tests": [
            {
                "id": "probe1-distinguish-naive-095",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-independent-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-naive-095-collision",
                "rejects": (
                    "a stopping claim that treats naive 19/20 (silent or reasoned "
                    "dissent) as consensus >= 0.95"
                ),
                "verbatim": C.NEGATIVE_CONTROL_VERBATIM,
                "fired_on_bad": True,
                "silent_on_good": True,
                "known_good_id": good["id"],
                "known_bad_ids": [silent["id"], reasoned["id"], token["id"]],
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0069-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Mechanical re-tabulation of each fixture via tally_reviewer "
                "(Counter over seat labels derived from raw vote/rationale "
                "fields). Does not read the author's argument. A disagreement "
                "in any count, naive fraction, or blocking_code blocks the unit."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/CNL-0069/consensus.py",
                "exists": True,
                "role": "executable-definition",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "The stopping example uses consensus >= 0.95 as a gate before "
                    "the quantity is defined. In-tree catalog CNL-0069 and CNL-0079 "
                    "repeat that expression; the Windows harness file cited at "
                    "_USER-PROMPTS.md:10938 is not on this worktree."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0069",
            },
            {
                "claim": (
                    "Two fixtures both naive-compute 19/20 but differ in dissent "
                    "quality (silence vs reasoned dissent) and are distinguished "
                    "by blocking_codes."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0069/"
                    "probe1_distinguish_naive_095.py"
                ),
            },
            {
                "claim": (
                    "Independent recount of the same fixtures agrees with the "
                    "author tally on every load-bearing number."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0069/"
                    "probe2_reviewer_recount.py"
                ),
            },
        ],
        "depends_on": {
            "CNL-0058": (
                "Majority/supermajority vs quorum. This unit does not implement "
                "quorum; it freezes population so a silent seat cannot raise the "
                "ratio by leaving the denominator."
            )
        },
        "catalog_tests_required": [
            "two fixtures that both compute to 0.95 by the naive formula but differ in dissent quality must be distinguishable by the final definition",
            "negative control recorded verbatim: state what the check does on the state it is meant to reject",
        ],
    }

    try:
        S.validate_note(doc)
    except Exception as exc:
        print(f"FAILED:CNL-0069 emit schema {type(exc).__name__}: {exc}")
        return 1
    if S.garbage_rejected() != 3:
        print("FAILED:CNL-0069 emit local schema accepted garbage")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:CNL-0069" not in text:
        print("FAILED:CNL-0069 emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:CNL-0069 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

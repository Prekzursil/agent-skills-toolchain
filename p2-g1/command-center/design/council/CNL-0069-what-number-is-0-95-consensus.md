{
  "answer": "Consensus >= 0.95 is not a mood score and not agree/(agree+dissent). It is a predicate over explicit agreement with a named candidate_id, computed as n_explicit_agree / n_frozen_population using Fraction arithmetic against 95/100, where population is the declared seat set frozen at round-open (silent seats stay in the denominator). A naive 19/20 from one silent seat is NOT the same number as a naive 19/20 from one reasoned dissent: the first blocks with ['SILENCE_IN_FROZEN_POPULATION'] and the second with ['REASONED_DISSENT_UNRESOLVED']. Neither satisfies consensus_ge(0.95). Unanimous 20/20 explicit agree does. Token dissent is a third quality (['TOKEN_DISSENT_UNRESOLVED']) and also fails the gate. SUCCESS:CNL-0069",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0069-what-number-is-0-95-consensus.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "contract"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0069/consensus.py",
      "role": "executable-definition"
    }
  ],
  "catalog_tests_required": [
    "two fixtures that both compute to 0.95 by the naive formula but differ in dissent quality must be distinguishable by the final definition",
    "negative control recorded verbatim: state what the check does on the state it is meant to reject"
  ],
  "definition": {
    "naive_formula": "n_explicit_agree / n_frozen_population",
    "of_what": "Explicit agreement with the named candidate_id on this round (here candidate.synthesis.v1), not interpersonal harmony.",
    "population": "Declared seats frozen at round-open. Denominator does not shrink when a seat is silent, abstains, or dissents. CNL-0058 shrinking-denominator games are out of scope: this unit freezes the roster.",
    "position_taxonomy": [
      "explicit_agree: vote==agree",
      "silent: missing/null/unknown vote",
      "reasoned_dissent: vote==dissent AND rationale.claim AND rationale.evidence_anchor",
      "token_dissent: vote==dissent otherwise",
      "abstain: vote==abstain"
    ],
    "qualified_predicate": "consensus_ge(0.95) iff Fraction(n_explicit_agree, n_population) >= 95/100 AND silence_count==0 AND reasoned_dissent_count==0 AND token_dissent_count==0 AND abstain_count==0. Blocking codes name which conjunct failed.",
    "silent_equals_reasoned_dissent": false
  },
  "depends_on": {
    "CNL-0058": "Majority/supermajority vs quorum. This unit does not implement quorum; it freezes population so a silent seat cannot raise the ratio by leaving the denominator."
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0069",
      "claim": "The stopping example uses consensus >= 0.95 as a gate before the quantity is defined. In-tree catalog CNL-0069 and CNL-0079 repeat that expression; the Windows harness file cited at _USER-PROMPTS.md:10938 is not on this worktree.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0069/probe1_distinguish_naive_095.py",
      "claim": "Two fixtures both naive-compute 19/20 but differ in dissent quality (silence vs reasoned dissent) and are distinguished by blocking_codes.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0069/probe2_reviewer_recount.py",
      "claim": "Independent recount of the same fixtures agrees with the author tally on every load-bearing number.",
      "verdict": "CONFIRMED"
    }
  ],
  "fixture_results": [
    {
      "blocking_codes": [
        "SILENCE_IN_FROZEN_POPULATION"
      ],
      "id": "naive-095-silent",
      "n_abstain": 0,
      "n_explicit_agree": 19,
      "n_population": 20,
      "n_reasoned_dissent": 0,
      "n_silent": 1,
      "n_token_dissent": 0,
      "naive_fraction": "19/20",
      "naive_ge_095": true,
      "stopping_ok": false
    },
    {
      "blocking_codes": [
        "REASONED_DISSENT_UNRESOLVED"
      ],
      "id": "naive-095-reasoned-dissent",
      "n_abstain": 0,
      "n_explicit_agree": 19,
      "n_population": 20,
      "n_reasoned_dissent": 1,
      "n_silent": 0,
      "n_token_dissent": 0,
      "naive_fraction": "19/20",
      "naive_ge_095": true,
      "stopping_ok": false
    },
    {
      "blocking_codes": [
        "TOKEN_DISSENT_UNRESOLVED"
      ],
      "id": "naive-095-token-dissent",
      "n_abstain": 0,
      "n_explicit_agree": 19,
      "n_population": 20,
      "n_reasoned_dissent": 0,
      "n_silent": 0,
      "n_token_dissent": 1,
      "naive_fraction": "19/20",
      "naive_ge_095": true,
      "stopping_ok": false
    },
    {
      "blocking_codes": [],
      "id": "known-good-unanimous",
      "n_abstain": 0,
      "n_explicit_agree": 20,
      "n_population": 20,
      "n_reasoned_dissent": 0,
      "n_silent": 0,
      "n_token_dissent": 0,
      "naive_fraction": "20/20",
      "naive_ge_095": true,
      "stopping_ok": true
    }
  ],
  "negative_controls": [
    {
      "fired_on_bad": true,
      "id": "NC-naive-095-collision",
      "known_bad_ids": [
        "naive-095-silent",
        "naive-095-reasoned-dissent",
        "naive-095-token-dissent"
      ],
      "known_good_id": "known-good-unanimous",
      "rejects": "a stopping claim that treats naive 19/20 (silent or reasoned dissent) as consensus >= 0.95",
      "silent_on_good": true,
      "verbatim": "On fixture naive-095-silent (19 explicit_agree, 1 silent, n=20), naive_ratio=19/20=0.95 and consensus_ge(0.95) returns ok=False blocking_codes=['SILENCE_IN_FROZEN_POPULATION']. The check REJECTS a naive 0.95 that includes a silent seat. On fixture naive-095-reasoned-dissent (19 explicit_agree, 1 reasoned_dissent, n=20), naive_ratio=19/20=0.95 and consensus_ge(0.95) returns ok=False blocking_codes=['REASONED_DISSENT_UNRESOLVED']. The check REJECTS a naive 0.95 that treats reasoned dissent as a rounding error. On fixture known-good-unanimous (20 explicit_agree, n=20), naive_ratio=20/20=1 and consensus_ge(0.95) returns ok=True blocking_codes=[]. The check is SILENT on unanimous explicit agreement."
    }
  ],
  "question": "The required stopping example says consensus >= 0.95 - consensus of WHAT, computed how, over which population, and does a 0.95 with one silent participant mean the same as a 0.95 with one reasoned dissent?",
  "reviewer": {
    "independent": true,
    "method": "Mechanical re-tabulation of each fixture via tally_reviewer (Counter over seat labels derived from raw vote/rationale fields). Does not read the author's argument. A disagreement in any count, naive fraction, or blocking_code blocks the unit.",
    "reviewer_id": "CNL-0069-probe2-independent-recount",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0069",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0069/probe1_distinguish_naive_095.py",
      "id": "probe1-distinguish-naive-095",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0069/probe2_reviewer_recount.py",
      "id": "probe2-independent-recount",
      "result": "PASS"
    }
  ],
  "title": "What number is 0.95 consensus",
  "unit_id": "CNL-0069"
}

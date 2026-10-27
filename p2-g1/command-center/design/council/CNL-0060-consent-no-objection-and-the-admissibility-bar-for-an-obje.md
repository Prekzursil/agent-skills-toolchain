{
  "answer": "Consent / no-objection is fail-closed on admissible objections and fail-open on unfalsifiable ones. After a recorded window, the proposal is CONSENTED iff the set of ADMISSIBLE objections is empty. Silence of a seated participant is defined as consent under this protocol only (it is not inherited by unanimity or majority). An objection is admissible only when (1) the objector is seated, (2) the window is open, (3) the target names a live claim on this proposal, (4) the record validates against the objection schema, and (5) the falsifier DISCRIMINATES: a counterexample instance makes the claim's registered predicate return False, or a vacuity pair shows the predicate does not distinguish the proposer's known-good from known-bad. Unfalsifiable concerns (kind=concern, empty instance, instance that still satisfies the predicate, unseated filings) are INADMISSIBLE and do not block. Repeated identical inadmissible filings still do not block. A concrete counterexample still stands \u2014 the bar is not 'ignore all objections'. Chair waiver of an admissible objection is refused here; that is a veto-override path (CNL-0024), not consent. A proposal whose own known-bad still passes its predicate cannot open a consent window.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0060-consent-no-objection-and-the-admissibility-bar-for-an-obje.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0060/admissibility.py",
      "role": "checker"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0060/objection.schema.json",
      "role": "objection-schema"
    }
  ],
  "both_states": {
    "fired_means": "hostage-detector fires = evaluate.admissible False on unfalsifiable",
    "fired_on_planted_bad": true,
    "known_good_verbatim": "evaluate(counterexample) admissible=True code=ADMISSIBLE predicate_false=True schema_ok=True consent_outcome=BLOCKED",
    "planted_bad_verbatim": "evaluate(unfalsifiable) admissible=False code=UNFALSIFIABLE schema_ok=False consent_outcome=CONSENTED blocker_count=0",
    "silent_means": "hostage-detector silent = evaluate.admissible True on real break",
    "silent_on_known_good": true
  },
  "claims": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0060/admissibility.py:158",
      "claim": "Unfalsifiable objections are inadmissible and do not block.",
      "id": "C1",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0060/admissibility.py:247",
      "claim": "A concrete counterexample that falsifies the claim stands and blocks.",
      "id": "C2",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0060/admissibility.py:43",
      "claim": "Schema and predicate evaluation are independent signals.",
      "id": "C3",
      "verdict": "CONFIRMED"
    }
  ],
  "dependencies_on_this_tree": {
    "CNL-0023": "absent \u2014 vote-weight provenance not required to execute the bar",
    "CNL-0024": "absent \u2014 veto override is a different protocol; not guessed"
  },
  "detector": {
    "id": "cnl-0060-admissibility-bar",
    "pair_and_gate_note": "Rejected treating two schema checks, or two restatements of admissible, as independent signals. The pair is schema vs predicate outcome, different functions, different fields.",
    "pair_and_gate_rejected": true,
    "signals": [
      {
        "id": "schema",
        "mechanism": "jsonschema Draft-07 over objection.schema.json",
        "role": "shape: kind in {counterexample,vacuity}; instance required"
      },
      {
        "id": "predicate-eval",
        "mechanism": "registered predicate on instance / vacuity pair",
        "role": "discrimination: predicate False, or pair does not split"
      }
    ],
    "stopping_bind": "Admission is fail-closed AND: both schema_ok and discrimination must pass before an objection can block. Schema-only success is not admission (the dressed known-good instance is refused). OR-admission is rejected because a schema-valid vibe would hostage."
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:37281",
      "claim": "Catalog question is the unit's load-bearing question.",
      "command": "python3 -c 'print(open(\"command-center/WORK-UNIT-CATALOG.json\").read().count(\"CNL-0060\"))'",
      "raw_output": "id and question rows present in catalog",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0060/admissibility.py:158",
      "claim": "Live evaluate() refuses unfalsifiable and admits the known-bad instance.",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0060/probe1_both_states.py",
      "raw_output": "evaluate(unfalsifiable) admissible=False code=UNFALSIFIABLE schema_ok=False consent_outcome=CONSENTED blocker_count=0 | evaluate(counterexample) admissible=True code=ADMISSIBLE predicate_false=True schema_ok=True consent_outcome=BLOCKED",
      "verdict": "CONFIRMED"
    }
  ],
  "live": {
    "eval_counterexample": {
      "admissible": true,
      "claim_id": "consent-excludes-absent",
      "code": "ADMISSIBLE",
      "predicate_false": true,
      "predicate_id": "exclude_absent",
      "schema_errors": [],
      "schema_ok": true
    },
    "eval_unfalsifiable": {
      "admissible": false,
      "code": "UNFALSIFIABLE",
      "eval_code": "UNKNOWN_KIND",
      "kind": "concern",
      "predicate_false": null,
      "schema_errors": [
        "'concern' is not one of ['counterexample', 'vacuity']",
        "Additional properties are not allowed ('note' was unexpected)"
      ],
      "schema_ok": false
    },
    "hostage_blocker_count": 0,
    "outcome_counterexample": "BLOCKED",
    "outcome_triple_unfalsifiable": "CONSENTED",
    "outcome_unfalsifiable": "CONSENTED",
    "proposal_eligible": {
      "claim_count": 1,
      "eligible": true,
      "reason": "DISCRIMINATES"
    },
    "schema_counterexample": {
      "errors": [],
      "ok": true
    },
    "schema_unfalsifiable": {
      "errors": [
        "'concern' is not one of ['counterexample', 'vacuity']",
        "Additional properties are not allowed ('note' was unexpected)"
      ],
      "ok": false
    },
    "vacuous_eligible": {
      "claim_id": "anything-goes",
      "eligible": false,
      "reason": "KNOWN_BAD_PASSES"
    }
  },
  "negative_control": {
    "state_meant_to_reject": "unfalsifiable concern (kind=concern, no discriminating instance)",
    "verbatim": "On fixture objection-unfalsifiable.json (kind=concern, no instance) schema_ok=False evaluate.admissible=False code=UNFALSIFIABLE outcome=CONSENTED. The check REFUSES the block so an unfalsifiable concern cannot hostage the council. If this fixture were admitted, one seat could stall every consent decision.",
    "what_the_check_does": "REFUSES admissibility and leaves consent CONSENTED; does not block"
  },
  "planted_mutant_control": {
    "per_class_recall": [
      {
        "caught": 1,
        "class": "unfalsifiable_concern",
        "planted": 1,
        "recall": 1.0,
        "scope": "admissibility.evaluate"
      },
      {
        "caught": 1,
        "class": "empty_instance",
        "planted": 1,
        "recall": 1.0,
        "scope": "admissibility.evaluate"
      },
      {
        "caught": 1,
        "class": "non_falsifying_instance",
        "planted": 1,
        "recall": 1.0,
        "scope": "admissibility.evaluate"
      },
      {
        "caught": 1,
        "class": "unseated_objector",
        "planted": 1,
        "recall": 1.0,
        "scope": "admissibility.evaluate"
      }
    ],
    "scope": "admissibility.evaluate over four planted-bad objection classes",
    "unplanted_classes": [
      "nlp-classification-of-prose-vibes",
      "semantic-similarity-of-concern-wording"
    ]
  },
  "protocol": {
    "decision_rule": "CONSENTED iff admissible_objections == 0",
    "distinct_from": [
      "unanimity (explicit yes from every seat)",
      "veto (CNL-0024 named kill-right with override)",
      "majority (threshold of ballots)"
    ],
    "id": "consent-no-objection",
    "silence": "consent"
  },
  "question": "In a consent decision any objection blocks - so what makes an objection admissible, and what stops one participant from holding the council hostage with an unfalsifiable concern?",
  "residual_unknowns": [
    "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this worktree; the bar is executable from fixtures plus the catalog question.",
    "CNL-0023 and CNL-0024 artifacts are absent; residual, not a structural block for this unit."
  ],
  "reviewer": {
    "counterexample_or": "constructed-instance",
    "independent": true,
    "note": "Reviewer constructed a schema-valid non-falsifying instance (must be inadmissible) and an alternate two-absent-seat break (must be admissible). REFUTED-NOT-ATTEMPTED is not used.",
    "recount_agrees": true,
    "reviewer_id": "CNL-0060-probe2-reviewer-counterexample",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0060",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0060/probe1_both_states.py",
      "id": "probe1-both-states",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0060/probe2_reviewer_counterexample.py",
      "id": "probe2-reviewer",
      "result": "PASS"
    }
  ],
  "title": "Consent / no-objection and the admissibility bar for an objection",
  "unit_id": "CNL-0060"
}

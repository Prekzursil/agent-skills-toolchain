{
 "answer": "Four ceilings HARD-STOP: effort, time, tokens, turns. Seven dials DEGRADE: tool_calls, sources, experiments, speaking_quotas, maximum_inactivity, rebuttal_depth, escalation. One floor GATES consensus: minimum_engagement. The silent corruption is always the same shape: leftover agreement, a shrunk roster, unrun work scored complete, or a cap treated as an answer, rewritten as CONSENSUS. SUCCESS:CNL-0008",
 "artifacts": [
  {
   "path": "command-center/design/council/CNL-0008-budget-block-12-dials-and-the-exhaustion-semantics.md",
   "role": "primary"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
   "role": "executable-semantics"
  }
 ],
 "budgets_schema_fragment": {
  "$comment": "Typed fragment for the CouncilSpec v2 budgets block. CNL-0001 owns the root envelope; this unit specifies exhaustion semantics only.",
  "additionalProperties": false,
  "properties": {
   "dials": {
    "items": {
     "properties": {
      "exhaustion": {
       "enum": [
        "HARD_STOP",
        "DEGRADE",
        "GATE"
       ],
       "type": "string"
      },
      "id": {
       "enum": [
        "effort",
        "time",
        "tokens",
        "tool_calls",
        "sources",
        "experiments",
        "turns",
        "speaking_quotas",
        "minimum_engagement",
        "maximum_inactivity",
        "rebuttal_depth",
        "escalation"
       ],
       "type": "string"
      }
     },
     "required": [
      "id",
      "exhaustion"
     ],
     "type": "object"
    },
    "maxItems": 12,
    "minItems": 12,
    "type": "array"
   },
   "roster_frozen": {
    "const": true,
    "description": "MUTED and INACTIVE seats remain in the stopping set.",
    "type": "boolean"
   },
   "stopping_precedence": {
    "items": {
     "type": "string"
    },
    "minItems": 4,
    "type": "array"
   }
  },
  "required": [
   "dials",
   "stopping_precedence",
   "roster_frozen"
  ],
  "type": "object"
 },
 "claim_under_test": "Remaining speakers agreeing after a budget binds is CONSENSUS.",
 "claim_verdict": "REFUTED",
 "dials": [
  {
   "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
   "exhaustion": "HARD_STOP",
   "id": "effort",
   "kind": "ceiling",
   "markers": [
    "HARD_STOP:effort",
    "BUDGET_EXHAUSTED"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "BUDGET_EXHAUSTED",
   "roster_size": 3,
   "silent_corruption": "agreement_overrides_hard_stop: leftover speakers still agree, so the stop is labelled CONSENSUS after effort is already spent.",
   "stopping_set_size": 3,
   "wrong_choice": "DEGRADE (hurry remaining work / keep going cheaply)",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "BUDGET_EXHAUSTED",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
   "exhaustion": "HARD_STOP",
   "id": "time",
   "kind": "ceiling",
   "markers": [
    "HARD_STOP:time",
    "BUDGET_EXHAUSTED"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "BUDGET_EXHAUSTED",
   "roster_size": 3,
   "silent_corruption": "Time-pressure majority is recorded as CONSENSUS. Wall-clock is not recoverable; the stopping rule then cannot distinguish agreement from expiry.",
   "stopping_set_size": 3,
   "wrong_choice": "DEGRADE (hurry-up vote as the clock hits zero)",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "BUDGET_EXHAUSTED",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
   "exhaustion": "HARD_STOP",
   "id": "tokens",
   "kind": "ceiling",
   "markers": [
    "HARD_STOP:tokens",
    "BUDGET_EXHAUSTED"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "BUDGET_EXHAUSTED",
   "roster_size": 3,
   "silent_corruption": "Truncated arguments enter the vote unlabelled. A partial reads as a complete CONSENSUS.",
   "stopping_set_size": 3,
   "wrong_choice": "DEGRADE (emit truncated turns and still vote)",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "BUDGET_EXHAUSTED",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "CONSENSUS",
   "exhaustion": "DEGRADE",
   "id": "tool_calls",
   "kind": "capability",
   "markers": [
    "DEGRADED:tool_calls",
    "CONSENSUS",
    "COVERAGE_INCOMPLETE"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONSENSUS",
   "roster_size": 3,
   "silent_corruption": "unrun_counts_as_complete: coverage-gated stopping fires because missing tool results are treated as empty-success.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP the council, OR silent DEGRADE that treats unrun tools as done",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONSENSUS",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": false,
    "unrun_labelled_complete": true
   }
  },
  {
   "declared_reason_on_fixture": "CONSENSUS",
   "exhaustion": "DEGRADE",
   "id": "sources",
   "kind": "capability",
   "markers": [
    "DEGRADED:sources",
    "CONSENSUS",
    "COVERAGE_INCOMPLETE"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONSENSUS",
   "roster_size": 3,
   "silent_corruption": "Omitted citations fill the gap; a coverage target in the stopping expression fires on a search that did not happen.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP, OR treat unfetched sources as coverage-complete",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONSENSUS",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": false,
    "unrun_labelled_complete": true
   }
  },
  {
   "declared_reason_on_fixture": "CONSENSUS",
   "exhaustion": "DEGRADE",
   "id": "experiments",
   "kind": "capability",
   "markers": [
    "DEGRADED:experiments",
    "CONSENSUS",
    "COVERAGE_INCOMPLETE"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONSENSUS",
   "roster_size": 3,
   "silent_corruption": "Absence of an experiment is scored as 'no effect'. Coverage-complete CONSENSUS then masquerades as an empirical result.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP, OR treat unrun experiments as null results",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONSENSUS",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": false,
    "unrun_labelled_complete": true
   }
  },
  {
   "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
   "exhaustion": "HARD_STOP",
   "id": "turns",
   "kind": "ceiling",
   "markers": [
    "HARD_STOP:turns",
    "BUDGET_EXHAUSTED"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "BUDGET_EXHAUSTED",
   "roster_size": 3,
   "silent_corruption": "Turn cap becomes decorative. The last majority at the cap is stamped CONSENSUS \u2014 consensus-by-attrition.",
   "stopping_set_size": 3,
   "wrong_choice": "DEGRADE (one more round until someone agrees)",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "BUDGET_EXHAUSTED",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "CONTINUE",
   "exhaustion": "DEGRADE",
   "id": "speaking_quotas",
   "kind": "per-seat ceiling",
   "markers": [
    "DEGRADED:speaking_quotas"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONTINUE",
   "roster_size": 3,
   "silent_corruption": "shrink_roster_on_mute: a quota-silenced dissenter leaves the roster; remaining seats are unanimous. Silence-from-quota is treated as consent.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP the whole council, OR drop MUTED seats from the stopping set",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONTINUE",
    "depth_cap_as_answered": false,
    "roster_shrunk": true,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "ENGAGEMENT_UNMET",
   "exhaustion": "GATE",
   "id": "minimum_engagement",
   "kind": "floor",
   "markers": [
    "GATE:minimum_engagement",
    "ENGAGEMENT_UNMET"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "ENGAGEMENT_UNMET",
   "roster_size": 3,
   "silent_corruption": "engagement_among_speakers_only: unengaged seats fall out of the denominator. Thin participation yields CONSENSUS.",
   "stopping_set_size": 3,
   "wrong_choice": "DEGRADE (CONSENSUS among those who spoke) or mid-run HARD_STOP",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "ENGAGEMENT_UNMET",
    "depth_cap_as_answered": false,
    "roster_shrunk": true,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "CONTINUE",
   "exhaustion": "DEGRADE",
   "id": "maximum_inactivity",
   "kind": "per-seat ceiling",
   "markers": [
    "DEGRADED:maximum_inactivity"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONTINUE",
   "roster_size": 3,
   "silent_corruption": "shrink_roster_on_inactive: an AFK dissenter is removed from quorum; ALL-agree fires on the remainder.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP the council, OR drop INACTIVE seats from the stopping set",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONTINUE",
    "depth_cap_as_answered": false,
    "roster_shrunk": true,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "CONTINUE",
   "exhaustion": "DEGRADE",
   "id": "rebuttal_depth",
   "kind": "ladder",
   "markers": [
    "DEGRADED:rebuttal_depth",
    "OBLIGATION_OPEN"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "CONTINUE",
   "roster_size": 3,
   "silent_corruption": "depth_cap_counts_as_answered: unrebutted-because-capped claims count as unopposed, so a no-objection stopping expression fires.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP the council, OR treat DEPTH_CAPPED as answered/unopposed",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "CONTINUE",
    "depth_cap_as_answered": true,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  },
  {
   "declared_reason_on_fixture": "ESCALATION_EXHAUSTED",
   "exhaustion": "DEGRADE",
   "id": "escalation",
   "kind": "ladder",
   "markers": [
    "DEGRADED:escalation",
    "ESCALATION_EXHAUSTED"
   ],
   "observed_match": true,
   "observed_reason_on_fixture": "ESCALATION_EXHAUSTED",
   "roster_size": 3,
   "silent_corruption": "escalation_deadlock_is_consensus: 'we cannot climb' is filed as 'resolved at this tier'.",
   "stopping_set_size": 3,
   "wrong_choice": "HARD_STOP at first escalation, OR record stuck-tier as CONSENSUS",
   "wrong_choice_observed": {
    "corrupt_reason": "CONSENSUS",
    "declared_reason": "ESCALATION_EXHAUSTED",
    "depth_cap_as_answered": false,
    "roster_shrunk": false,
    "silently_became_consensus": true,
    "unrun_labelled_complete": false
   }
  }
 ],
 "evidence": [
  {
   "claim": "evaluate() is the declared stopping function; HARD_STOP binds before agreement.",
   "kind": "live-tree",
   "line": 255,
   "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
   "snippet": "def evaluate(state: CouncilState, policy: Policy = DECLARED) -> Verdict:"
  },
  {
   "claim": "masquerade_fires compares claimed CONSENSUS against declared reason \u2014 a second field.",
   "kind": "live-tree",
   "line": 432,
   "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
   "snippet": "def masquerade_fires("
  },
  {
   "claim": "Each dial has a planted exhaustion fixture used by both probes.",
   "kind": "live-tree",
   "line": 460,
   "path": "command-center/p2-wave/probes/CNL-0008/semantics.py",
   "snippet": "def fixture_for(dial: str) -> CouncilState:"
  }
 ],
 "question": "For each of the 12 budget dials (effort, time, tokens, tool calls, sources, experiments, turns, speaking quotas, minimum engagement, maximum inactivity, rebuttal depth, escalation), does exhaustion HARD-STOP the council or DEGRADE it - and which choice silently corrupts the stopping rule if made wrong?",
 "residual_unknowns": [
  "CNL-0001's CouncilSpec v2 root envelope is not on this worktree; this unit ships the budgets fragment and executable semantics, not the envelope merge.",
  "Numeric cap defaults (10/3/2) are fixture values, not production limits."
 ],
 "reviewer": {
  "counterexample": "turns cap 10/10 with alice/bob/cara all position=A evaluates to BUDGET_EXHAUSTED, not CONSENSUS. Claiming CONSENSUS FIRES the masquerade detector.",
  "independent": true,
  "reviewer_id": "CNL-0008-probe2-masquerade",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "roster_frozen": true,
 "sentinel": "SUCCESS:CNL-0008",
 "state": "SUCCESS",
 "stopping_precedence": [
  "HARD_STOP ceiling exhausted \u2192 BUDGET_EXHAUSTED (never CONSENSUS)",
  "minimum_engagement unmet on the stopping set \u2192 not CONSENSUS",
  "deadlock AND escalation exhausted \u2192 ESCALATION_EXHAUSTED",
  "outstanding depth-capped obligation \u2192 CONTINUE (cap is not an answer)",
  "all stopping-set positions agree AND floors met \u2192 CONSENSUS (may carry DEGRADED:* and COVERAGE_INCOMPLETE)",
  "else CONTINUE"
 ],
 "strongest_surviving_counterargument": "A DEGRADE capability (tool_calls/sources/experiments) CAN still end in CONSENSUS after the dial is exhausted, because the council may agree on already-gathered evidence. That is declared, not a masquerade \u2014 provided COVERAGE_INCOMPLETE stays on the artifact and unrun work is not scored complete. Treating that CONSENSUS as coverage-complete is the corruption; probe 2 observes CORRUPT:unrun_as_complete on the wrong-choice policy.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0008/probe1_exhaustion_per_dial.py",
   "id": "exhaustion_per_dial",
   "observed": {
    "effort": "BUDGET_EXHAUSTED",
    "escalation": "ESCALATION_EXHAUSTED",
    "experiments": "CONSENSUS",
    "maximum_inactivity": "CONTINUE",
    "minimum_engagement": "ENGAGEMENT_UNMET",
    "rebuttal_depth": "CONTINUE",
    "sources": "CONSENSUS",
    "speaking_quotas": "CONTINUE",
    "time": "BUDGET_EXHAUSTED",
    "tokens": "BUDGET_EXHAUSTED",
    "tool_calls": "CONSENSUS",
    "turns": "BUDGET_EXHAUSTED"
   },
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0008/probe2_masquerade_consensus.py",
   "id": "masquerade",
   "known_good": {
    "masquerade_fires": false,
    "reason": "CONSENSUS"
   },
   "planted_bad": {
    "agreement": true,
    "dial": "turns",
    "masquerade_fires": true,
    "reason": "BUDGET_EXHAUSTED"
   },
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0008/probe2_masquerade_consensus.py",
   "id": "negative_control",
   "midrun_engagement_unmet_reason": "CONTINUE",
   "result": "PASS",
   "what_the_check_does_on_the_state_it_rejects": "masquerade_fires(CONSENSUS, turns-exhausted AND remaining-agree) returns True (FIRES). On known-good consensus it returns False (SILENT)."
  }
 ],
 "title": "Budget block: 12 dials and the exhaustion semantics",
 "ts": "2026-08-25T00:51:16Z",
 "unit_id": "CNL-0008"
}

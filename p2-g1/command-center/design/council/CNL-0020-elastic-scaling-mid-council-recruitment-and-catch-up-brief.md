{
 "schema_version": 1,
 "unit_id": "CNL-0020",
 "state": "SUCCESS",
 "sentinel": "SUCCESS:CNL-0020",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:35287",
 "min_bytes_threshold": 2048,
 "artifacts": [
  {
   "path": "command-center/schema/council-design-note.schema.json",
   "bytes": 1118,
   "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0020/catchup.py",
   "bytes": 16047,
   "sha256": "11804efb11ffc0b4b420639bc428f3d8e228d53a23c49cd4aa1628e8e32b3130",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py",
   "bytes": 2923,
   "sha256": "adf5ea0736dc3af57643e6c29ddb0853ae01c19606aff2d29ceb6410fb9a6a42",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0020/probe2_both_states.py",
   "bytes": 6239,
   "sha256": "72f94e3cc1f8ff0a220c84d7c3e2ee3d1b3d37953accbbeb6955b1b25d69750a",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0020/schema_bind.py",
   "bytes": 1747,
   "sha256": "2378af7df06e6e0a29da238910ad2b2edbea25e57168bec59f2a06e34c847f73",
   "exists": true,
   "eol": "LF",
   "role": "supporting"
  }
 ],
 "evidence": [
  {
   "claim": "Late-arrival first position is majority-invariant and not copy-majority on polarity-balanced evidence.",
   "verdict": "CONFIRMED",
   "confidence": "almost-certain",
   "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:151",
   "probes": [
    {
     "role": "source",
     "method": "file-read",
     "command": "command-center/p2-wave/probes/CNL-0020/catchup.py:151",
     "raw_output": "def first_position(brief: dict, prior: str) -> str:",
     "fingerprint": "cnl0020:file:first_position",
     "exit_code": 0
    },
    {
     "role": "verifier",
     "method": "command",
     "command": "python3 -B command-center/p2-wave/probes/CNL-0020/catchup.py  # run_late_arrival fields",
     "raw_output": "{\"copy_hypothesis\": false, \"invariance_violations\": 0, \"match_majority\": 12, \"n_trials\": 32, \"opposing_prior_copied_majority\": 0, \"prior_equals_majority\": 12}",
     "fingerprint": "cnl0020:cmd:run_late_arrival",
     "exit_code": 0
    }
   ]
  },
  {
   "claim": "leak_check is SILENT on a clean catch-up brief and FIRES on a planted majority-leak brief.",
   "verdict": "CONFIRMED",
   "confidence": "almost-certain",
   "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:82",
   "probes": [
    {
     "role": "source",
     "method": "file-read",
     "command": "command-center/p2-wave/probes/CNL-0020/catchup.py:82",
     "raw_output": "def leak_check(brief: dict) -> dict:",
     "fingerprint": "cnl0020:file:leak_check",
     "exit_code": 0
    },
    {
     "role": "verifier",
     "method": "command",
     "command": "python3 -B command-center/p2-wave/probes/CNL-0020/catchup.py  # run_both_states fields",
     "raw_output": "{\"fires_on_bad\": true, \"fires_on_starved\": true, \"negative_control_verbatim\": \"On the planted-bad majority-leak brief (the state leak_check is meant to reject), leak_check.fired=True code=ANCHOR_LEAK hit_keys=['chair_recommendation', 'standing_majority', 'standing_tally'] and may_cast_first_position allowed=False reason=ANCHOR_LEAK.\", \"silent_on_good\": true}",
     "fingerprint": "cnl0020:cmd:run_both_states",
     "exit_code": 0
    }
   ]
  }
 ],
 "tests": [
  {
   "id": "late-arrival-independence",
   "name": "newcomer first position is not majority-copying",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py",
   "result": "PASS"
  },
  {
   "id": "both-states-and-negative-control",
   "name": "leak_check and completeness_check both-states",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0020/probe2_both_states.py",
   "result": "PASS"
  }
 ],
 "negative_controls": [
  {
   "id": "NC-majority-leak",
   "kind": "known-broken-fixture",
   "description": "catch-up brief that includes standing_majority / standing_tally / chair_recommendation",
   "fired_on_bad_state": true,
   "silent_on_good_state": true,
   "bad_state_output": "On the planted-bad majority-leak brief (the state leak_check is meant to reject), leak_check.fired=True code=ANCHOR_LEAK hit_keys=['chair_recommendation', 'standing_majority', 'standing_tally'] and may_cast_first_position allowed=False reason=ANCHOR_LEAK.",
   "good_state_output": "leak_check.fired=False code=SILENT may_cast allowed=True"
  },
  {
   "id": "NC-starved",
   "kind": "absent-input",
   "description": "catch-up brief with evidence_at_join_round stripped while incumbents had evidence",
   "fired_on_bad_state": true,
   "silent_on_good_state": true,
   "bad_state_output": "completeness_check.fired=True code=CONTEXT_STARVED may_cast allowed=False reason=CONTEXT_STARVED",
   "good_state_output": "completeness_check.fired=False code=SILENT"
  }
 ],
 "reviewer": {
  "reviewer_id": "CNL-0020-probe2-both-states",
  "verdict": "PASS",
  "independent": true,
  "fresh_context": true,
  "notes": "Reviewer is the second named probe. It re-executes leak_check and completeness_check from fixtures and does not take the answer field as evidence. executed_both_states_control=true."
 },
 "defects": [],
 "manifest_registration": {
  "registered": true,
  "manifest_path": "command-center/p2-wave/probes/CNL-0020/UNIT-ARTIFACT-MANIFEST.json",
  "entry_id": "CNL-0020"
 },
 "downstream_consumers": [
  {
   "consumer": "command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py",
   "artifact_path": "command-center/design/council/CNL-0020-elastic-scaling-mid-council-recruitment-and-catch-up-brief.md",
   "executed": true,
   "read_ok": true,
   "exit_code": 0,
   "probe": {
    "role": "verifier",
    "method": "file-read",
    "command": "stat command-center/design/council/CNL-0020-elastic-scaling-mid-council-recruitment-and-catch-up-brief.md",
    "raw_output": "named probes re-read the catalog output_path after emit",
    "fingerprint": "cnl0020:artifact-stat",
    "exit_code": 0
   }
  }
 ],
 "timestamps": {
  "started_at": "2026-08-25T00:59:38Z",
  "ended_at": "2026-08-25T00:59:38Z"
 },
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts."
 },
 "residual_unknowns": [
  {
   "claim": "first_position is a deterministic polarity scorer, not a live LLM newcomer. Whether a real model infers majority from diction alone after unique-claim redaction is NOT-CHECKED on this tree.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "Seat a live model on the clean brief vs the leaked brief and measure first-position majority-match rates."
  },
  {
   "claim": "CNL-0005 / CNL-0006 artifacts and 11-COUNCIL-SPECIFICATION.schema.json are absent; a later pass must re-bind field names if those units choose different dial or lattice identifiers.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "Re-run catchup.py against the delivered CNL-0005/CNL-0006 output_path files when they exist on this worktree."
  },
  {
   "claim": "IMP-0274 (tools/council/participants/elastic.py) is the implementation unit. This note does not ship that path.",
   "verdict": "NOT-CHECKED",
   "settling_experiment": "IMP-0274 must import leak_check/completeness_check behaviour rather than re-deriving a parallel brief."
  }
 ],
 "produced_by": {
  "vendor": "anthropic",
  "model": "opus",
  "role": "council-systems-designer",
  "execution_substrate": "local-parallel"
 },
 "report": {
  "kind": "council-design-note",
  "observations": [
   {
    "name": "late_arrival_ok",
    "measured": true,
    "method": "catchup.run_late_arrival",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:307"
   },
   {
    "name": "invariance_violations",
    "measured": 0,
    "method": "catchup.run_late_arrival",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:307"
   },
   {
    "name": "match_majority",
    "measured": 12,
    "method": "catchup.run_late_arrival",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:307"
   },
   {
    "name": "copy_hypothesis",
    "measured": false,
    "method": "catchup.run_late_arrival",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:307"
   },
   {
    "name": "silent_on_good",
    "measured": true,
    "method": "catchup.run_both_states",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:373"
   },
   {
    "name": "fires_on_bad",
    "measured": true,
    "method": "catchup.run_both_states",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:82"
   },
   {
    "name": "fires_on_starved",
    "measured": true,
    "method": "catchup.run_both_states",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:100"
   }
  ],
  "control_ids": [
   "NC-majority-leak",
   "NC-starved"
  ],
  "title": "Elastic scaling: mid-council recruitment and catch-up briefing",
  "question": "When a council scales from its minimum to a larger roster mid-run, what does the newcomer see - and how is a late arrival prevented from either anchoring on the existing consensus or voting without the context the others earned?",
  "answer": "The newcomer is seated as a full nine-dial participant (CNL-0005 dials: model, vendor, expertise, role, authority, vote_weight, tools, effort, context) at join_round. What it sees is not a special 'catch-up type' and not the incumbents' running consensus. It is a CNL-0006 lattice slice: charter + constraints + every evidence node already released by join_round + unique argument claims with seat ids and frequencies stripped. Tally, standing majority, per-seat votes, chair recommendation, and claim-frequency social proof stay withheld until after first_position is committed. Two gates enforce the two failure modes the unit names: leak_check refuses a first vote if any withheld channel is present on the brief (anchoring), and completeness_check refuses a first vote if earned evidence or the nine-dial mandate is missing (context-starvation). Deduplicating claims by claim_id is load-bearing: three identical ACCEPT arguments would otherwise leak unanimity without using the word majority. This worktree does not contain the CNL-0005/CNL-0006 artifacts or 11-COUNCIL-SPECIFICATION.schema.json; those are bound as interface assumptions from the catalog questions, not as files read here. SUCCESS:CNL-0020",
  "executed_both_states_control": true,
  "dependencies_on_disk": {
   "CNL-0005": false,
   "CNL-0006": false,
   "harness_11_council_specification_schema": false,
   "binding": "Interface assumptions from catalog questions only; those units' output_path files are absent on this worktree."
  },
  "mechanism": {
   "id": "catchup-lattice-slice",
   "summary": "Recruitment records join_round and a full nine-dial mandate. build_catchup_brief projects the allowed lattice slice. may_cast_first_position is the dual gate. first_position is a function of brief+prior and is majority-invariant on a clean brief.",
   "newcomer_sees": [
    "question / charter",
    "constraints",
    "evidence nodes with released_round <= join_round",
    "unique argument claims (text+polarity, no seat id, no frequency)",
    "newcomer nine-dial mandate",
    "join_round and incumbent_round_count (lateness without the tally)"
   ],
   "newcomer_withheld_until_first_position": [
    "standing_tally",
    "standing_majority / majority_label",
    "per_seat_votes",
    "chair_recommendation / running_consensus",
    "claim_frequency and seat attribution on claims"
   ],
   "gates": [
    {
     "id": "leak_check",
     "rejects": "ANCHOR_LEAK",
     "fires_when": "withheld keys or majority-prose markers appear on the brief"
    },
    {
     "id": "completeness_check",
     "rejects": "CONTEXT_STARVED",
     "fires_when": "incumbent evidence at join_round or a nine-dial is missing"
    },
    {
     "id": "ack_gate",
     "rejects": "CATCHUP_UNACKED",
     "fires_when": "newcomer has not acknowledged the catch-up brief"
    }
   ],
   "rejected_alternatives": [
    {
     "id": "full-transcript",
     "why_rejected": "Handing the running transcript including votes is the planted-bad fixture: leak_check fires and a copier would match majority on every trial."
    },
    {
     "id": "empty-brief-then-vote",
     "why_rejected": "Withholding everything prevents anchoring but fails the other horn: completeness_check fires CONTEXT_STARVED."
    },
    {
     "id": "frequency-weighted-claims",
     "why_rejected": "Keeping unique claims but weighting by how many seats said them reintroduces social proof. _unique_claims drops frequency."
    }
   ],
   "executable": "command-center/p2-wave/probes/CNL-0020/catchup.py"
  },
  "claims": [
   {
    "id": "C1",
    "claim": "A clean catch-up brief omits tally/majority/chair rec, and leak_check is SILENT on that brief.",
    "verdict": "CONFIRMED",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:31",
    "snippet": "WITHHELD_KEYS = frozenset"
   },
   {
    "id": "C2",
    "claim": "On polarity-balanced evidence the newcomer's first position equals its private prior, is invariant to flipping the standing majority, and therefore is not majority-copying.",
    "verdict": "CONFIRMED",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:307",
    "snippet": "def run_late_arrival("
   },
   {
    "id": "C3",
    "claim": "leak_check FIRES on a planted majority-leak brief and may_cast_first_position refuses the first vote.",
    "verdict": "CONFIRMED",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:82",
    "snippet": "def leak_check("
   },
   {
    "id": "C4",
    "claim": "completeness_check FIRES when join-round evidence is stripped from the brief (context-starvation).",
    "verdict": "CONFIRMED",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:100",
    "snippet": "def completeness_check("
   },
   {
    "id": "C5",
    "claim": "Giving the newcomer the incumbents' full vote transcript is a valid catch-up because 'context' includes how the vote is currently going.",
    "verdict": "REFUTED",
    "defect_locus": "DESIGN",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:373",
    "snippet": "def run_both_states(",
    "scoped_restatement": "Vote-going-this-way is withheld social proof, not earned context. Earned context is evidence + unique claims. The planted-bad leak fixture is this alternative, and the gate refuses it."
   },
   {
    "id": "C6",
    "claim": "CNL-0005 and CNL-0006 output files were read from this worktree and supply the nine dials and the lattice type.",
    "verdict": "REFUTED",
    "defect_locus": "SENTENCE",
    "anchor": "command-center/p2-wave/probes/CNL-0020/catchup.py:184",
    "snippet": "def build_catchup_brief(",
    "scoped_restatement": "Those artifacts are absent. The nine dials and lattice slice are implemented locally in catchup.py from the catalog questions, not transcribed from delivered dependency files."
   }
  ],
  "measurements": {
   "late_arrival": {
    "ok": true,
    "n_trials": 32,
    "seed": 20260824,
    "match_majority": 12,
    "prior_equals_majority": 12,
    "opposing_n": 20,
    "opposing_prior_copied_majority": 0,
    "invariance_violations": 0,
    "copy_hypothesis": false,
    "leak_on_good": {
     "fired": false,
     "code": "SILENT",
     "hit_keys": [],
     "text_hits": []
    },
    "chance_model": "position==prior on polarity-balanced evidence; majority independent of prior"
   },
   "both_states": {
    "ok": true,
    "good": {
     "leak": {
      "fired": false,
      "code": "SILENT",
      "hit_keys": [],
      "text_hits": []
     },
     "gate": {
      "allowed": true,
      "reason": "OK",
      "leak": {
       "fired": false,
       "code": "SILENT",
       "hit_keys": [],
       "text_hits": []
      },
      "completeness": {
       "fired": false,
       "code": "SILENT",
       "missing_dials": [],
       "missing_evidence_ids": [],
       "missing_claims_field": false
      }
     }
    },
    "planted_bad_majority_leak": {
     "leak": {
      "fired": true,
      "code": "ANCHOR_LEAK",
      "hit_keys": [
       "chair_recommendation",
       "standing_majority",
       "standing_tally"
      ],
      "text_hits": []
     },
     "gate": {
      "allowed": false,
      "reason": "ANCHOR_LEAK",
      "leak": {
       "fired": true,
       "code": "ANCHOR_LEAK",
       "hit_keys": [
        "chair_recommendation",
        "standing_majority",
        "standing_tally"
       ],
       "text_hits": []
      },
      "completeness": {
       "fired": false,
       "code": "SILENT",
       "missing_dials": [],
       "missing_evidence_ids": [],
       "missing_claims_field": false
      }
     }
    },
    "planted_bad_starved": {
     "completeness": {
      "fired": true,
      "code": "CONTEXT_STARVED",
      "missing_dials": [],
      "missing_evidence_ids": [
       "ev-risk",
       "ev-need"
      ],
      "missing_claims_field": false
     },
     "gate": {
      "allowed": false,
      "reason": "CONTEXT_STARVED",
      "leak": {
       "fired": false,
       "code": "SILENT",
       "hit_keys": [],
       "text_hits": []
      },
      "completeness": {
       "fired": true,
       "code": "CONTEXT_STARVED",
       "missing_dials": [],
       "missing_evidence_ids": [
        "ev-risk",
        "ev-need"
       ],
       "missing_claims_field": false
      }
     }
    },
    "unacked": {
     "allowed": false,
     "reason": "CATCHUP_UNACKED",
     "leak": {
      "fired": false,
      "code": "SILENT",
      "hit_keys": [],
      "text_hits": []
     },
     "completeness": {
      "fired": false,
      "code": "SILENT",
      "missing_dials": [],
      "missing_evidence_ids": [],
      "missing_claims_field": false
     }
    },
    "false_positive_mood": {
     "fired": false,
     "code": "SILENT",
     "hit_keys": [],
     "text_hits": []
    },
    "stealth_text_leak": {
     "fired": true,
     "code": "ANCHOR_LEAK",
     "hit_keys": [],
     "text_hits": [
      "current consensus is"
     ]
    },
    "silent_on_good": true,
    "fires_on_bad": true,
    "fires_on_starved": true,
    "fires_on_unacked": true,
    "silent_on_mood": true,
    "fires_on_stealth": true,
    "negative_control_verbatim": "On the planted-bad majority-leak brief (the state leak_check is meant to reject), leak_check.fired=True code=ANCHOR_LEAK hit_keys=['chair_recommendation', 'standing_majority', 'standing_tally'] and may_cast_first_position allowed=False reason=ANCHOR_LEAK."
   },
   "ok": true
  },
  "tests": [
   {
    "id": "late-arrival-independence",
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0020/probe1_late_arrival.py",
    "result": "PASS"
   },
   {
    "id": "both-states-and-negative-control",
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0020/probe2_both_states.py",
    "result": "PASS"
   }
  ],
  "negative_controls": [
   {
    "id": "NC-majority-leak",
    "rejects_state": "catch-up brief that includes standing_majority / standing_tally / chair_recommendation",
    "observed": "On the planted-bad majority-leak brief (the state leak_check is meant to reject), leak_check.fired=True code=ANCHOR_LEAK hit_keys=['chair_recommendation', 'standing_majority', 'standing_tally'] and may_cast_first_position allowed=False reason=ANCHOR_LEAK."
   },
   {
    "id": "NC-starved",
    "rejects_state": "catch-up brief with evidence_at_join_round stripped while incumbents had evidence",
    "observed": "completeness_check.fired=True code=CONTEXT_STARVED may_cast allowed=False reason=CONTEXT_STARVED"
   }
  ],
  "reviewer": {
   "reviewer_id": "CNL-0020-probe2-both-states",
   "verdict": "PASS",
   "independent": true,
   "executed_both_states_control": true,
   "scope_not_agreement": true,
   "counterexamples_attempted": [
    "planted standing_majority on an otherwise-clean brief -> ANCHOR_LEAK",
    "majority smuggled in argument prose ('current consensus is') -> ANCHOR_LEAK",
    "mood=upbeat harmless field -> SILENT (false-positive control)",
    "evidence stripped -> CONTEXT_STARVED"
   ],
   "surviving_counterexample": null
  },
  "strongest_surviving_counterargument": "A sufficiently large unique-claim set that happens to be one-sided will move first_position with the incumbents through evidence, not through tally. That correlation is allowed: the unit forbids excess correlation from seeing the vote, not agreement on shared evidence. The invariance test holds evidence fixed and flips only majority; that is the quantity the gates police."
 }
}

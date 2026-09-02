{
  "unit_id": "CNL-0071",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0071",
  "title": "Irreducible disagreement: when to stop trying to converge",
  "output_schema": "command-center/schema/council-design-note.schema.json",
  "catalog_path_is_md_bytes_are_json": true,
  "question": "What distinguishes a disagreement that more rounds would resolve from one that no amount of deliberation can - and what evidence must accompany an irreducible-disagreement verdict so it is not simply fatigue relabelled?",
  "answer": "More rounds can still resolve a disagreement when the attached information-gain trace shows the last stable_window rounds still moving: new claim ids, new evidence ids, or vote Hamming > 0 (signal 1) AND a sha256 mismatch of the canonical claim/evidence dumps or vote tuple (signal 2). No amount of further deliberation is the right call only when those two signals agree that gain has collapsed for the window, the position partition is unchanged, and the record names an irreducible_set of at least two claims that cannot be jointly satisfied for a reason that is not budget, timeout, or fatigue. Round-budget exhaustion without that pack is no-decision / fatigue, not irreducible-disagreement.",
  "distinction": {
    "resolvable_if": "last defined round-gain > 0, or any round inside stable_window still moved on either independent signal.",
    "irreducible_if": "honest trace attached, both signals agree gain==0 and moved==false for stable_window consecutive rounds, stop_reason is an incommensurability class, and irreducible_set names the mutually unsatisfiable claims.",
    "fatigue_is_not": "stop_reason in {round-budget, timeout, fatigue, chair-discretion, majority-tired}, or an irreducible_set whose why is tired/budget, even if gain has already hit zero.",
    "not_deadlock": "CNL-0084 (not delivered on this tree) is process-stuck vs slow-but-progressing. This unit is epistemic: still-moving disagreement vs named incommensurability after gain collapse.",
    "not_circular_debate_detector": "CNL-0090 (not delivered) detects circling. Circling without a named irreducible_set is circular-debate, not irreducible-disagreement."
  },
  "irreducible_verdict_requirements": [
    "information_gain_trace attached covering every round; missing trace fails the declaration",
    "recomputed trace must match the attached one (forged zero-gain is rejected)",
    "signal 1 (set cardinality + vote Hamming) and signal 2 (sha256 canonical dump inequality) must agree; disagreement fails closed",
    "last stable_window rounds (default 2) have gain==0 and moved==false",
    "stop_reason in {incommensurable-positions, incompatible-evidence-standards, mutually-exclusive-axioms}",
    "irreducible_set has >=2 paired claims with a why that is not fatigue/budget/timeout"
  ],
  "gain_definition": {
    "signal_1": "gain(t)=|claims_t-claims_{t-1}|+|evidence_t-evidence_{t-1}|+Hamming(votes_t,votes_{t-1})",
    "signal_2": "moved(t)=sha256(canon(claim_ids)) or sha256(canon(evidence_ids)) or vote-tuple differs",
    "round_1": "no predecessor; gain and moved are undefined",
    "identifier_not_lexical": "Gain is over claim/evidence identifiers, not paraphrase text. A rewrite of the same id is NOT counted as gain here. Semantic uniqueness is CNL-0051 / CNL-0090 and is residual."
  },
  "claims": [
    {
      "id": "C1",
      "claim": "Declaring irreducible-disagreement while last-round information gain is still positive must be rejected.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/irreducibility.py:150"
    },
    {
      "id": "C2",
      "claim": "An irreducible declaration with no attached information-gain trace must be rejected.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/irreducibility.py:92"
    },
    {
      "id": "C3",
      "claim": "Zero-gain plus a round-budget/fatigue stop is fatigue relabel, not irreducible-disagreement.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/irreducibility.py:185"
    },
    {
      "id": "C4",
      "claim": "A collapsed-gain run with incommensurable-positions and a two-claim irreducible_set is accepted (known-good silent).",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/probe2_negative_control.py:1"
    }
  ],
  "evidence": [
    {
      "claim": "Catalog question and the positive-gain fail test for this unit.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:37817",
      "second_anchor": "command-center/WORK-UNIT-CATALOG.json:37821"
    },
    {
      "claim": "Signal 1 is cardinality+Hamming, not a hash.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/gain.py:45"
    },
    {
      "claim": "Signal 2 is sha256/tuple inequality, not a count.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/fingerprint.py:43"
    },
    {
      "claim": "Planted-bad last gain is positive; known-good last gain is 0.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0071/fixtures/planted-bad.json:1",
      "measured": {
        "planted_bad_last_gain": 3,
        "known_good_last_gain": 0,
        "planted_bad_check": {
          "fired": true,
          "silent": false,
          "accepted": false,
          "reason": "positive-gain",
          "last_gain": 3,
          "last_moved": true
        },
        "known_good_check": {
          "fired": false,
          "silent": true,
          "accepted": true,
          "reason": "irreducible-evidence-complete",
          "last_gain": 0,
          "window": 2
        },
        "fatigue_check": {
          "fired": true,
          "silent": false,
          "accepted": false,
          "reason": "fatigue-relabel",
          "stop_reason": "round-budget"
        },
        "planted_bad_moves_last": {
          "claims_fp_prev": "d667fac15f6548f44116df2edc7afdcf2810f6a317018b0389b3561d2eaa930c",
          "claims_fp_curr": "f23693a42b9e6aaa5d97908e76e6d257e4413f92f737533ae91017fa2be7b544",
          "evidence_fp_prev": "b85b43f28c97dd5994f2e9a9b35b2854a62e8c278897a7e2bb70ae0247a076b3",
          "evidence_fp_curr": "f0152cc85f9b363a9cbbdb153ea3eab7a8f2f62bfdb00ec3f332a5bf694d266a",
          "votes_moved": true,
          "claims_moved": true,
          "evidence_moved": true,
          "moved": true,
          "signal": "sha256-canonical-dump-inequality",
          "round": 3
        },
        "known_good_moves_last": {
          "claims_fp_prev": "85f3dd5aad6ea52944a357410b40003ca950241e73c5a48352aeae7c240a57d4",
          "claims_fp_curr": "85f3dd5aad6ea52944a357410b40003ca950241e73c5a48352aeae7c240a57d4",
          "evidence_fp_prev": "22249aa61fd2594e50910aa574afbb977f9df8f7377e6f02e19c72245d899ad8",
          "evidence_fp_curr": "22249aa61fd2594e50910aa574afbb977f9df8f7377e6f02e19c72245d899ad8",
          "votes_moved": false,
          "claims_moved": false,
          "evidence_moved": false,
          "moved": false,
          "signal": "sha256-canonical-dump-inequality",
          "round": 3
        }
      }
    }
  ],
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0071/probe1_positive_gain_must_fail.py",
      "result": "PASS",
      "requirement": "information-gain trace attached; declaring irreducibility while gain is still positive must FAIL"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0071/probe2_negative_control.py",
      "result": "PASS",
      "requirement": "negative control recorded verbatim: what the check does on the state it is meant to reject"
    }
  ],
  "negative_controls": [
    {
      "rejected_state": "declared_outcome=irreducible-disagreement AND last-round information gain > 0",
      "check_behavior": "FIRES (rejects the declaration) with reason=positive-gain",
      "verbatim": "rejected_state=declared_outcome=irreducible-disagreement AND last-round information gain > 0; planted-bad fired=True reason=positive-gain last_gain=3; known-good fired=False silent=True reason=irreducible-evidence-complete",
      "known_good_behavior": "SILENT / accepted=true with reason=irreducible-evidence-complete"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0071-probe1-positive-gain-counterexample",
    "verdict": "PASS",
    "independent": true,
    "scope_not_agreement": true,
    "counterexample": "fixtures/planted-bad.json declares irreducible-disagreement with last_gain=3; check fires reason=positive-gain.",
    "human_fresh_context": "REFUTED-NOT-ATTEMPTED"
  },
  "strongest_surviving_counterargument": "Identifier-set gain treats a same-id paraphrase as zero content gain. If members only reword C1/C2, this unit will allow an irreducible verdict once votes also freeze. Whether that paraphrase is still 'new information' is CNL-0051/CNL-0090 and is NOT-CHECKED here. The 0.95 consensus interaction is CNL-0069, also residual.",
  "dependencies_on_this_tree": {
    "CNL-0069": "artifact absent \u2014 consensus number not used as a gate in this check",
    "CNL-0084": "artifact absent \u2014 deadlock ladder not used; distinction stated in prose only"
  },
  "inputs_on_this_tree": {
    "_USER-PROMPTS.md:10746-10767": false,
    "_USER-PROMPTS.md:10915-10946": false,
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "note": "Harness paths from the catalog are not present on this worktree. No quotes from those files are invented. Anchors are catalog + live probes."
  },
  "schema_garbage_control": {
    "ok": true,
    "detail": "garbage-rejected-3-of-3"
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "schema"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0071/irreducibility.py",
      "exists": true,
      "role": "check"
    }
  ],
  "residual_unknowns": [
    "Harness restore files named in catalog inputs are absent; v1 $defs.outcome 17-enum not re-derived here (that is CNL-0072).",
    "CNL-0069 0.95 consensus definition is not on disk; this unit does not treat consensus>=0.95 as irreducibility.",
    "CNL-0084 deadlock escalation ladder is not on disk.",
    "Semantic paraphrase-vs-new-claim (CNL-0051) is not this metric.",
    "A separate human reviewer in a fresh context was REFUTED-NOT-ATTEMPTED; the executable counterexample is probe1."
  ],
  "SUCCESS:CNL-0071": true
}

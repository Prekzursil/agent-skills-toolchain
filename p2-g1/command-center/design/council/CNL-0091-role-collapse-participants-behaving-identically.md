{
  "unit_id": "CNL-0091",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0091",
  "report_kind": "council-detector-spec",
  "title": "Role collapse: participants behaving identically",
  "question": "What behavioural distance metric shows that the critic has started behaving like the proposer - and what is the distance between two seats that genuinely agree?",
  "pathology": "The critic seat produces proposer speech-acts and proposer lexicon, so assigned roles are no longer recoverable from behaviour. Shared conclusions are not the pathology.",
  "depends_on": [
    "CNL-0027"
  ],
  "dependency_note": "CNL-0027 triad mandates are not delivered on this tree; this spec uses the catalog obligation split (proposer constructs, critic tests) and does not rebuild ADV-0092.",
  "markdown_spec": "# CNL-0091 Role collapse: participants behaving identically\n\n## Question\n\nWhat behavioural distance metric shows that the critic has started behaving\nlike the proposer \u2014 and what is the distance between two seats that\ngenuinely agree?\n\n## Pathology\n\nRole collapse is not \u201cthe critic endorsed the same conclusion\u201d. Two seats\nthat genuinely agree still owe different obligations: the proposer\nconstructs; the critic steelmans, names residual risk, and states the\nconditions of agreement. Collapse is when those obligations are no longer\nrecoverable from the text \u2014 the critic has started *behaving* like the\nproposer. A Role: label is not a behaviour.\n\nThis unit depends on the CNL-0027 triad (proposer / critic / synthesiser)\nas a mandate source. CNL-0027 is not delivered on this tree; the detector\ntreats the triad as: proposer constructs a proposal, critic tests it,\nsynthesiser may not silently become a third critic or a second proposer.\nOnly the proposer\u2013critic pair is scored here.\n\n## Metric (two independent signals)\n\nDo **not** use stance/conclusion distance as the fire statistic. Genuine\nagreement and collapse both have low stance distance; a stance detector is\nsilent in the planted-bad state *or* fires on every real agreement, and\nin either case measures nothing useful.\n\nSignal A (`d_act`): L1/2 distance between speech-act histograms over\n{propose, critique, steelman, condition}. Bag counts of disjoint phrase\nlists.\n\nSignal B (`d_sig`): absolute difference of role-lexicon skew, using a\n**disjoint** vocabulary (implementation-plan markers vs failure-mode\nmarkers). Different tokens, different aggregation from A.\n\nCombined: `d = (d_act + d_sig) / 2` in `[0, 1]`.\n\nFire when `d < 0.35`. The gate is pre-registered in `detector.py` as\n`COLLAPSE_GATE`; fixtures were written to the role-lexicon contract, not\ntuned after seeing distances.\n\nProbe 2 is a third, order-based mechanism: the first matching speech-act\nphrase classifies the seat. A collapsed critic is recovered as proposer;\na genuine-agreement critic is still recovered as critic.\n\n## Distance between seats that genuinely agree\n\nThat distance is `d_combined` on the `genuine-agreement` fixture \u2014 a\nnumber, not an adjective. It sits with the diverse (known-good) cluster,\nabove the gate, even though `d_stance` on that pair is ~0 (same\nconclusion). Stance cannot tell collapse from agreement; role-obligation\ndistance can.\n\n## Controls\n\n1. Known-present first: `collapsed-calibrate` must FIRE before any\n   absence is reported. If it does not, the fixture is broken (retry\n   policy: fix the fixture once; do not count a mechanism failure).\n2. Known-good: `diverse-calibrate` must be SILENT.\n3. Negative control: `genuine-agreement` is the state a stance metric\n   would treat as collapse. This detector must be SILENT. Recorded\n   verbatim in the both-states object.\n4. Hold-out planted-bad: paraphrased collapse (different wording, same\n   acts) must still FIRE \u2014 lexical Jaccard alone would miss it.\n5. False-positive rate is reported as a number over the four clean\n   fixtures.\n\nADV-0092 is a later pathology simulation of five-role differentiation.\nThis unit does not rebuild it.\n",
  "metric": {
    "name": "role-obligation combined L1",
    "combined_formula": "d = (d_act + d_sig) / 2; fire iff d < COLLAPSE_GATE",
    "does_not_use": "stance/conclusion Jaccard, Role: labels, or token-set Jaccard on the full brief",
    "signals": [
      {
        "id": "A-act",
        "name": "d_act",
        "mechanism": "L1/2 distance of speech-act histograms over propose/critique/steelman/condition phrase bags"
      },
      {
        "id": "B-sig",
        "name": "d_sig",
        "mechanism": "absolute difference of critic-lexicon skew using vocab disjoint from the speech-act phrase lists"
      }
    ],
    "foil": {
      "name": "d_stance",
      "mechanism": "Jaccard distance of conclusion: token sets",
      "why_not_the_metric": "collapsed-calibrate and genuine-agreement both have d_stance\u22480 (measured 0.0 vs 0.0); stance cannot separate them"
    },
    "probe2_mechanism": "first matching speech-act phrase classifies the seat; collapsed critic recovers as proposer, agreement critic recovers as critic"
  },
  "thresholds": {
    "collapse_gate": 0.35,
    "gate_registration": "pre-registered",
    "collapsed_anchor_distance": 0.0,
    "diverse_anchor_distance": 1.0,
    "genuine_agreement_distance": 1.0,
    "paraphrase_collapse_distance": 0.0
  },
  "answers": {
    "behavioural_distance_metric": "Mean of speech-act histogram L1/2 (d_act) and disjoint role-lexicon skew gap (d_sig). A critic has started behaving like the proposer when that combined distance falls below the pre-registered gate 0.35. Stance distance is recorded as a foil and is not used.",
    "genuine_agreement_distance": 1.0
  },
  "both_states": {
    "known_present_evaluated_first": true,
    "fired_on_bad": true,
    "silent_on_good": true,
    "planted_bad_id": "collapsed-calibrate",
    "known_good_id": "diverse-calibrate",
    "verbatim": "CONTROL-FIRST id=collapsed-calibrate d_combined=0.0 d_stance=0.0 fired=True gate=0.35 | KNOWN-GOOD id=diverse-calibrate d_combined=1.0 d_stance=0.571429 fired=False | NEG-CONTROL id=genuine-agreement d_combined=1.0 d_stance=0.0 fired=False | HOLD OUT id=collapsed-paraphrase d_combined=0.0 d_stance=0.0 fired=True"
  },
  "false_positive_rate": 0.0,
  "false_negative_rate": 0.0,
  "negative_control": {
    "id": "genuine-agreement",
    "rejects_state": "two seats that share a conclusion while the critic still discharges steelman/condition/failure-mode obligations",
    "check_does": "stays SILENT because d_combined remains above the gate even though d_stance is ~0; a stance detector would fire",
    "fired": false,
    "verbatim": "NEG-CONTROL genuine-agreement d_combined=1.0 d_stance=0.0 fired=False (stance is low; detector stays silent)"
  },
  "tests": [
    {
      "id": "T-PROBE-1-BOTH-STATES",
      "name": "Known-present first, then known-good silence, then agreement silence",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0091/probe1_both_states.py",
      "result": "PASS",
      "exit_code": 0,
      "output_tail": "CONTROL-FIRST id=collapsed-calibrate d_combined=0.0 d_stance=0.0 fired=True gate=0.35\nKNOWN-GOOD id=diverse-calibrate d_combined=1.0 d_stance=0.571429 fired=False\nNEG-CONTROL id=genuine-agreement d_combined=1.0 d_stance=0.0 fired=False\nHOLD OUT id=collapsed-paraphrase d_combined=0.0 d_stance=0.0 fired=True\nfired_on_bad=True silent_on_good=True silent_on_agree=True d_collapse=0.0 d_agree=1.0 d_stance_collapse=0.0 d_stance_agree=0.0\nSUCCESS:CNL-0091-probe1 both-states control-first"
    },
    {
      "id": "T-PROBE-2-ROLE-RECOVERY",
      "name": "Order-based role recovery, numeric FP rate, schema garbage rejection",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0091/probe2_role_recovery.py",
      "result": "PASS",
      "exit_code": 0,
      "output_tail": "false_positive_rate=0.0 n_clean=4\nfalse_negative_rate=0.0 n_bad=2\nschema_garbage_rejected=3/3\nrole_guess_collapsed_critic=proposer role_guess_agree_critic=critic d_agree=1.0 artifact_checked=False\nSUCCESS:CNL-0091-probe2 role-recovery schema-discrimination"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0091-probe2-both-states-rerun",
    "verdict": "PASS",
    "independent": true,
    "reran_both_states": true,
    "scope": "Re-derived fire/silence from fixtures via first-act classification and a second detector.score_all() call; did not copy probe 1 claimed fields. Cross-vendor Codex is the catalog reviewer_requirement; this tree records the executable re-run rather than fabricating a vendor."
  },
  "evidence": [
    {
      "path": "command-center/p2-wave/probes/CNL-0091/detector.py",
      "line": 28,
      "snippet": "COLLAPSE_GATE = 0.35",
      "kind": "spec",
      "claim": "Collapse gate is pre-registered, not fit after seeing distances.",
      "anchor": "command-center/p2-wave/probes/CNL-0091/detector.py:28"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/detector.py",
      "line": 11,
      "snippet": "Stance/conclusion Jaccard is computed",
      "kind": "spec",
      "claim": "Stance is a foil and is never the fire statistic.",
      "anchor": "command-center/p2-wave/probes/CNL-0091/detector.py:11"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/detector.py",
      "line": 132,
      "snippet": "Order-based classifier: earliest matching speech-act phrase",
      "kind": "live-tree",
      "claim": "Probe 2 recovers role from phrase order, not from bag L1.",
      "anchor": "command-center/p2-wave/probes/CNL-0091/detector.py:132"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/fixtures.json",
      "line": 51,
      "snippet": "\"id\": \"genuine-agreement\"",
      "kind": "live-tree",
      "claim": "Genuine-agreement fixture shares a conclusion and keeps critic acts.",
      "anchor": "command-center/p2-wave/probes/CNL-0091/fixtures.json:51"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 38838,
      "snippet": "What behavioural distance metric shows that the critic has started behaving like the proposer",
      "kind": "catalog",
      "claim": "Catalog question for CNL-0091 is the question this spec answers.",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:38838"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0091-role-collapse-participants-behaving-identically.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/detector-spec.schema.json",
      "exists": true,
      "role": "schema"
    },
    {
      "path": "command-center/schema/council-detector-spec.schema.json",
      "exists": true,
      "role": "catalog-schema-shim"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/detector.py",
      "exists": true,
      "role": "detector"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0091/fixtures.json",
      "exists": true,
      "role": "fixtures"
    }
  ],
  "produced_at": "2026-08-25T00:55:41Z",
  "completion_line": "SUCCESS:CNL-0091"
}
